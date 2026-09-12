from typing import Any

from flask import Flask
from sqlalchemy import Connection, event

from app.extensions import db


def test_empty_catalog(app: Flask) -> None:
    response = app.test_client().get("/api/products")
    assert response.status_code == 200
    assert response.get_json() == {"data": []}


def test_catalog_returns_complete_products_in_code_point_order(app: Flask) -> None:
    client = app.test_client()
    for code in ["a-1", "Z-1", "A_1", "A-1", "A0"]:
        created = client.post(
            "/api/products",
            json={
                "code": code,
                "name": "Named",
                "category": "Mixed",
                "sizes": ["s", "S", "M"],
                "colors": ["紅", "blue", "Blue"],
                "unit_price": "12.5",
                "inventory": 7,
            },
        )
        assert created.status_code == 201

    response = client.get("/api/products")

    assert response.status_code == 200
    assert response.get_json() == {
        "data": [
            {
                "code": code,
                "name": "Named",
                "category": "Mixed",
                "sizes": ["M", "S", "s"],
                "colors": ["Blue", "blue", "紅"],
                "unit_price": "12.50",
                "inventory": 7,
            }
            for code in ["A-1", "A0", "A_1", "Z-1", "a-1"]
        ]
    }


def test_catalog_queries_do_not_grow_per_product(app: Flask) -> None:
    client = app.test_client()
    for index in range(30):
        assert (
            client.post(
                "/api/products",
                json={
                    "code": f"P-{index:02}",
                    "name": "Item",
                    "category": f"category-{index}",
                    "sizes": ["M", "S"],
                    "colors": ["Red", "Blue"],
                    "unit_price": "1",
                    "inventory": 5,
                },
            ).status_code
            == 201
        )

    reads = 0

    def count_reads(
        connection: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        nonlocal reads
        if statement.lstrip().upper().startswith("SELECT"):
            reads += 1

    with app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", count_reads)
    try:
        response = client.get("/api/products")
    finally:
        event.remove(engine, "before_cursor_execute", count_reads)

    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 30
    # A query budget checks batching without prescribing SQL or query order.
    assert 0 < reads <= 4
