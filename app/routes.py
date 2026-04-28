import secrets
from datetime import timedelta
from collections import Counter, defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, session
from sqlalchemy import select, func, or_

from app.db import db
from app.models import Vessel, Position, Port, WatchlistEntry, ChatMessage, utcnow
from app import assistant

bp = Blueprint("main", __name__)


def _stats():
    total_vessels = db.session.execute(select(func.count(Vessel.mmsi))).scalar_one()
    total_positions = db.session.execute(select(func.count(Position.id))).scalar_one()
    watchlist_count = db.session.execute(select(func.count(WatchlistEntry.id))).scalar_one()
    cutoff = utcnow() - timedelta(hours=1)
    active = db.session.execute(
        select(func.count(Vessel.mmsi)).where(Vessel.last_seen >= cutoff)
    ).scalar_one()
    return {
        "vessels": total_vessels,
        "positions": total_positions,
        "watchlist": watchlist_count,
        "active": active,
    }


def _latest_position_for_each_vessel():
    sub = (
        select(Position.vessel_mmsi, func.max(Position.timestamp).label("ts"))
        .group_by(Position.vessel_mmsi)
        .subquery()
    )
    stmt = (
        select(Vessel, Position)
        .join(Position, Position.vessel_mmsi == Vessel.mmsi)
        .join(sub, (Position.vessel_mmsi == sub.c.vessel_mmsi) & (Position.timestamp == sub.c.ts))
    )
    return db.session.execute(stmt).all()


@bp.route("/")
def landing():
    return render_template("landing.html", stats=_stats())


@bp.route("/dashboard")
def dashboard():
    cutoff = utcnow() - timedelta(hours=24)
    stmt = (
        select(Vessel)
        .where(Vessel.last_seen >= cutoff)
        .order_by(Vessel.last_seen.desc())
        .limit(50)
    )
    recent = db.session.execute(stmt).scalars().all()
    return render_template("dashboard.html", vessels=recent, stats=_stats())


@bp.route("/map")
def fleet_map():
    return render_template("map.html", stats=_stats())


@bp.route("/api/fleet")
def fleet_json():
    rows = _latest_position_for_each_vessel()
    return jsonify([
        {
            "mmsi": v.mmsi,
            "name": v.name or f"MMSI {v.mmsi}",
            "type": v.ship_type_label,
            "color": v.ship_type_color,
            "flag": v.flag,
            "lat": p.latitude,
            "lon": p.longitude,
            "sog": p.sog_knots,
            "cog": p.cog_degrees,
            "status": p.nav_status_label,
        }
        for v, p in rows
    ])


@bp.route("/ports")
def ports():
    ports_list = db.session.execute(select(Port).order_by(Port.name)).scalars().all()

    rows = _latest_position_for_each_vessel()
    by_port = defaultdict(list)
    unmatched = []

    for v, p in rows:
        matched = False
        for port in ports_list:
            radius_deg = port.radius_km / 111.0
            if abs(p.latitude - port.latitude) < radius_deg and abs(p.longitude - port.longitude) < radius_deg:
                by_port[port.id].append((v, p))
                matched = True
                break
        if not matched:
            unmatched.append((v, p))

    return render_template(
        "ports.html",
        ports=ports_list,
        by_port=by_port,
        at_sea=unmatched,
        stats=_stats(),
    )


@bp.route("/fleet")
def fleet_analytics():
    vessels = db.session.execute(select(Vessel)).scalars().all()

    type_counts = Counter(v.ship_type_label for v in vessels)
    flag_counts = Counter(v.flag or "Unknown" for v in vessels)

    rows = _latest_position_for_each_vessel()
    status_counts = Counter(p.nav_status_label for v, p in rows)

    type_data = sorted(type_counts.items(), key=lambda x: -x[1])
    flag_data = sorted(flag_counts.items(), key=lambda x: -x[1])[:10]
    status_data = sorted(status_counts.items(), key=lambda x: -x[1])

    avg_length = (
        sum(v.length_m for v in vessels if v.length_m) /
        max(1, sum(1 for v in vessels if v.length_m))
    )
    total_length = sum(v.length_m for v in vessels if v.length_m)
    avg_speed_rows = [p.sog_knots for v, p in rows if p.sog_knots is not None and p.sog_knots > 0.5]
    avg_speed = sum(avg_speed_rows) / max(1, len(avg_speed_rows))

    return render_template(
        "fleet.html",
        type_data=type_data,
        flag_data=flag_data,
        status_data=status_data,
        avg_length=avg_length,
        total_length=total_length,
        avg_speed=avg_speed,
        active_count=len(rows),
        stats=_stats(),
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
    return render_template("search.html", q=q, results=results, stats=_stats())


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
    latest = positions[0] if positions else None
    return render_template(
        "vessel.html",
        vessel=vessel,
        positions=positions,
        latest=latest,
        stats=_stats(),
    )


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
    return render_template("track.html", entries=entries, stats=_stats())


@bp.route("/assistant")
def assistant_page():
    if "chat_session" not in session:
        session["chat_session"] = secrets.token_hex(8)
    sid = session["chat_session"]

    history = db.session.execute(
        select(ChatMessage).where(ChatMessage.session_id == sid)
        .order_by(ChatMessage.created_at.asc()).limit(50)
    ).scalars().all()

    return render_template("assistant.html", history=history, stats=_stats())


@bp.route("/assistant/send", methods=["POST"])
def assistant_send():
    if "chat_session" not in session:
        session["chat_session"] = secrets.token_hex(8)
    sid = session["chat_session"]

    data = request.get_json(silent=True) or {}
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return jsonify({"error": "empty"}), 400
    if len(user_text) > 500:
        return jsonify({"error": "too long"}), 400

    db.session.add(ChatMessage(session_id=sid, role="user", content=user_text))
    db.session.commit()

    reply = assistant.respond(user_text)

    db.session.add(ChatMessage(session_id=sid, role="assistant", content=reply))
    db.session.commit()

    return jsonify({"reply": reply})


@bp.route("/assistant/clear", methods=["POST"])
def assistant_clear():
    sid = session.get("chat_session")
    if sid:
        db.session.execute(
            ChatMessage.__table__.delete().where(ChatMessage.session_id == sid)
        )
        db.session.commit()
    return redirect(url_for("main.assistant_page"))


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


@bp.route("/api/stats")
def stats_json():
    return jsonify(_stats())


@bp.route("/health")
def health():
    try:
        db.session.execute(select(1))
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500
