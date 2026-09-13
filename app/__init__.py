import os
from collections.abc import Mapping
from typing import Any

from flask import Flask
from sqlalchemy import URL

from app import models  # noqa: F401
from app.errors import register_error_handlers
from app.extensions import db, migrate
from app.health import health
from app.json import StrictJSONProvider
from app.products.routes import products
from app.seed import seed_demo_command


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.json = StrictJSONProvider(app)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=URL.create(
            "postgresql+psycopg",
            username=os.environ.get("POSTGRES_USER", "gainmiles"),
            password=os.environ.get("POSTGRES_PASSWORD", "gainmiles-local"),
            host=os.environ.get("DB_HOST", "db"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("POSTGRES_DB", "gainmiles"),
        ),
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "connect_args": {
                "connect_timeout": 2,
                "options": "-c statement_timeout=2000",
            },
        },
    )
    if config is not None:
        app.config.update(config)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=False)
    app.register_blueprint(health)
    app.register_blueprint(products)
    register_error_handlers(app)
    app.cli.add_command(seed_demo_command)
    return app
