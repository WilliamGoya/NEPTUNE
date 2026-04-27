# Neptune — Maritime Logistics Platform

Real-time vessel tracking and port coordination MVP.

A Flask web application that ingests live AIS (Automatic Identification System) data
from the global maritime network and presents it through a web dashboard. Users can
browse tracked vessels, search by name or IMO number, view position history, and
add vessels to the watchlist.

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  AISStream.io   │ ───WS──►│  fetcher.py      │
│  (live AIS)     │         │  (data ingester) │
└─────────────────┘         └────────┬─────────┘
                                     │ SQLAlchemy
                                     ▼
                            ┌──────────────────┐
                            │  PostgreSQL /    │
                            │  SQLite          │
                            └────────┬─────────┘
                                     │
                            ┌────────▼─────────┐
                            │  Flask web app   │
                            │  (app/__init__)  │
                            └────────┬─────────┘
                                     │ HTTPS
                                     ▼
                                  Browser
```

**Two processes, one database.** The web app and the AIS fetcher run independently
and communicate only through the database. This is the standard pattern for
ingestion-plus-presentation systems and means either side can be restarted without
disturbing the other.

## Tech stack

- **Flask 3** — web framework
- **SQLAlchemy 2** — ORM
- **Alembic** — schema migrations
- **psycopg2-binary** — Postgres driver
- **websockets** — async client for AISStream
- **gunicorn** — production WSGI server
- **Jinja2** — templating (bundled with Flask)

## Local setup

```bash
# 1. Clone and enter the repo
cd neptune

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the env template and fill in values
cp .env.example .env
# Edit .env: set AISSTREAM_API_KEY (free at https://aisstream.io)

# 5. Initialize the database
flask --app app db upgrade

# 6. Seed the watchlist with a few demo vessels (optional)
python scripts/seed.py

# 7. In one terminal, run the AIS fetcher
python fetcher.py

# 8. In another terminal, run the web app
flask --app app run --debug
```

Open http://localhost:5000.

## Database schema

Three tables. The schema is defined in `app/models.py` and managed via Alembic
migrations under `migrations/versions/`.

**`vessels`** — one row per ship. Natural key is the MMSI (Maritime Mobile Service
Identity, a 9-digit number assigned by the vessel's flag state). IMO number is also
captured when available — IMO is more stable across ownership changes but isn't
broadcast in every AIS message.

**`positions`** — append-only time-series of position reports. Indexed on
`(vessel_mmsi, timestamp DESC)` so the "latest position per vessel" query is a
fast index scan rather than a sort. In production you'd partition this by month;
for the MVP the index is enough.

**`watchlist`** — user-submitted vessel names that the fetcher prioritizes. This
is what the `/track` form writes to.

## Deployment to Render

1. Push this repo to GitHub.
2. On Render, create a new **Web Service** pointing at your repo.
3. Build command: `pip install -r requirements.txt && flask --app app db upgrade`
4. Start command: `gunicorn 'app:create_app()'`
5. Add a **PostgreSQL** instance and copy its `DATABASE_URL` into the web service's
   environment variables.
6. Add `AISSTREAM_API_KEY` and `SECRET_KEY` to the web service env vars.
7. Create a separate **Background Worker** on Render with start command
   `python fetcher.py`, sharing the same `DATABASE_URL` and `AISSTREAM_API_KEY`.

The web service and the worker scale independently. The worker is what keeps the
database fresh; the web service is stateless and can be redeployed without data loss.

## File layout

```
neptune/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # SQLAlchemy models
│   ├── routes.py            # HTTP routes
│   ├── db.py                # DB session helper
│   ├── templates/           # Jinja templates
│   └── static/              # CSS
├── migrations/              # Alembic migrations
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
├── scripts/
│   └── seed.py              # Demo data loader
├── fetcher.py               # AIS ingestion process
├── requirements.txt
├── render.yaml              # Render blueprint
├── Procfile                 # Process definitions
├── .env.example
└── README.md
```
