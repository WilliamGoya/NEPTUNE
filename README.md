# Neptune

Maritime logistics platform with real-time AIS vessel tracking.

## Stack

Flask · SQLAlchemy · Alembic · Postgres (Supabase) / SQLite · websockets · gunicorn

## Setup with Supabase

1. Create a project at https://supabase.com.
2. Open SQL Editor → New query, paste `scripts/supabase_seed.sql`, run it.
3. Project Settings → Database → Connection string → URI → Session pooler → copy URL.
4. Local install:

```bash
git clone <your-repo-url>
cd neptune
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

5. Edit `.env`:
   - `DATABASE_URL` = Supabase URL from step 3
   - `AISSTREAM_API_KEY` = free key from https://aisstream.io
   - `SECRET_KEY` = `python -c "import secrets; print(secrets.token_hex(32))"`

6. Run:

```bash
flask --app app run --debug
```

7. Open http://localhost:5000.

8. (Optional) Live AIS ingestion:

```bash
python fetcher.py
```

## Setup with local SQLite

```bash
cp .env.example .env
flask --app app db upgrade
python scripts/seed.py
flask --app app run --debug
```

## Deployment to Render

Push to GitHub. Render reads `render.yaml` and provisions web service, worker, and Postgres. Set `AISSTREAM_API_KEY` manually in the Render dashboard.

## Layout

```
neptune/
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── routes.py
│   ├── templates/
│   └── static/
├── migrations/
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
├── scripts/
│   ├── seed.py
│   └── supabase_seed.sql
├── fetcher.py
├── requirements.txt
├── render.yaml
├── Procfile
├── .env.example
└── README.md
```

## Routes

- `GET /` — dashboard
- `GET /search?q=...` — search by name or MMSI
- `GET /vessel/<mmsi>` — vessel detail with map
- `GET /track` — watchlist
- `POST /track` — add to watchlist
- `GET /api/positions/<mmsi>` — position JSON feed
- `GET /health` — health check
