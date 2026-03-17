"""
Application configuration — reads values from .env via python-dotenv.
"""
import os
from dotenv import load_dotenv

# Load .env from project root
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-secret")

    # ── Database ──
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(basedir, "instance", "placement_db.sqlite"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Google Sheets ──
    GOOGLE_CREDS_FILE = os.getenv(
        "GOOGLE_CREDS_FILE",
        os.path.join(basedir, "slotallocator-d352c8aaa512.json"),
    )
