"""
Database models — User and AllocationRun.
"""
import json
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()




class AllocationRun(db.Model):
    """Stores metadata + results of each allocation run."""
    __tablename__ = "allocation_runs"

    id = db.Column(db.Integer, primary_key=True)
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
        return f"<AllocationRun {self.id}>"
