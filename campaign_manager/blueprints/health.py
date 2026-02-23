"""Health check endpoint."""
import os
from flask import Blueprint, jsonify
from campaign_manager import db as _db

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    db_url = os.environ.get("DATABASE_URL", "")
    return jsonify({
        "ok": True,
        "db_active": _db.is_active(),
        "db_url_set": bool(db_url),
        "db_url_prefix": db_url[:30] + "..." if len(db_url) > 30 else db_url,
    })
