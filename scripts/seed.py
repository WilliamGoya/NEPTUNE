import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import db
from app.models import Vessel, Position, Port, utcnow


DEMO_VESSELS = [
    (255805953, 9811000, "MAERSK SENTOSA",  70, "PRT", 399.0, 59.0),
    (538008149, 9525338, "MSC OSCAR",       70, "MHL", 395.0, 59.0),
    (235103368, 9811049, "EVER ACE",        70, "GBR", 400.0, 62.0),
    (244730000, 9314226, "STELLA",          80, "NLD", 183.0, 32.0),
    (215280000, 9456307, "BLUE STAR DELOS", 60, "MLT", 145.0, 24.0),
]

DEMO_PORTS = [
    ("Algeciras", "ESP", 36.13, -5.45, 20.0),
    ("Valencia",  "ESP", 39.45, -0.32, 18.0),
    ("Piraeus",   "GRC", 37.94, 23.65, 18.0),
    ("Tangier",   "MAR", 35.78, -5.78, 18.0),
]


def main():
    app = create_app()
    with app.app_context():
        added = 0
        for mmsi, imo, name, ship_type, flag, length, beam in DEMO_VESSELS:
            existing = db.session.get(Vessel, mmsi)
            if existing:
                continue

            now = utcnow()
            v = Vessel(
                mmsi=mmsi, imo=imo, name=name, ship_type=ship_type, flag=flag,
                length_m=length, beam_m=beam,
                first_seen=now - timedelta(days=30),
                last_seen=now - timedelta(minutes=5),
            )
            db.session.add(v)
            db.session.add(Position(
                vessel_mmsi=mmsi,
                timestamp=now - timedelta(minutes=5),
                latitude=36.0 + (mmsi % 100) / 100,
                longitude=-5.0 + (mmsi % 200) / 100,
                sog_knots=12.5, cog_degrees=87.0, heading_degrees=88, nav_status=0,
            ))
            added += 1

        for name, country, lat, lon, radius in DEMO_PORTS:
            existing = db.session.execute(
                db.select(Port).where(Port.name == name)
            ).scalar_one_or_none()
            if not existing:
                db.session.add(Port(name=name, country=country, latitude=lat, longitude=lon, radius_km=radius))

        db.session.commit()
        print(f"Seeded {added} vessels and {len(DEMO_PORTS)} ports.")


if __name__ == "__main__":
    main()
