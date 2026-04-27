"""
A single SQLAlchemy instance shared by both the Flask app and the standalone
fetcher script. Putting it in its own module avoids circular imports between
__init__.py (which needs db to call init_app) and models.py (which needs db.Model).
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
