from typing import Any

import pytest
from flask import Flask


def test_patch_inventory_preserves_other_fields(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201

    patched = client.patch("/api/products/A-001", json={"inventory": 12})

    assert patched.status_code == 200
    assert patched.get_json() == {**original.get_json(), "inventory": 12}
    assert client.get("/api/products/A-001").get_json() == patched.get_json()


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"sizes": ["M", "L"]}, {"sizes": ["L", "M"]}),
        ({"colors": ["Red", "Black"]}, {"colors": ["Black", "Red"]}),
        (
            {"sizes": ["S", "M"], "colors": ["Red", "Blue"]},
            {"sizes": ["M", "S"], "colors": ["Blue", "Red"]},
        ),
        (
            {
                "name": " New name ",
                "category": " New category ",
                "sizes": [" s ", "S", "L"],
                "colors": ["blue", " Blue ", "紅"],
                "unit_price": "0",
                "inventory": 0,
            },
            {
                "name": "New name",
                "category": "New category",
                "sizes": ["L", "S", "s"],
                "colors": ["Blue", "blue", "紅"],
                "unit_price": "0.00",
                "inventory": 0,
            },
        ),
    ],
)
def test_patch_replaces_only_supplied_fields(
    app: Flask,
    product_payload: dict[str, Any],
    changes: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201
    result = client.patch("/api/products/A-001", json=changes)
    assert result.status_code == 200
    assert result.get_json() == {**original.get_json(), **expected}
    assert client.get("/api/products/A-001").get_json() == result.get_json()


@pytest.mark.parametrize(
    ("price", "expected", "inventory"),
    [
        ("0", "0.00", 0),
        ("200", "200.00", 20),
        ("200.0", "200.00", 20),
        ("200.00", "200.00", 20),
        ("0.01", "0.01", 1),
        ("9999999999.99", "9999999999.99", 2147483647),
    ],
)
def test_patch_numeric_boundaries(
    app: Flask,
    product_payload: dict[str, Any],
    price: str,
    expected: str,
    inventory: int,
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201
    result = client.patch(
        "/api/products/A-001", json={"unit_price": price, "inventory": inventory}
    )
    assert result.status_code == 200
    assert result.get_json() == {
        **original.get_json(),
        "unit_price": expected,
        "inventory": inventory,
    }
    assert client.get("/api/products/A-001").get_json() == result.get_json()


INVALID_OPTIONS: tuple[object, ...] = (
    [],
    "M",
    {},
    [True],
    [1],
    [None],
    [""],
    [" \t"],
    ["M", " M "],
    [["M"]],
)
INVALID_TEXT: tuple[object, ...] = (
    None,
    "",
    " \t\n",
    True,
    1,
    [],
    "bad\x00text",
    "bad\ud800text",
)
INVALID_PRICE: tuple[object, ...] = (
    None,
    200,
    200.0,
    True,
    {},
    "",
    "-1",
    "+1",
    " 1",
    "1 ",
    "1\n",
    "1e2",
    "NaN",
    "Infinity",
    "0.001",
    "10000000000",
    "1.",
    ".1",
    "１",
)
INVALID_INVENTORY: tuple[object, ...] = (
    None,
    -1,
    2147483648,
    True,
    False,
    "1",
    1.0,
    [],
)


@pytest.mark.parametrize(
    ("field", "value"),
    [("code", "A-001"), ("code", "B-002"), ("code", None), ("extra", 1)]
    + [(field, value) for field in ("name", "category") for value in INVALID_TEXT]
    + [
        (field, value)
        for field in ("sizes", "colors")
        for value in (*INVALID_OPTIONS, None, ["bad\x00text"], ["bad\ud800text"])
    ]
    + [("unit_price", value) for value in INVALID_PRICE]
    + [("inventory", value) for value in INVALID_INVENTORY],
)
def test_patch_invalid_fields_leave_original_unchanged(
    app: Flask, product_payload: dict[str, Any], field: str, value: object
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    assert original.status_code == 201
    result = client.patch(
        "/api/products/A-001", json={"name": "Would change", field: value}
    )
    assert result.status_code == 422
    error = result.get_json()["error"]
    assert set(error) == {"code", "message", "fields"}
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed."
    assert isinstance(error["fields"][field], list) and error["fields"][field]
    assert client.get("/api/products/A-001").get_json() == original.get_json()


@pytest.mark.parametrize("body", [{}, None, [], "product", 1, True])
def test_patch_rejects_empty_or_non_object_body(app: Flask, body: object) -> None:
    result = app.test_client().patch(
        "/api/products/missing",
        data=app.json.dumps(body),
        content_type="application/json",
    )
    assert result.status_code == 422
    assert result.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("body", "media_type", "status", "code"),
    [
        ("{", "application/json", 400, "INVALID_JSON"),
        ("", "application/json", 400, "INVALID_JSON"),
        ('{"unit_price":NaN}', "application/json", 400, "INVALID_JSON"),
        ('{"unit_price":Infinity}', "application/json", 400, "INVALID_JSON"),
        ('{"unit_price":-Infinity}', "application/json", 400, "INVALID_JSON"),
        ("{", "text/plain", 415, "UNSUPPORTED_MEDIA_TYPE"),
        ("{}", None, 415, "UNSUPPORTED_MEDIA_TYPE"),
        ("{}", "application/problem+json", 415, "UNSUPPORTED_MEDIA_TYPE"),
        ('{"inventory":true}', "application/json", 422, "VALIDATION_ERROR"),
        ('{"code":"missing"}', "application/json", 422, "VALIDATION_ERROR"),
        ('{"inventory":1}', "application/json", 404, "PRODUCT_NOT_FOUND"),
    ],
)
def test_patch_validates_before_existence(
    app: Flask, body: str, media_type: str | None, status: int, code: str
) -> None:
    response = app.test_client().patch(
        "/api/products/missing", data=body, content_type=media_type
    )
    assert response.status_code == status
    error = response.get_json()["error"]
    assert error["code"] == code
    assert isinstance(error["fields"], dict)
    if status != 422:
        assert error["fields"] == {}


@pytest.mark.parametrize("code", ["%00", "%20A-001", "A.001", "%E6%98%9F"])
def test_patch_invalid_url_code_is_not_found_after_validation(
    app: Flask, code: str
) -> None:
    client = app.test_client()
    assert client.patch(f"/api/products/{code}", json={}).status_code == 422
    result = client.patch(f"/api/products/{code}", json={"inventory": 1})
    assert result.status_code == 404
    assert result.get_json()["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_patch_category_changes_only_target_product(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    other = client.post("/api/products", json={**product_payload, "code": "A-002"})
    assert original.status_code == other.status_code == 201
    for category in ("Cloth", "cloth"):
        result = client.patch("/api/products/A-001", json={"category": category})
        assert result.status_code == 200
        assert result.get_json() == {**original.get_json(), "category": category}
        assert client.get("/api/products/A-001").get_json() == result.get_json()
        assert client.get("/api/products/A-002").get_json() == other.get_json()
