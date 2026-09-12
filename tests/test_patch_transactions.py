from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from typing import Any

import pytest
from flask import Flask
from sqlalchemy import Connection, Engine, text

from app.extensions import db


@pytest.fixture
def database(app: Flask) -> Engine:
    with app.app_context():
        return db.engine


@pytest.mark.parametrize(
    "deferred", [False, True], ids=["during-replacement", "at-commit"]
)
def test_failed_patch_restores_attributes_options_and_category(
    app: Flask,
    database: Engine,
    product_payload: dict[str, Any],
    deferred: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    other = client.post("/api/products", json={**product_payload, "code": "A-002"})
    assert original.status_code == other.status_code == 201
    changes = {
        "name": "Changed",
        "category": "new-category",
        "unit_price": "99.50",
        "inventory": 5,
        "sizes": ["M", "L"],
        "colors": ["Red", "Green"],
    }
    with database.begin() as connection:
        connection.execute(text("CREATE SEQUENCE patch_failure_reached"))
        connection.execute(
            text("""
            CREATE FUNCTION fail_option_replacement() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.product_code = 'A-001'
                   AND EXISTS (
                       SELECT 1 FROM products p JOIN categories c USING (category_id)
                       WHERE p.code = 'A-001' AND p.name = 'Changed'
                         AND p.inventory = 5 AND p.unit_price = 99.50
                         AND c.name = 'new-category'
                   ) AND EXISTS (
                       SELECT 1 FROM product_sizes
                       WHERE product_code = 'A-001' AND size = 'L'
                   ) AND EXISTS (
                       SELECT 1 FROM product_colors
                       WHERE product_code = 'A-001' AND color = 'Green'
                   ) THEN
                    PERFORM nextval('patch_failure_reached');
                    RAISE EXCEPTION 'controlled patch failure';
                END IF;
                RETURN OLD;
            END $$
        """)
        )
        trigger = "CREATE CONSTRAINT TRIGGER" if deferred else "CREATE TRIGGER"
        timing = "DEFERRABLE INITIALLY DEFERRED" if deferred else ""
        connection.execute(
            text(f"""
            {trigger} fail_patch AFTER DELETE ON product_sizes {timing}
            FOR EACH ROW EXECUTE FUNCTION fail_option_replacement()
        """)
        )

    result = client.patch("/api/products/A-001", json=changes)

    assert result.status_code == 500
    assert result.get_json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "fields": {},
        }
    }
    assert "controlled patch failure" in caplog.text
    assert client.get("/api/products/A-001").get_json() == original.get_json()
    assert client.get("/api/products/A-002").get_json() == other.get_json()
    with database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT is_called FROM patch_failure_reached")
            ).scalar_one()
            is True
        )
        assert connection.execute(
            text("SELECT name FROM categories")
        ).scalars().all() == ["cloth"]
        assert (
            connection.execute(text("SELECT count(*) FROM product_sizes")).scalar_one()
            == 4
        )
        assert (
            connection.execute(text("SELECT count(*) FROM product_colors")).scalar_one()
            == 4
        )
    with database.begin() as connection:
        connection.execute(text("DROP TRIGGER fail_patch ON product_sizes"))
    retry = client.patch("/api/products/A-001", json=changes)
    assert retry.status_code == 200
    assert retry.get_json() == {
        "code": "A-001",
        "name": "Changed",
        "category": "new-category",
        "unit_price": "99.50",
        "inventory": 5,
        "sizes": ["L", "M"],
        "colors": ["Green", "Red"],
    }
    assert client.get("/api/products/A-001").get_json() == retry.get_json()


def wait_for_waiting_writers(connection: Connection, count: int) -> None:
    deadline = monotonic() + 8
    pause = Event()
    while monotonic() < deadline:
        pids = (
            connection.execute(
                text("""
            SELECT pid FROM pg_stat_activity
            WHERE datname = current_database() AND wait_event_type = 'Lock'
              AND pid <> pg_backend_pid()
        """)
            )
            .scalars()
            .all()
        )
        if len(pids) == count:
            return
        pause.wait(0.01)
    pytest.fail(f"Expected {count} independent writers blocked at the DB boundary")


def test_overlapping_patches_share_one_new_category(
    concurrent_app: Flask, database: Engine, product_payload: dict[str, Any]
) -> None:
    client = concurrent_app.test_client()
    for code in ("A-001", "A-002"):
        assert (
            client.post(
                "/api/products", json={**product_payload, "code": code}
            ).status_code
            == 201
        )
    with database.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        connection.execute(
            text("""
            CREATE FUNCTION pause_category() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM pg_advisory_xact_lock(70804);
                RETURN NEW;
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER pause_category_write BEFORE INSERT ON categories
            FOR EACH ROW EXECUTE FUNCTION pause_category()
        """)
        )
        connection.execute(text("SELECT pg_advisory_lock(70804)"))
        with ThreadPoolExecutor(max_workers=2) as workers:
            try:
                futures = [
                    workers.submit(
                        concurrent_app.test_client().patch,
                        f"/api/products/{code}",
                        json={"category": "new-shared"},
                    )
                    for code in ("A-001", "A-002")
                ]
                wait_for_waiting_writers(connection, 2)
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(70804)"))
            results = [future.result(timeout=15) for future in futures]
    for response in results:
        assert response.status_code == 200
        body = response.get_json()
        assert body["category"] == "new-shared"
        assert client.get(f"/api/products/{body['code']}").get_json() == body
    with database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM categories WHERE name = 'new-shared'")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM categories WHERE name = 'cloth'")
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "replace_options", [False, True], ids=["preserve-omitted", "last-replacement-wins"]
)
def test_overlapping_patches_use_the_last_successful_values(
    concurrent_app: Flask,
    database: Engine,
    product_payload: dict[str, Any],
    replace_options: bool,
) -> None:
    client = concurrent_app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201
    first = {
        "inventory": 11,
        "name": "First",
        "category": "new-category",
        "sizes": ["M", "XL"],
        "colors": ["Red", "White"],
    }
    second: dict[str, Any] = {"inventory": 22}
    if replace_options:
        second.update({"sizes": ["L"], "colors": ["Black"]})
    with database.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        connection.execute(
            text("""
            CREATE FUNCTION pause_first_patch() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM pg_advisory_xact_lock(70804);
                RETURN NEW;
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER pause_first_update BEFORE UPDATE ON products
            FOR EACH ROW WHEN (NEW.inventory = 11)
            EXECUTE FUNCTION pause_first_patch()
        """)
        )
        connection.execute(text("SELECT pg_advisory_lock(70804)"))
        with ThreadPoolExecutor(max_workers=2) as workers:
            try:
                first_future = workers.submit(
                    concurrent_app.test_client().patch,
                    "/api/products/A-001",
                    json=first,
                )
                # First writer already holds the product lock when the trigger waits.
                wait_for_waiting_writers(connection, 1)
                second_future = workers.submit(
                    concurrent_app.test_client().patch,
                    "/api/products/A-001",
                    json=second,
                )
                wait_for_waiting_writers(connection, 2)
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(70804)"))
            first_response = first_future.result(timeout=15)
            second_response = second_future.result(timeout=15)
    assert first_response.status_code == second_response.status_code == 200
    assert first_response.get_json() == {**original.get_json(), **first}
    expected = {**original.get_json(), **first, **second}
    assert second_response.get_json() == expected
    assert client.get("/api/products/A-001").get_json() == expected
