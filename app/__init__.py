"""
Flask application factory — creates app, loads config, registers blueprints.
"""
import os
from flask import Flask
from .models import db
from .config import Config

# mail instance comes from the email_service module so that the service
# layer owns the extension and routes/services can import it directly.
from .services.email_service import mail


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
    mail.init_app(app)

    # ── Register blueprints ──
    from .auth.routes import auth_bp
    from .routes.allocator import allocator_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(allocator_bp, url_prefix="/allocator")
    
    # ── Root redirect ──
    @app.route("/")
    def index():
        from flask import redirect, url_for, session
        if session.get("user_id"):
            return redirect(url_for("allocator.upload"))
        return redirect(url_for("auth.login"))

    # ── Create DB tables ──
    with app.app_context():
        db.create_all()

    return app