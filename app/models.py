from datetime import datetime, timezone
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vessel(db.Model):
    __tablename__ = "vessels"

    mmsi: Mapped[int] = mapped_column(primary_key=True)
    imo: Mapped[int | None] = mapped_column(index=True)
    name: Mapped[str | None] = mapped_column(db.String(120), index=True)
    call_sign: Mapped[str | None] = mapped_column(db.String(20))
    ship_type: Mapped[int | None]
    flag: Mapped[str | None] = mapped_column(db.String(3))
    length_m: Mapped[float | None]
    beam_m: Mapped[float | None]
    first_seen: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    positions = relationship(
        "Position", back_populates="vessel",
        cascade="all, delete-orphan", lazy="dynamic",
    )

    @property
    def ship_type_label(self) -> str:
        t = self.ship_type or 0
        if 70 <= t <= 79: return "Cargo"
        if 80 <= t <= 89: return "Tanker"
        if 60 <= t <= 69: return "Passenger"
        if 30 <= t <= 39: return "Fishing / Special"
        if 40 <= t <= 49: return "High-speed craft"
        if 50 <= t <= 59: return "Service"
        return "Other"

    def __repr__(self) -> str:
        return f"<Vessel {self.mmsi} {self.name or '(unnamed)'}>"


class Position(db.Model):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vessel_mmsi: Mapped[int] = mapped_column(
        db.ForeignKey("vessels.mmsi", ondelete="CASCADE"), nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    sog_knots: Mapped[float | None]
    cog_degrees: Mapped[float | None]
    heading_degrees: Mapped[float | None]
    nav_status: Mapped[int | None]

    vessel = relationship("Vessel", back_populates="positions")

    __table_args__ = (
        Index("ix_positions_mmsi_ts_desc", "vessel_mmsi", "timestamp"),
    )


class WatchlistEntry(db.Model):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(db.String(120), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(default=utcnow)
    submitted_by_ip: Mapped[str | None] = mapped_column(db.String(45))
    matched_mmsi: Mapped[int | None] = mapped_column(
        db.ForeignKey("vessels.mmsi", ondelete="SET NULL"),
    )

    __table_args__ = (
        UniqueConstraint("query", name="uq_watchlist_query"),
    )
