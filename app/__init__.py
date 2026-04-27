"""
Flask application factory.

Using the factory pattern (rather than a module-level `app = Flask(__name__)`)
because it makes testing easier (each test can build a fresh app with overridden
config) and it's the pattern Flask-Migrate's CLI expects when you point it at
'app:create_app()'.
"""
import os
from flask import Flask
from flask_migrate import Migrate
from dotenv import load_dotenv

from app.db import db

load_dotenv()


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    # --- Configuration ---------------------------------------------------------
    # Render exposes the Postgres URL as DATABASE_URL but uses the legacy
    # 'postgres://' scheme; SQLAlchemy 2.x requires 'postgresql://'.
    db_url = os.environ.get("DATABASE_URL", "sqlite:///neptune.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Pool settings tuned for Render's free tier + Supabase session pooler.
        # pool_pre_ping handles connections that the pooler may have closed.
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 280,
        },
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
    )
    if config_overrides:
        app.config.update(config_overrides)

    # --- Extensions ------------------------------------------------------------
    db.init_app(app)
    Migrate(app, db, directory="migrations")

    # --- Blueprints ------------------------------------------------------------
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    # --- Models must be imported so Alembic can autogenerate migrations -------
    from app import models  # noqa: F401

    return app
