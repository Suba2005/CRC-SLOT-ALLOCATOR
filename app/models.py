"""
Database models — User and AllocationRun.
"""
import json
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """Application user with role-based access."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.String(20),
        nullable=False,
        default="student",
    )  # student | leader | staff | crc_head
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    allocation_runs = db.relationship(
        "AllocationRun", backref="user", lazy=True
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class AllocationRun(db.Model):
    """Stores metadata + results of each allocation run."""
    __tablename__ = "allocation_runs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    sheet_url = db.Column(db.String(500), nullable=True)
    config_json = db.Column(db.Text, nullable=True)  # JSON string
    results_json = db.Column(db.Text, nullable=True)  # JSON string

    def set_config(self, config: dict):
        self.config_json = json.dumps(config)

    def get_config(self) -> dict:
        return json.loads(self.config_json) if self.config_json else {}

    def set_results(self, results: dict):
        self.results_json = json.dumps(results, default=str)

    def get_results(self) -> dict:
        return json.loads(self.results_json) if self.results_json else {}

    def __repr__(self):
        return f"<AllocationRun {self.id} by user {self.user_id}>"
