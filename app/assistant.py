from __future__ import annotations

import re
from datetime import timedelta
from sqlalchemy import select, func, or_

from app.db import db
from app.models import Vessel, Position, Port, WatchlistEntry, utcnow


GREETINGS = ("hi", "hello", "hey", "hola", "buenos", "good morning", "good afternoon")
THANKS = ("thanks", "thank you", "gracias", "cheers", "ty")
HELP_HINTS = ("help", "what can you do", "commands", "options")


def respond(prompt: str) -> str:
    p = (prompt or "").strip()
    if not p:
        return "Try asking me something — for example: 'how many tankers are there?', 'where is MAERSK SENTOSA?', or 'what's anchored at Algeciras?'"

    q = p.lower()

    if any(q.startswith(g) for g in GREETINGS):
        return _greeting()
    if any(t in q for t in THANKS):
        return "You're welcome. Anything else?"
    if any(h in q for h in HELP_HINTS):
        return _help_text()

    if re.search(r"how many vessels|total vessels|fleet size|how many ships", q):
        return _count_vessels()
    if re.search(r"how many tankers", q):
        return _count_by_type(80, 89, "tankers")
    if re.search(r"how many cargo|how many container", q):
        return _count_by_type(70, 79, "cargo vessels")
    if re.search(r"how many passenger|how many ferries", q):
        return _count_by_type(60, 69, "passenger vessels")
    if re.search(r"how many anchored|at anchor|anchoring", q):
        return _count_by_status(1, "at anchor")
    if re.search(r"how many moored|alongside", q):
        return _count_by_status(5, "moored")
    if re.search(r"how many under way|underway|moving|sailing", q):
        return _count_by_status(0, "under way")

    m = re.search(r"(?:where is|locate|find|position of|track) ([a-z0-9 \-]+)", q)
    if m:
        return _locate_vessel(m.group(1).strip())

    m = re.search(r"(?:what(?:'s| is) at|whats at|what is in|vessels at|ships at|in port of) ([a-z ]+)", q)
    if m:
        return _at_port(m.group(1).strip())

    if re.search(r"fastest|highest speed|quickest", q):
        return _fastest()
    if re.search(r"largest|biggest", q):
        return _largest()
    if re.search(r"watchlist|tracked|tracking", q):
        return _watchlist_summary()
    if re.search(r"recent|latest|newest|just arrived", q):
        return _recent_activity()

    if re.search(r"^\d{9}$", p):
        return _locate_by_mmsi(int(p))

    return _fallback(p)


def _greeting() -> str:
    return ("Hello — I'm Neptune's maritime ops assistant. I can answer questions "
            "about the live fleet, port activity, and individual vessels. "
            "Ask me 'help' for examples.")


def _help_text() -> str:
    return ("Here's what I can do:\n\n"
            "• Fleet stats — 'how many vessels?', 'how many tankers?', 'how many at anchor?'\n"
            "• Vessel lookup — 'where is MSC OSCAR?', 'locate STELLA', or paste a 9-digit MMSI\n"
            "• Port activity — 'what's at Algeciras?', 'ships at Piraeus'\n"
            "• Rankings — 'fastest vessel', 'largest ship'\n"
            "• Recent — 'latest activity', 'recent arrivals'")


def _count_vessels() -> str:
    n = db.session.execute(select(func.count(Vessel.mmsi))).scalar_one()
    cutoff = utcnow() - timedelta(hours=1)
    active = db.session.execute(
        select(func.count(Vessel.mmsi)).where(Vessel.last_seen >= cutoff)
    ).scalar_one()
    return f"Currently tracking {n} vessels. {active} have reported a position in the last hour."


def _count_by_type(low: int, high: int, label: str) -> str:
    n = db.session.execute(
        select(func.count(Vessel.mmsi))
        .where(Vessel.ship_type.between(low, high))
    ).scalar_one()
    if n == 0:
        return f"No {label} in the fleet right now."
    if n == 1:
        singular = label.rstrip("s")
        return f"There is 1 {singular} in the tracked fleet."
    return f"There are {n} {label} in the tracked fleet."


def _count_by_status(status: int, label: str) -> str:
    sub = (
        select(Position.vessel_mmsi, func.max(Position.timestamp).label("ts"))
        .group_by(Position.vessel_mmsi)
        .subquery()
    )
    stmt = (
        select(func.count(Position.id))
        .join(sub, (Position.vessel_mmsi == sub.c.vessel_mmsi) & (Position.timestamp == sub.c.ts))
        .where(Position.nav_status == status)
    )
    n = db.session.execute(stmt).scalar_one()
    if n == 0:
        return f"No vessels are currently {label}."
    return f"{n} vessel{'s are' if n != 1 else ' is'} currently {label}."


def _locate_vessel(name: str) -> str:
    if name.isdigit() and len(name) == 9:
        return _locate_by_mmsi(int(name))

    vessel = db.session.execute(
        select(Vessel).where(Vessel.name.ilike(f"%{name}%")).limit(1)
    ).scalar_one_or_none()
    if not vessel:
        return f"I couldn't find a vessel matching '{name}'. Try the exact name, or paste an MMSI."

    return _format_vessel_status(vessel)


def _locate_by_mmsi(mmsi: int) -> str:
    vessel = db.session.get(Vessel, mmsi)
    if not vessel:
        return f"No vessel with MMSI {mmsi} in the database."
    return _format_vessel_status(vessel)


def _format_vessel_status(vessel: Vessel) -> str:
    pos = db.session.execute(
        select(Position).where(Position.vessel_mmsi == vessel.mmsi)
        .order_by(Position.timestamp.desc()).limit(1)
    ).scalar_one_or_none()

    parts = [f"**{vessel.name or 'Unnamed'}** (MMSI {vessel.mmsi})"]
    parts.append(f"Type: {vessel.ship_type_label}" + (f" · Flag: {vessel.flag}" if vessel.flag else ""))

    if pos:
        parts.append(f"Position: {pos.latitude:.3f}°, {pos.longitude:.3f}°")
        if pos.sog_knots is not None:
            parts.append(f"Speed: {pos.sog_knots:.1f} kn · Course: {pos.cog_degrees:.0f}°"
                         if pos.cog_degrees is not None else f"Speed: {pos.sog_knots:.1f} kn")
        parts.append(f"Status: {pos.nav_status_label}")
        age = (utcnow() - pos.timestamp).total_seconds() / 60 if pos.timestamp.tzinfo else None
        if age is not None and age < 1440:
            parts.append(f"Last fix: {int(age)} min ago")
    else:
        parts.append("No position reports on file.")

    return "\n".join(parts)


def _at_port(port_name: str) -> str:
    port = db.session.execute(
        select(Port).where(Port.name.ilike(f"%{port_name}%")).limit(1)
    ).scalar_one_or_none()
    if not port:
        return (f"I don't have a port called '{port_name}' in my database. "
                "Known ports include Algeciras, Piraeus, Valencia, Genoa, Barcelona, Marseille, Naples.")

    sub = (
        select(Position.vessel_mmsi, func.max(Position.timestamp).label("ts"))
        .group_by(Position.vessel_mmsi)
        .subquery()
    )
    radius_deg = port.radius_km / 111.0
    stmt = (
        select(Vessel, Position)
        .join(Position, Position.vessel_mmsi == Vessel.mmsi)
        .join(sub, (Position.vessel_mmsi == sub.c.vessel_mmsi) & (Position.timestamp == sub.c.ts))
        .where(func.abs(Position.latitude - port.latitude) < radius_deg)
        .where(func.abs(Position.longitude - port.longitude) < radius_deg)
        .limit(20)
    )
    rows = db.session.execute(stmt).all()

    if not rows:
        return f"No vessels currently within {port.radius_km:.0f} km of {port.name}."

    lines = [f"**{port.name}** ({port.country}) — {len(rows)} vessel{'s' if len(rows) != 1 else ''} in range:"]
    for vessel, pos in rows[:10]:
        status = pos.nav_status_label
        lines.append(f"• {vessel.name or vessel.mmsi} ({vessel.ship_type_label}) — {status}")
    if len(rows) > 10:
        lines.append(f"…and {len(rows) - 10} more.")
    return "\n".join(lines)


def _fastest() -> str:
    sub = (
        select(Position.vessel_mmsi, func.max(Position.timestamp).label("ts"))
        .group_by(Position.vessel_mmsi)
        .subquery()
    )
    stmt = (
        select(Vessel, Position)
        .join(Position, Position.vessel_mmsi == Vessel.mmsi)
        .join(sub, (Position.vessel_mmsi == sub.c.vessel_mmsi) & (Position.timestamp == sub.c.ts))
        .where(Position.sog_knots.isnot(None))
        .order_by(Position.sog_knots.desc())
        .limit(5)
    )
    rows = db.session.execute(stmt).all()
    if not rows:
        return "No speed data available."
    lines = ["Fastest vessels right now:"]
    for v, p in rows:
        lines.append(f"• {v.name or v.mmsi} — {p.sog_knots:.1f} kn ({v.ship_type_label})")
    return "\n".join(lines)


def _largest() -> str:
    rows = db.session.execute(
        select(Vessel).where(Vessel.length_m.isnot(None))
        .order_by(Vessel.length_m.desc()).limit(5)
    ).scalars().all()
    if not rows:
        return "No size data available."
    lines = ["Largest vessels in the fleet:"]
    for v in rows:
        lines.append(f"• {v.name or v.mmsi} — {v.length_m:.0f} m × {v.beam_m:.0f} m ({v.ship_type_label})")
    return "\n".join(lines)


def _watchlist_summary() -> str:
    total = db.session.execute(select(func.count(WatchlistEntry.id))).scalar_one()
    matched = db.session.execute(
        select(func.count(WatchlistEntry.id)).where(WatchlistEntry.matched_mmsi.isnot(None))
    ).scalar_one()
    if total == 0:
        return "The watchlist is empty. Add vessels via the Watchlist page."
    return f"{total} vessel{'s' if total != 1 else ''} on the watchlist — {matched} actively tracked, {total - matched} awaiting first signal."


def _recent_activity() -> str:
    cutoff = utcnow() - timedelta(hours=1)
    rows = db.session.execute(
        select(Vessel).where(Vessel.last_seen >= cutoff)
        .order_by(Vessel.last_seen.desc()).limit(5)
    ).scalars().all()
    if not rows:
        return "No activity in the last hour."
    lines = ["Most recent activity:"]
    for v in rows:
        age_min = int((utcnow() - v.last_seen).total_seconds() / 60) if v.last_seen.tzinfo else 0
        lines.append(f"• {v.name or v.mmsi} ({v.ship_type_label}) — {age_min} min ago")
    return "\n".join(lines)


def _fallback(prompt: str) -> str:
    return (f"I'm not sure how to answer that. I work best with specific questions about "
            f"the fleet, vessels, or ports. Try 'help' to see what I can do.")
