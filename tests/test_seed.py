from typing import Any

import pytest
from flask import Flask
from sqlalchemy import Engine, text

from app import create_app
from app.extensions import db


@pytest.fixture
def database(app: Flask) -> Engine:
    with app.app_context():
        return db.engine


def table_counts(database: Engine) -> dict[str, int]:
    with database.connect() as connection:
        return {
            table: connection.execute(
                text(f"SELECT count(*) FROM {table}")
            ).scalar_one()
            for table in ("categories", "products", "product_sizes", "product_colors")
        }


@pytest.fixture
def expected_demo() -> list[dict[str, Any]]:
    return [
        {
            "code": "A-001",
            "name": "Star",
            "category": "cloth",
            "sizes": ["M", "S"],
            "unit_price": "200.00",
            "inventory": 20,
            "colors": ["Blue", "Red"],
        },
        {
            "code": "A-002",
            "name": "Moon",
            "category": "cloth",
            "sizes": ["L", "M"],
            "unit_price": "300.00",
            "inventory": 10,
            "colors": ["Red", "White"],
        },
        {
            "code": "B-001",
            "name": "Eagle",
            "category": "pants",
            "sizes": ["L", "M"],
            "unit_price": "100.00",
            "inventory": 23,
            "colors": ["Green"],
        },
        {
            "code": "B-002",
            "name": "Bird",
            "category": "pants",
            "sizes": ["L", "M", "S"],
            "unit_price": "50.00",
            "inventory": 12,
            "colors": ["Black"],
        },
    ]


def test_seed_imports_reference_catalog(
    app: Flask, expected_demo: list[dict[str, Any]], database: Engine
) -> None:
    client = app.test_client()
    assert client.get("/api/products").get_json() == {"data": []}

    result = app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "Created: 4; skipped: 0."
    assert table_counts(database) == {
        "categories": 2,
        "products": 4,
        "product_sizes": 9,
        "product_colors": 6,
    }
    assert client.get("/api/products").get_json() == {"data": expected_demo}
    for product in expected_demo:
        assert client.get(f"/api/products/{product['code']}").get_json() == product


def test_repeated_seed_skips_complete_existing_products(
    app: Flask, expected_demo: list[dict[str, Any]], database: Engine
) -> None:
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0

    repeated = runner.invoke(args=["seed-demo"])

    assert repeated.exit_code == 0, repeated.output
    assert repeated.output.strip() == "Created: 0; skipped: 4."
    assert table_counts(database) == {
        "categories": 2,
        "products": 4,
        "product_sizes": 9,
        "product_colors": 6,
    }
    assert app.test_client().get("/api/products").get_json() == {"data": expected_demo}


@pytest.mark.parametrize("remove_options", [False, True])
def test_seed_preserves_edited_product_without_repairing_options(
    app: Flask,
    database: Engine,
    expected_demo: list[dict[str, Any]],
    remove_options: bool,
) -> None:
    edited = {
        "code": "A-001",
        "name": "Edited Star",
        "category": "custom",
        "sizes": ["XL"],
        "unit_price": "123.45",
        "inventory": 99,
        "colors": ["Purple"],
    }
    assert app.test_client().post("/api/products", json=edited).status_code == 201
    if remove_options:
        with database.begin() as connection:
            connection.execute(
                text("DELETE FROM product_sizes WHERE product_code = 'A-001'")
            )
            connection.execute(
                text("DELETE FROM product_colors WHERE product_code = 'A-001'")
            )
        edited = {**edited, "sizes": [], "colors": []}

    result = app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "Created: 3; skipped: 1."
    assert app.test_client().get("/api/products").get_json() == {
        "data": [edited, *expected_demo[1:]]
    }
    assert app.test_client().get("/api/products/A-001").get_json() == edited


def test_seed_recreates_deleted_sample(
    app: Flask, database: Engine, expected_demo: list[dict[str, Any]]
) -> None:
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    with database.begin() as connection:
        connection.execute(text("DELETE FROM products WHERE code = 'B-002'"))
    assert app.test_client().get("/api/products/B-002").status_code == 404

    result = runner.invoke(args=["seed-demo"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "Created: 1; skipped: 3."
    assert app.test_client().get("/api/products").get_json() == {"data": expected_demo}
    assert table_counts(database) == {
        "categories": 2,
        "products": 4,
        "product_sizes": 9,
        "product_colors": 6,
    }


def test_seed_resolves_preexisting_categories_by_name(
    app: Flask, database: Engine, expected_demo: list[dict[str, Any]]
) -> None:
    with database.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO categories (category_id, name) OVERRIDING SYSTEM VALUE
            VALUES (31, 'pants'), (42, 'cloth')
        """)
        )
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    assert app.test_client().get("/api/products").get_json() == {"data": expected_demo}
    assert table_counts(database) == {
        "categories": 2,
        "products": 4,
        "product_sizes": 9,
        "product_colors": 6,
    }


def test_application_creation_does_not_seed(app: Flask) -> None:
    restarted = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
        }
    )
    try:
        assert restarted.test_client().get("/api/products").get_json() == {"data": []}
    finally:
        with restarted.app_context():
            db.session.remove()
            db.engine.dispose()


@pytest.mark.parametrize("keep_existing", [False, True])
def test_failed_seed_rolls_back_all_new_products_and_preserves_existing_data(
    app: Flask,
    database: Engine,
    keep_existing: bool,
    caplog: pytest.LogCaptureFixture,
    expected_demo: list[dict[str, Any]],
) -> None:
    client = app.test_client()
    existing = {
        "code": "B-001",
        "name": "Existing Eagle",
        "category": "custom",
        "sizes": ["XL"],
        "unit_price": "456.78",
        "inventory": 8,
        "colors": ["Pink"],
    }
    if keep_existing:
        assert client.post("/api/products", json=existing).status_code == 201
    before = client.get("/api/products").get_json()
    before_counts = table_counts(database)
    with database.begin() as connection:
        # The sequence survives rollback and proves the fault ran after a full
        # earlier product plus the next product and its category existed.
        connection.execute(text("CREATE SEQUENCE seed_failure_reached"))
        connection.execute(
            text("""
            CREATE FUNCTION fail_second_sample() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.product_code = 'A-002'
                   AND EXISTS (SELECT 1 FROM products WHERE code = 'A-001')
                   AND EXISTS (SELECT 1 FROM product_sizes WHERE product_code = 'A-001')
                   AND EXISTS (
                       SELECT 1 FROM product_colors WHERE product_code = 'A-001'
                   )
                   AND EXISTS (SELECT 1 FROM products WHERE code = 'A-002')
                   AND EXISTS (SELECT 1 FROM categories WHERE name = 'cloth') THEN
                    PERFORM nextval('seed_failure_reached');
                    RAISE EXCEPTION 'controlled seed failure';
                END IF;
                RETURN NEW;
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER fail_seed AFTER INSERT ON product_colors
            FOR EACH ROW EXECUTE FUNCTION fail_second_sample()
        """)
        )

    failed = app.test_cli_runner().invoke(args=["seed-demo"])

    assert failed.exit_code != 0
    assert "Created:" not in failed.output
    assert "Demo seed failed; no products were imported." in failed.output
    assert "controlled seed failure" in caplog.text
    with database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT is_called FROM seed_failure_reached")
            ).scalar_one()
            is True
        )
    assert client.get("/api/products").get_json() == before
    assert client.get("/api/products/A-001").status_code == 404
    assert client.get("/api/products/A-002").status_code == 404
    assert table_counts(database) == before_counts

    with database.begin() as connection:
        connection.execute(text("DROP TRIGGER fail_seed ON product_colors"))
    retried = app.test_cli_runner().invoke(args=["seed-demo"])
    assert retried.exit_code == 0, retried.output
    expected = (
        [*expected_demo[:2], existing, expected_demo[3]]
        if keep_existing
        else expected_demo
    )
    assert client.get("/api/products").get_json() == {"data": expected}
