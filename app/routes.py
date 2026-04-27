from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from sqlalchemy import select, func

from app.db import db
from app.models import Vessel, Position, WatchlistEntry, utcnow

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    cutoff = utcnow() - timedelta(hours=24)
    stmt = (
        select(Vessel)
        .where(Vessel.last_seen >= cutoff)
        .order_by(Vessel.last_seen.desc())
        .limit(50)
    )
    recent = db.session.execute(stmt).scalars().all()

    total_vessels = db.session.execute(select(func.count(Vessel.mmsi))).scalar_one()
    total_positions = db.session.execute(select(func.count(Position.id))).scalar_one()
    watchlist_count = db.session.execute(select(func.count(WatchlistEntry.id))).scalar_one()

    return render_template(
        "index.html",
        vessels=recent,
        stats={
            "vessels": total_vessels,
            "positions": total_positions,
            "watchlist": watchlist_count,
        },
    )


@bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        if q.isdigit() and len(q) == 9:
            stmt = select(Vessel).where(Vessel.mmsi == int(q))
        else:
            stmt = (
                select(Vessel)
                .where(Vessel.name.ilike(f"%{q}%"))
                .order_by(Vessel.last_seen.desc())
                .limit(50)
            )
        results = db.session.execute(stmt).scalars().all()
    return render_template("search.html", q=q, results=results)


@bp.route("/vessel/<int:mmsi>")
def vessel_detail(mmsi: int):
    vessel = db.session.get(Vessel, mmsi)
    if vessel is None:
        abort(404)

    stmt = (
        select(Position)
        .where(Position.vessel_mmsi == mmsi)
        .order_by(Position.timestamp.desc())
        .limit(50)
    )
    positions = db.session.execute(stmt).scalars().all()
    return render_template("vessel.html", vessel=vessel, positions=positions)


@bp.route("/track", methods=["GET", "POST"])
def track():
    if request.method == "POST":
        query = (request.form.get("query") or "").strip()
        if not query:
            flash("Please enter a vessel name or MMSI.", "error")
            return redirect(url_for("main.track"))
        if len(query) > 120:
            flash("That's too long — max 120 characters.", "error")
            return redirect(url_for("main.track"))

        existing = db.session.execute(
            select(WatchlistEntry).where(WatchlistEntry.query == query)
        ).scalar_one_or_none()

        if existing:
            flash(f"'{query}' is already on the watchlist.", "info")
        else:
            matched_mmsi = None
            if query.isdigit() and len(query) == 9:
                v = db.session.get(Vessel, int(query))
                if v: matched_mmsi = v.mmsi
            else:
                v = db.session.execute(
                    select(Vessel).where(Vessel.name.ilike(query)).limit(1)
                ).scalar_one_or_none()
                if v: matched_mmsi = v.mmsi

            entry = WatchlistEntry(
                query=query,
                submitted_by_ip=request.remote_addr,
                matched_mmsi=matched_mmsi,
            )
            db.session.add(entry)
            db.session.commit()
            if matched_mmsi:
                flash(f"Added '{query}' — already tracking (MMSI {matched_mmsi}).", "success")
            else:
                flash(f"Added '{query}' — we'll track it next time it appears on AIS.", "success")
        return redirect(url_for("main.track"))

    entries = db.session.execute(
        select(WatchlistEntry).order_by(WatchlistEntry.submitted_at.desc()).limit(100)
    ).scalars().all()
    return render_template("track.html", entries=entries)


@bp.route("/api/positions/<int:mmsi>")
def positions_json(mmsi: int):
    stmt = (
        select(Position)
        .where(Position.vessel_mmsi == mmsi)
        .order_by(Position.timestamp.desc())
        .limit(200)
    )
    rows = db.session.execute(stmt).scalars().all()
    return jsonify([
        {
            "lat": p.latitude,
            "lon": p.longitude,
            "sog": p.sog_knots,
            "cog": p.cog_degrees,
            "ts": p.timestamp.isoformat() if p.timestamp else None,
        }
        for p in rows
    ])


@bp.route("/health")
def health():
    try:
        db.session.execute(select(1))
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500
