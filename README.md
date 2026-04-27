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

## Quick start (Supabase + local Flask)

This is the fastest path: Supabase provides the Postgres database, Flask runs
locally for development, and you can deploy to Render later.

**1. Create a Supabase project** at https://supabase.com (free tier works fine).
Pick a region close to you. Wait ~2 minutes for it to provision.

**2. Load the schema and seed data.** In the Supabase dashboard, open
**SQL Editor → New query**, paste the contents of `scripts/supabase_seed.sql`,
and click **Run**. This creates all three tables, indexes, and inserts 20 real
vessels with ~80 position reports across the Mediterranean.

**3. Get your connection string.** In Supabase, go to **Project Settings →
Database → Connection string → URI**, switch the mode to **Session pooler**
(port 5432), and copy the URL. It looks like:
`postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-eu-west-3.pooler.supabase.com:5432/postgres`

**4. Set up the project locally.**

```bash
git clone <your-repo-url>
cd neptune

python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env:
#   DATABASE_URL=<the Supabase URL from step 3>
#   AISSTREAM_API_KEY=<get one free at https://aisstream.io>
#   SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
```

**5. Run the web app.**

```bash
flask --app app run --debug
```

Open http://localhost:5000 — you should see the dashboard populated with the
20 seeded vessels.

**6. (Optional) Run the AIS fetcher** in a separate terminal to ingest live
data on top of the seed:

```bash
python fetcher.py
```

## Alternative: pure local SQLite (no Supabase)

If you want to develop without any cloud dependencies:

```bash
cp .env.example .env
# Leave DATABASE_URL as the SQLite default

flask --app app db upgrade       # creates the schema
python scripts/seed.py           # adds 5 demo vessels (Python-based seed)
flask --app app run --debug
```

The Python seed (`scripts/seed.py`) is smaller than the SQL seed but works
on every database backend.

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
│   ├── seed.py              # Python-based demo data loader (any DB)
│   └── supabase_seed.sql    # SQL seed for Supabase (20 real vessels)
├── fetcher.py               # AIS ingestion process
├── requirements.txt
├── render.yaml              # Render blueprint
├── Procfile                 # Process definitions
├── .env.example
└── README.md
```
