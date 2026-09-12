from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from typing import Any

import pytest
from flask import Flask
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import URL


@pytest.fixture
def observer(app: Flask, database_url: URL) -> Iterator[Engine]:
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        yield engine
    finally:
        engine.dispose()


def table_counts(observer: Engine) -> dict[str, int]:
    with observer.connect() as connection:
        return {
            table: connection.execute(
                text(f"SELECT count(*) FROM {table}")
            ).scalar_one()
            for table in ("categories", "products", "product_sizes", "product_colors")
        }


def test_products_reuse_existing_category(
    app: Flask, observer: Engine, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    for code in ("A-001", "B-002"):
        response = client.post("/api/products", json={**product_payload, "code": code})
        assert response.status_code == 201
        assert (
            client.get(response.headers["Location"]).get_json()["category"] == "cloth"
        )
    assert table_counts(observer) == {
        "categories": 1,
        "products": 2,
        "product_sizes": 4,
        "product_colors": 4,
    }


@pytest.mark.parametrize(
    "deferred", [False, True], ids=["during-detail-write", "at-commit"]
)
def test_database_failure_rolls_back_entire_create(
    app: Flask,
    observer: Engine,
    product_payload: dict[str, Any],
    deferred: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with observer.connect() as connection:
        # The commit case runs after all rows exist; the immediate case interrupts
        # a detail write after its product and new category have been inserted.
        connection.execute(
            text("""
            CREATE FUNCTION fail_product_write() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF EXISTS (SELECT 1 FROM products WHERE code = NEW.product_code)
                   AND EXISTS (SELECT 1 FROM categories WHERE name = 'cloth') THEN
                    RAISE EXCEPTION 'controlled product write failure';
                END IF;
                RETURN NEW;
            END $$
        """)
        )
        if deferred:
            connection.execute(
                text("""
                CREATE CONSTRAINT TRIGGER fail_write AFTER INSERT ON product_colors
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                EXECUTE FUNCTION fail_product_write()
            """)
            )
        else:
            connection.execute(
                text("""
                CREATE TRIGGER fail_write AFTER INSERT ON product_colors
                FOR EACH ROW EXECUTE FUNCTION fail_product_write()
            """)
            )

    client = app.test_client()
    response = client.post("/api/products", json=product_payload)

    assert response.status_code == 500
    assert response.get_json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "fields": {},
        }
    }
    assert "controlled product write failure" in caplog.text
    assert "Unexpected API error" in caplog.text
    assert client.get("/api/products/A-001").status_code == 404
    assert table_counts(observer) == {
        "categories": 0,
        "products": 0,
        "product_sizes": 0,
        "product_colors": 0,
    }

    with observer.connect() as connection:
        connection.execute(text("DROP TRIGGER fail_write ON product_colors"))
    retry = client.post("/api/products", json=product_payload)
    assert retry.status_code == 201
    assert client.get(retry.headers["Location"]).get_json() == retry.get_json()


def test_duplicate_code_rolls_back_new_category(
    app: Flask, observer: Engine, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    assert client.post("/api/products", json=product_payload).status_code == 201
    duplicate = client.post(
        "/api/products", json={**product_payload, "category": "new-category"}
    )
    assert duplicate.status_code == 409
    assert table_counts(observer) == {
        "categories": 1,
        "products": 1,
        "product_sizes": 2,
        "product_colors": 2,
    }


def wait_for_two_blocked_writers(connection: Connection) -> None:
    deadline = monotonic() + 8
    pause = Event()
    while monotonic() < deadline:
        pids = (
            connection.execute(
                text("""
            SELECT DISTINCT pid FROM pg_locks
            WHERE locktype = 'advisory' AND objid = 70802 AND NOT granted
              AND database = (
                SELECT oid FROM pg_database WHERE datname = current_database()
              )
        """)
            )
            .scalars()
            .all()
        )
        if len(pids) == 2:
            return
        pause.wait(0.01)
    pytest.fail(
        "Two independent PostgreSQL writers did not reach the synchronization lock"
    )


@pytest.mark.parametrize(
    "same_code", [False, True], ids=["same-new-category", "duplicate-code"]
)
def test_overlapping_creates(
    concurrent_app: Flask,
    observer: Engine,
    product_payload: dict[str, Any],
    same_code: bool,
) -> None:
    table = "products" if same_code else "categories"
    with observer.connect() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION pause_insert() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM pg_advisory_xact_lock(70802);
                RETURN NEW;
            END $$
        """)
        )
        connection.execute(
            text(f"""
            CREATE TRIGGER pause_write BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION pause_insert()
        """)
        )
        connection.execute(text("SELECT pg_advisory_lock(70802)"))
        with ThreadPoolExecutor(max_workers=2) as workers:
            try:
                # Distinct categories let duplicate-code requests reach the product
                # insert independently instead of queuing on category uniqueness.
                payloads = [
                    {
                        **product_payload,
                        "code": "A-001" if same_code else f"A-{index}",
                        "category": f"category-{index}" if same_code else "cloth",
                    }
                    for index in range(2)
                ]

                def post(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
                    response = concurrent_app.test_client().post(
                        "/api/products", json=payload
                    )
                    return response.status_code, response.get_json()

                futures = [workers.submit(post, payload) for payload in payloads]
                wait_for_two_blocked_writers(connection)
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(70802)"))
            results = [future.result(timeout=15) for future in futures]

    assert sorted(status for status, _ in results) == (
        [201, 409] if same_code else [201, 201]
    )
    client = concurrent_app.test_client()
    for status, body in results:
        if status == 201:
            assert client.get(f"/api/products/{body['code']}").get_json() == body
        else:
            assert body["error"]["code"] == "PRODUCT_CODE_EXISTS"
    product_count = 1 if same_code else 2
    assert table_counts(observer) == {
        "categories": 1,
        "products": product_count,
        "product_sizes": 2 * product_count,
        "product_colors": 2 * product_count,
    }


def test_unexpected_unique_constraint_failure_is_not_a_code_conflict(
    app: Flask,
    observer: Engine,
    product_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201
    with observer.connect() as connection:
        connection.execute(
            text("CREATE UNIQUE INDEX test_unique_name ON products (name)")
        )

    failed = client.post(
        "/api/products",
        json={**product_payload, "code": "B-002", "category": "new-category"},
    )

    assert failed.status_code == 500
    assert failed.get_json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "fields": {},
        }
    }
    assert "test_unique_name" in caplog.text
    assert client.get("/api/products/B-002").status_code == 404
    assert client.get(original.headers["Location"]).get_json() == original.get_json()
    assert table_counts(observer) == {
        "categories": 1,
        "products": 1,
        "product_sizes": 2,
        "product_colors": 2,
    }
