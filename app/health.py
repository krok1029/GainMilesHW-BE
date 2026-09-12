from flask import Blueprint, Response, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

health = Blueprint("health", __name__)


@health.get("/health")
def check_health() -> tuple[Response, int]:
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.warning("PostgreSQL health query failed")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok"), 200
