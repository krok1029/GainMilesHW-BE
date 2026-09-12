from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest
from flask import Flask
from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db


def test_upgrade_builds_the_four_catalog_tables(app: Flask) -> None:
    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())

    assert tables == {
        "alembic_version",
        "categories",
        "products",
        "product_sizes",
        "product_colors",
    }


@pytest.fixture
def catalog(app: Flask) -> Iterator[Connection]:
    with app.app_context(), db.engine.begin() as connection:
        category_id = connection.execute(
            text("INSERT INTO categories (name) VALUES ('cloth') RETURNING category_id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO products VALUES "
                "('A-001', 'Star', :category_id, 200.00, 20)"
            ),
            {"category_id": category_id},
        )
        connection.execute(
            text("INSERT INTO product_sizes VALUES ('A-001', 'S'), ('A-001', 'M')")
        )
        connection.execute(
            text(
                "INSERT INTO product_colors VALUES ('A-001', 'Red'), ('A-001', 'Blue')"
            )
        )
        yield connection


@pytest.mark.parametrize(
    ("statement", "sqlstate"),
    [
        ("UPDATE products SET inventory = -1", "23514"),
        ("UPDATE products SET unit_price = -1", "23514"),
        ("UPDATE products SET unit_price = 'NaN'", "23514"),
        ("UPDATE products SET name = '  '", "23514"),
        ("UPDATE products SET code = ''", "23514"),
        ("UPDATE categories SET name = ''", "23514"),
        ("UPDATE product_sizes SET size = ' S '", "23514"),
        ("UPDATE product_colors SET color = ''", "23514"),
        ("UPDATE products SET name = NULL", "23502"),
        ("INSERT INTO products SELECT * FROM products", "23505"),
        ("INSERT INTO categories (name) VALUES ('cloth')", "23505"),
        ("INSERT INTO product_sizes VALUES ('A-001', 'S')", "23505"),
        ("INSERT INTO product_colors VALUES ('A-001', 'Red')", "23505"),
        ("INSERT INTO product_sizes VALUES ('missing', 'S')", "23503"),
        ("INSERT INTO product_colors VALUES ('missing', 'Red')", "23503"),
        ("UPDATE products SET category_id = -1", "23503"),
        ("DELETE FROM categories", "23001"),
    ],
)
def test_migrated_database_enforces_catalog_integrity(
    catalog: Connection, statement: str, sqlstate: str
) -> None:
    with pytest.raises(IntegrityError) as failure, catalog.begin_nested():
        catalog.execute(text(statement))
    assert isinstance(failure.value.orig, psycopg.Error)
    assert failure.value.orig.sqlstate == sqlstate


def test_foreign_keys_follow_code_changes_and_remove_deleted_details(
    catalog: Connection,
) -> None:
    catalog.execute(text("UPDATE products SET code = 'A-003' WHERE code = 'A-001'"))
    for table in ("product_sizes", "product_colors"):
        assert set(
            catalog.execute(text(f"SELECT product_code FROM {table}")).scalars()
        ) == {"A-003"}

    catalog.execute(text("DELETE FROM products WHERE code = 'A-003'"))

    for table in ("product_sizes", "product_colors"):
        assert catalog.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    assert catalog.execute(text("SELECT name FROM categories")).scalar_one() == "cloth"


def test_repeated_upgrade_preserves_records_and_matches_models(app: Flask) -> None:
    with app.app_context(), db.engine.begin() as connection:
        category_id = connection.execute(
            text("INSERT INTO categories (name) VALUES ('pants') RETURNING category_id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO products VALUES "
                "('B-001', 'Eagle', :category_id, 100.00, 23)"
            ),
            {"category_id": category_id},
        )

    runner = app.test_cli_runner()
    repeated = runner.invoke(args=["db", "upgrade"])
    assert repeated.exit_code == 0, repeated.output
    comparison = runner.invoke(args=["db", "check"])
    assert comparison.exit_code == 0, comparison.output

    with app.app_context(), db.engine.connect() as connection:
        assert connection.execute(
            text("SELECT code, unit_price, inventory FROM products")
        ).one() == ("B-001", Decimal("100.00"), 23)


def test_initial_migration_can_be_reversed_on_an_empty_test_database(
    app: Flask,
) -> None:
    result = app.test_cli_runner().invoke(args=["db", "downgrade", "base"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert set(inspect(db.engine).get_table_names()) == {"alembic_version"}
