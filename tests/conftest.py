import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app import create_app
from app.extensions import db


@pytest.fixture
def database_url() -> Iterator[URL]:
    configured = os.environ.get("TEST_DATABASE_URL")
    if not configured:
        pytest.fail("TEST_DATABASE_URL must point to the dedicated test PostgreSQL")
    admin_url = make_url(configured)
    if admin_url.get_backend_name() != "postgresql" or (
        admin_url.database != "gainmiles_test"
    ):
        pytest.fail("Tests require the separate PostgreSQL database gainmiles_test")

    database_name = f"test_{uuid4().hex}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        try:
            yield admin_url.set(database=database_name)
        finally:
            with admin.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE "{database_name}" WITH (FORCE)')
                )
    finally:
        admin.dispose()


@pytest.fixture
def app(database_url: URL) -> Iterator[Flask]:
    application = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": database_url})
    try:
        result = application.test_cli_runner().invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        yield application
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()
