import os
from flask import Flask
from flask_migrate import Migrate
from dotenv import load_dotenv

from app.db import db

load_dotenv()


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    db_url = os.environ.get("DATABASE_URL", "sqlite:///neptune.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 280,
        },
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
    )
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    Migrate(app, db, directory="migrations")

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    from app import models  # noqa: F401

    return app
