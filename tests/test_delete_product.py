from typing import Any

import pytest
from flask import Flask
from sqlalchemy import Engine, text

from app.extensions import db


def test_delete_product_returns_empty_204_and_then_not_found(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    assert client.post("/api/products", json=product_payload).status_code == 201

    deleted = client.delete("/api/products/A-001")

    assert deleted.status_code == 204
    assert deleted.data == b""
    assert client.get("/api/products/A-001").get_json() == {
        "error": {
            "code": "PRODUCT_NOT_FOUND",
            "message": "Product not found.",
            "fields": {},
        }
    }
    assert client.get("/api/products/A-001").status_code == 404


@pytest.fixture
def database(app: Flask) -> Engine:
    with app.app_context():
        return db.engine


def test_repeated_delete_returns_product_not_found(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    assert client.post("/api/products", json=product_payload).status_code == 201
    assert client.delete("/api/products/A-001").status_code == 204
    repeated = client.delete("/api/products/A-001")
    assert repeated.status_code == 404
    assert repeated.mimetype == "application/json"
    assert repeated.get_json() == {
        "error": {
            "code": "PRODUCT_NOT_FOUND",
            "message": "Product not found.",
            "fields": {},
        }
    }


@pytest.mark.parametrize(
    "code", ["missing", "a-001", "%00", "%20A-001", "A.001", "%E6%98%9F"]
)
def test_unknown_or_invalid_delete_code_preserves_existing_product(
    app: Flask, product_payload: dict[str, Any], code: str
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201
    result = client.delete(f"/api/products/{code}")
    assert result.status_code == 404
    assert result.get_json() == {
        "error": {
            "code": "PRODUCT_NOT_FOUND",
            "message": "Product not found.",
            "fields": {},
        }
    }
    assert client.get("/api/products/A-001").get_json() == original.get_json()


@pytest.mark.parametrize(
    "keep_other", [False, True], ids=["last-product", "shared-category"]
)
def test_delete_cascades_options_but_preserves_category_and_other_products(
    app: Flask, database: Engine, product_payload: dict[str, Any], keep_other: bool
) -> None:
    client = app.test_client()
    assert client.post("/api/products", json=product_payload).status_code == 201
    if keep_other:
        other = client.post("/api/products", json={**product_payload, "code": "A-002"})
        assert other.status_code == 201
    with database.connect() as connection:
        category = connection.execute(
            text("SELECT category_id, name FROM categories")
        ).one()

    result = client.delete("/api/products/A-001")

    assert result.status_code == 204
    assert result.data == b""
    assert client.get("/api/products/A-001").status_code == 404
    if keep_other:
        assert client.get("/api/products/A-002").get_json() == other.get_json()
    with database.connect() as connection:
        assert (
            connection.execute(text("SELECT category_id, name FROM categories")).one()
            == category
        )
        for table in ("product_sizes", "product_colors"):
            assert (
                connection.execute(
                    text(f"SELECT count(*) FROM {table} WHERE product_code = 'A-001'")
                ).scalar_one()
                == 0
            )


@pytest.mark.parametrize("deferred", [False, True], ids=["during-cascade", "at-commit"])
def test_delete_failure_rolls_back_product_and_all_options(
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
    with database.begin() as connection:
        connection.execute(text("CREATE SEQUENCE delete_failure_reached"))
        connection.execute(
            text("""
            CREATE FUNCTION fail_detail_delete() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.product_code = 'A-001' AND NOT EXISTS (
                    SELECT 1 FROM products WHERE code = 'A-001'
                ) THEN
                    PERFORM nextval('delete_failure_reached');
                    RAISE EXCEPTION 'controlled delete failure';
                END IF;
                RETURN OLD;
            END $$
        """)
        )
        trigger = "CREATE CONSTRAINT TRIGGER" if deferred else "CREATE TRIGGER"
        timing = "DEFERRABLE INITIALLY DEFERRED" if deferred else ""
        connection.execute(
            text(f"""
            {trigger} fail_delete AFTER DELETE ON product_colors {timing}
            FOR EACH ROW EXECUTE FUNCTION fail_detail_delete()
        """)
        )

    result = client.delete("/api/products/A-001")

    assert result.status_code == 500
    assert result.get_json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "fields": {},
        }
    }
    assert "controlled delete failure" in caplog.text
    assert client.get("/api/products/A-001").get_json() == original.get_json()
    assert client.get("/api/products/A-002").get_json() == other.get_json()
    with database.connect() as connection:
        # Sequences survive rollback, proving the product delete reached its cascade.
        assert (
            connection.execute(
                text("SELECT is_called FROM delete_failure_reached")
            ).scalar_one()
            is True
        )
        assert (
            connection.execute(text("SELECT count(*) FROM product_sizes")).scalar_one()
            == 4
        )
        assert (
            connection.execute(text("SELECT count(*) FROM product_colors")).scalar_one()
            == 4
        )
        assert connection.execute(
            text("SELECT name FROM categories")
        ).scalars().all() == ["cloth"]
    with database.begin() as connection:
        connection.execute(text("DROP TRIGGER fail_delete ON product_colors"))
    assert client.delete("/api/products/A-001").status_code == 204
    assert client.get("/api/products/A-001").status_code == 404
    assert client.get("/api/products/A-002").get_json() == other.get_json()
