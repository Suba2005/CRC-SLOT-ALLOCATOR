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

    # ── Flask-Mail (Gmail SMTP TLS 587) ──
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USE_SSL = False  # Must be False when using TLS on port 587
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")
    MAIL_DEBUG = os.getenv("MAIL_DEBUG", "False").lower() == "true"
