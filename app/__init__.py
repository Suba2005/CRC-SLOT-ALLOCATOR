"""
Flask application factory — creates app, loads config, registers blueprints.
"""
import os
from flask import Flask
from .models import db
from .config import Config


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    # Create Flask app
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    # Load configuration
    app.config.from_object(config_class)

    # Ensure the instance folder exists (for SQLite)
    os.makedirs(app.instance_path, exist_ok=True)

    # ── Initialise extensions ──
    db.init_app(app)

    # ── Register blueprints ──
    from .routes.allocator import allocator_bp

    app.register_blueprint(allocator_bp, url_prefix="/allocator")

    # ── Root redirect ──
    @app.route("/")
    def index():
        from flask import redirect, url_for
        return redirect(url_for("allocator.upload"))

    # ── Create DB tables ──
    with app.app_context():
        db.create_all()

    return app