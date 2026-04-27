"""
Neptune AIS data fetcher.

Connects to AISStream.io's WebSocket feed and persists vessel position reports
to the Neptune database. Designed to run as a long-lived background process
independent of the Flask web app.

Why WebSockets and not a REST poll?
  AIS data is a firehose: a single ship broadcasts a position report every 2-10
  seconds, and there are ~50,000 vessels active globally at any moment. Polling
  REST endpoints would either miss updates or hammer the upstream API. The
  AISStream WebSocket pushes only the messages you've subscribed to (filtered
  by bounding box and message type).

Why a separate process and not a Flask background thread?
  Long-lived WebSocket consumers shouldn't share a process with a web server.
  The web server scales by spawning workers (gunicorn forks); the WebSocket
  client must be a single, stable connection. Mixing them either duplicates
  the connection (cost + dedupe headaches) or makes scaling the web server
  impossible.

Resilience features:
  - Exponential backoff on reconnect (capped at 60s)
  - Bounded in-memory deduplication: we won't write the same (mmsi, timestamp)
    twice in a row even if the upstream replays.
  - Batched commits: we accumulate up to BATCH_SIZE messages or BATCH_SECONDS
    of wall time before committing, drastically reducing transaction overhead
    on the database. Important when the firehose hits ~100 msg/sec.
  - Watchlist matching: each new vessel is checked against the watchlist table
    and the matched_mmsi column is back-filled if a name matches.

Run it with:
    python fetcher.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from collections import deque
from contextlib import suppress
from datetime import datetime, timezone

import websockets
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app import create_app
from app.db import db
from app.models import Vessel, Position, WatchlistEntry, utcnow

# --- Configuration ---------------------------------------------------------
load_dotenv()

API_KEY = os.environ.get("AISSTREAM_API_KEY")
BBOX_RAW = os.environ.get("AIS_BOUNDING_BOX", "30.0,-6.0,46.0,36.0")
WS_URL = "wss://stream.aisstream.io/v0/stream"

BATCH_SIZE = 100         # Commit after this many messages...
BATCH_SECONDS = 5.0      # ...or after this many seconds, whichever comes first.
RECONNECT_BASE = 2.0     # Seconds; doubles per retry up to RECONNECT_MAX.
RECONNECT_MAX = 60.0
DEDUP_WINDOW = 5000      # Last N (mmsi, timestamp) tuples to remember.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("neptune.fetcher")


# --- Helpers ---------------------------------------------------------------
def parse_bbox(raw: str) -> list[list[float]]:
    """AISStream wants a list of [[lat_min, lon_min], [lat_max, lon_max]] pairs."""
    parts = [float(p.strip()) for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError(f"AIS_BOUNDING_BOX must have 4 numbers, got: {raw!r}")
    lat_min, lon_min, lat_max, lon_max = parts
    return [[[lat_min, lon_min], [lat_max, lon_max]]]


def upsert_vessel(session, mmsi: int, fields: dict) -> None:
    """Insert-or-update a vessel row.

    SQLAlchemy 2.x's dialect-specific INSERT ... ON CONFLICT is the only way to
    do this atomically without a SELECT-then-UPDATE round-trip. We pick the
    right dialect at runtime so the same fetcher works against SQLite locally
    and Postgres in production.
    """
    bind = session.get_bind()
    dialect = bind.dialect.name

    base = {"mmsi": mmsi, **fields}

    if dialect == "postgresql":
        stmt = pg_insert(Vessel).values(**base)
        # Update only the columns we actually have new data for.
        update_cols = {k: stmt.excluded[k] for k in fields if fields[k] is not None}
        update_cols["last_seen"] = stmt.excluded["last_seen"]
        stmt = stmt.on_conflict_do_update(index_elements=["mmsi"], set_=update_cols)
    elif dialect == "sqlite":
        stmt = sqlite_insert(Vessel).values(**base)
        update_cols = {k: stmt.excluded[k] for k in fields if fields[k] is not None}
        update_cols["last_seen"] = stmt.excluded["last_seen"]
        stmt = stmt.on_conflict_do_update(index_elements=["mmsi"], set_=update_cols)
    else:
        # Fallback for other dialects: SELECT-then-UPDATE/INSERT.
        existing = session.get(Vessel, mmsi)
        if existing:
            for k, v in fields.items():
                if v is not None:
                    setattr(existing, k, v)
        else:
            session.add(Vessel(**base))
        return

    session.execute(stmt)


def match_watchlist(session, vessel: dict) -> None:
    """If this vessel matches an unmatched watchlist entry, back-fill it."""
    name = vessel.get("name")
    mmsi = vessel["mmsi"]
    if not name:
        return

    entry = session.execute(
        select(WatchlistEntry)
        .where(WatchlistEntry.matched_mmsi.is_(None))
        .where(WatchlistEntry.query.ilike(name))
        .limit(1)
    ).scalar_one_or_none()
    if entry:
        entry.matched_mmsi = mmsi
        log.info(f"Watchlist match: '{entry.query}' → MMSI {mmsi}")


# --- Message processing ----------------------------------------------------
def extract_position(msg: dict) -> dict | None:
    """Pull the fields we care about out of an AISStream PositionReport message.

    AISStream wraps the raw AIS payload in a Message envelope. The shape we
    care about looks like:

        {
          "MetaData": {
            "MMSI": 123456789, "ShipName": "EVER GIVEN ", "time_utc": "2024-..."
          },
          "Message": {
            "PositionReport": {
              "Latitude": 31.5, "Longitude": 32.5, "Sog": 12.4, "Cog": 87.0,
              "TrueHeading": 88, "NavigationalStatus": 0
            }
          }
        }
    """
    meta = msg.get("MetaData") or {}
    inner = (msg.get("Message") or {}).get("PositionReport") or {}
    if not inner:
        return None

    mmsi = meta.get("MMSI")
    if not mmsi:
        return None

    lat = inner.get("Latitude")
    lon = inner.get("Longitude")
    if lat is None or lon is None:
        return None
    # AIS sometimes reports 91/181 to mean "not available"
    if abs(lat) > 90 or abs(lon) > 180:
        return None

    ts_raw = meta.get("time_utc")
    ts = utcnow()
    if ts_raw:
        with suppress(Exception):
            # AISStream sends "2024-01-15 12:34:56.789012345 +0000 UTC" — slice off the nanos
            cleaned = ts_raw.replace(" UTC", "").rsplit(" ", 1)[0]
            ts = datetime.fromisoformat(cleaned).replace(tzinfo=timezone.utc)

    return {
        "mmsi": int(mmsi),
        "name": (meta.get("ShipName") or "").strip() or None,
        "timestamp": ts,
        "latitude": float(lat),
        "longitude": float(lon),
        "sog": _safe_float(inner.get("Sog")),
        "cog": _safe_float(inner.get("Cog")),
        "heading": _safe_int(inner.get("TrueHeading")),
        "nav_status": _safe_int(inner.get("NavigationalStatus")),
    }


def extract_static_data(msg: dict) -> dict | None:
    """Pull metadata from a ShipStaticData message — gives us IMO, dimensions, etc."""
    meta = msg.get("MetaData") or {}
    inner = (msg.get("Message") or {}).get("ShipStaticData") or {}
    if not inner:
        return None

    mmsi = meta.get("MMSI")
    if not mmsi:
        return None

    dims = inner.get("Dimension") or {}
    length = None
    beam = None
    if dims.get("A") is not None and dims.get("B") is not None:
        length = float(dims["A"]) + float(dims["B"])
    if dims.get("C") is not None and dims.get("D") is not None:
        beam = float(dims["C"]) + float(dims["D"])

    return {
        "mmsi": int(mmsi),
        "name": (inner.get("Name") or meta.get("ShipName") or "").strip() or None,
        "imo": _safe_int(inner.get("ImoNumber")),
        "call_sign": (inner.get("CallSign") or "").strip() or None,
        "ship_type": _safe_int(inner.get("Type")),
        "length_m": length,
        "beam_m": beam,
    }


def _safe_float(x):
    try: return float(x) if x is not None else None
    except (TypeError, ValueError): return None


def _safe_int(x):
    try: return int(x) if x is not None else None
    except (TypeError, ValueError): return None


# --- Main loop -------------------------------------------------------------
class Fetcher:
    def __init__(self, app):
        self.app = app
        self.recent = deque(maxlen=DEDUP_WINDOW)
        self.recent_set: set[tuple[int, str]] = set()
        self.shutdown = asyncio.Event()

    def seen_recently(self, mmsi: int, ts: datetime) -> bool:
        key = (mmsi, ts.isoformat())
        if key in self.recent_set:
            return True
        self.recent.append(key)
        self.recent_set.add(key)
        # Trim the set to match the deque (deque drops from the left when full)
        if len(self.recent_set) > DEDUP_WINDOW:
            # Cheaper than rebuilding: drop ~10% oldest
            drop = max(1, len(self.recent_set) - DEDUP_WINDOW)
            for _ in range(drop):
                old = self.recent.popleft()
                self.recent_set.discard(old)
        return False

    async def run(self) -> None:
        if not API_KEY or API_KEY == "your_aisstream_api_key_here":
            log.error("AISSTREAM_API_KEY not set. Get a free key at https://aisstream.io")
            sys.exit(1)

        bbox = parse_bbox(BBOX_RAW)
        log.info(f"Bounding box: {bbox}")

        delay = RECONNECT_BASE
        while not self.shutdown.is_set():
            try:
                await self._connect_and_consume(bbox)
                delay = RECONNECT_BASE  # successful run resets backoff
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning(f"Connection error: {e!r}. Reconnecting in {delay:.0f}s.")
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.shutdown.wait(), timeout=delay)
                delay = min(delay * 2, RECONNECT_MAX)

    async def _connect_and_consume(self, bbox) -> None:
        async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
            sub = {
                "APIKey": API_KEY,
                "BoundingBoxes": bbox,
                "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
            }
            await ws.send(json.dumps(sub))
            log.info("Subscribed to AISStream feed.")

            buffer: list[dict] = []
            last_flush = asyncio.get_event_loop().time()

            while not self.shutdown.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=BATCH_SECONDS)
                    buffer.append(json.loads(raw))
                except asyncio.TimeoutError:
                    pass  # fall through to flush

                now = asyncio.get_event_loop().time()
                if buffer and (len(buffer) >= BATCH_SIZE or now - last_flush >= BATCH_SECONDS):
                    self._flush(buffer)
                    buffer.clear()
                    last_flush = now

    def _flush(self, messages: list[dict]) -> None:
        positions_added = 0
        vessels_touched = 0

        with self.app.app_context():
            session = db.session
            for msg in messages:
                msg_type = msg.get("MessageType")

                if msg_type == "PositionReport":
                    parsed = extract_position(msg)
                    if not parsed:
                        continue
                    if self.seen_recently(parsed["mmsi"], parsed["timestamp"]):
                        continue

                    upsert_vessel(session, parsed["mmsi"], {
                        "name": parsed["name"],
                        "last_seen": parsed["timestamp"],
                    })
                    session.add(Position(
                        vessel_mmsi=parsed["mmsi"],
                        timestamp=parsed["timestamp"],
                        latitude=parsed["latitude"],
                        longitude=parsed["longitude"],
                        sog_knots=parsed["sog"],
                        cog_degrees=parsed["cog"],
                        heading_degrees=parsed["heading"],
                        nav_status=parsed["nav_status"],
                    ))
                    positions_added += 1
                    vessels_touched += 1

                elif msg_type == "ShipStaticData":
                    parsed = extract_static_data(msg)
                    if not parsed:
                        continue
                    upsert_vessel(session, parsed["mmsi"], {
                        "name": parsed["name"],
                        "imo": parsed["imo"],
                        "call_sign": parsed["call_sign"],
                        "ship_type": parsed["ship_type"],
                        "length_m": parsed["length_m"],
                        "beam_m": parsed["beam_m"],
                        "last_seen": utcnow(),
                    })
                    match_watchlist(session, parsed)
                    vessels_touched += 1

            try:
                session.commit()
            except Exception as e:
                session.rollback()
                log.error(f"Commit failed: {e}")
                return

        log.info(f"Flushed: {positions_added} positions, {vessels_touched} vessels touched.")

    def stop(self, *_) -> None:
        log.info("Shutdown requested.")
        self.shutdown.set()


async def main():
    app = create_app()
    fetcher = Fetcher(app)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):  # Windows doesn't support add_signal_handler
            loop.add_signal_handler(sig, fetcher.stop)

    await fetcher.run()
    log.info("Fetcher stopped.")


if __name__ == "__main__":
    asyncio.run(main())
