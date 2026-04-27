import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import db
from app.models import Vessel, Position, utcnow


DEMO_VESSELS = [
    (255805953, 9811000, "MAERSK SENTOSA",  70, "PRT", 399.0, 59.0),
    (538008149, 9525338, "MSC OSCAR",       70, "MHL", 395.0, 59.0),
    (235103368, 9811049, "EVER ACE",        70, "GBR", 400.0, 62.0),
    (244730000, 9314226, "STELLA",          80, "NLD", 183.0, 32.0),
    (215280000, 9456307, "BLUE STAR DELOS", 60, "MLT", 145.0, 24.0),
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
                mmsi=mmsi,
                imo=imo,
                name=name,
                ship_type=ship_type,
                flag=flag,
                length_m=length,
                beam_m=beam,
                first_seen=now - timedelta(days=30),
                last_seen=now - timedelta(minutes=5),
            )
            db.session.add(v)
            db.session.add(Position(
                vessel_mmsi=mmsi,
                timestamp=now - timedelta(minutes=5),
                latitude=36.0 + (mmsi % 100) / 100,
                longitude=-5.0 + (mmsi % 200) / 100,
                sog_knots=12.5,
                cog_degrees=87.0,
                heading_degrees=88,
                nav_status=0,
            ))
            added += 1

        db.session.commit()
        print(f"Seeded {added} vessels (skipped {len(DEMO_VESSELS) - added} existing).")


if __name__ == "__main__":
    main()
