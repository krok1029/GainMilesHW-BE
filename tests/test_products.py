from typing import Any

import pytest
from flask import Flask

INVALID_COLLECTIONS: tuple[object, ...] = (
    [],
    "S",
    {},
    [1],
    [True],
    [None],
    [""],
    [" \t"],
    ["S", " S "],
    [["S"]],
)


def test_create_product_and_read_its_persisted_representation(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()

    created = client.post("/api/products", json=product_payload)

    expected = {
        "code": "A-001",
        "name": "Star",
        "category": "cloth",
        "sizes": ["M", "S"],
        "unit_price": "200.00",
        "inventory": 20,
        "colors": ["Blue", "Red"],
    }
    assert created.status_code == 201
    assert created.headers["Location"] == "/api/products/A-001"
    assert created.get_json() == expected

    retrieved = client.get(created.headers["Location"])
    assert retrieved.status_code == 200
    assert retrieved.get_json() == expected


def test_invalid_inventory_returns_field_error(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    response = app.test_client().post(
        "/api/products", json={**product_payload, "inventory": True}
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "fields": {"inventory": ["Must be an integer from 0 to 2147483647."]},
        }
    }
    assert app.test_client().get("/api/products/A-001").status_code == 404


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code", ""),
        ("code", " A-001"),
        ("code", "A-001 "),
        ("code", "A/001"),
        ("code", "Ａ001"),
        ("code", "A.001"),
        ("code", "A-001\n"),
        ("code", 123),
        ("name", " \t\n"),
        ("name", False),
        ("name", []),
        ("category", " "),
        ("category", 2),
        ("unit_price", 200),
        ("unit_price", 200.0),
        ("unit_price", True),
        ("unit_price", "-1"),
        ("unit_price", "+1"),
        ("unit_price", " 1"),
        ("unit_price", "1 "),
        ("unit_price", "1e2"),
        ("unit_price", "NaN"),
        ("unit_price", "Infinity"),
        ("unit_price", "0.001"),
        ("unit_price", "10000000000"),
        ("unit_price", "1."),
        ("unit_price", ".1"),
        ("unit_price", ""),
        ("unit_price", "１"),
        ("unit_price", "1\n"),
        ("unit_price", {}),
        ("inventory", -1),
        ("inventory", 2147483648),
        ("inventory", False),
        ("inventory", "1"),
        ("inventory", 1.0),
        ("inventory", []),
    ]
    + [
        (field, None)
        for field in (
            "code",
            "name",
            "category",
            "sizes",
            "unit_price",
            "inventory",
            "colors",
        )
    ]
    + [
        (field, value) for field in ("sizes", "colors") for value in INVALID_COLLECTIONS
    ],
)
def test_invalid_field_is_rejected_without_creating_product(
    app: Flask, product_payload: dict[str, Any], field: str, value: object
) -> None:
    response = app.test_client().post(
        "/api/products", json={**product_payload, field: value}
    )

    assert response.status_code == 422
    error = response.get_json()["error"]
    assert set(error) == {"code", "message", "fields"}
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed."
    assert isinstance(error["fields"][field], list)
    assert all(isinstance(message, str) for message in error["fields"][field])
    assert app.test_client().get("/api/products/A-001").status_code == 404


@pytest.mark.parametrize(
    "field", ["code", "name", "category", "sizes", "unit_price", "inventory", "colors"]
)
def test_missing_field_is_rejected(
    app: Flask, product_payload: dict[str, Any], field: str
) -> None:
    del product_payload[field]
    response = app.test_client().post("/api/products", json=product_payload)
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"][field] == ["Field is required."]


@pytest.mark.parametrize("body", [None, [], "product", 1, True])
def test_non_object_body_is_rejected(app: Flask, body: object) -> None:
    response = app.test_client().post(
        "/api/products", data=app.json.dumps(body), content_type="application/json"
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"] == {
        "body": ["Must be a JSON object."]
    }


def test_unknown_fields_are_rejected(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    response = app.test_client().post(
        "/api/products", json={**product_payload, "category_id": 1}
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"] == {"category_id": ["Unknown field."]}


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
def test_numeric_boundaries(
    app: Flask,
    product_payload: dict[str, Any],
    price: str,
    expected: str,
    inventory: int,
) -> None:
    client = app.test_client()
    created = client.post(
        "/api/products",
        json={**product_payload, "unit_price": price, "inventory": inventory},
    )
    assert created.status_code == 201
    stored = client.get(created.headers["Location"]).get_json()
    assert stored["unit_price"] == expected
    assert stored["inventory"] == inventory


def test_trimming_case_sensitivity_and_unicode_sorting(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    for code, category in [("A_001", " Cloth "), ("a_001", " cloth ")]:
        created = client.post(
            "/api/products",
            json={
                **product_payload,
                "code": code,
                "name": " \t 星星 \n",
                "category": category,
                "sizes": [" s ", "S", "尺寸", " M "],
                "colors": ["紅", "blue", " Blue ", "黑"],
            },
        )
        assert created.status_code == 201
        expected = {
            "code": code,
            "name": "星星",
            "category": category.strip(),
            "sizes": ["M", "S", "s", "尺寸"],
            "colors": ["Blue", "blue", "紅", "黑"],
            "unit_price": "200.00",
            "inventory": 20,
        }
        assert created.get_json() == expected
        assert client.get(created.headers["Location"]).get_json() == expected


def test_duplicate_code_preserves_existing_product(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    original = client.post("/api/products", json=product_payload)
    duplicate = client.post(
        "/api/products",
        json={**product_payload, "name": "Replacement", "category": "another"},
    )
    assert original.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "error": {
            "code": "PRODUCT_CODE_EXISTS",
            "message": "Product code already exists.",
            "fields": {},
        }
    }
    assert client.get(original.headers["Location"]).get_json() == original.get_json()


@pytest.mark.parametrize(
    ("method", "path", "body", "media_type", "status", "code"),
    [
        ("POST", "/api/products", "{", "application/json", 400, "INVALID_JSON"),
        ("POST", "/api/products", "", "application/json", 400, "INVALID_JSON"),
        ("POST", "/api/products", "{}", "text/plain", 415, "UNSUPPORTED_MEDIA_TYPE"),
        ("POST", "/api/products", "{}", None, 415, "UNSUPPORTED_MEDIA_TYPE"),
        (
            "POST",
            "/api/products",
            "{}",
            "application/problem+json",
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        ),
        ("GET", "/missing", None, None, 404, "NOT_FOUND"),
        ("GET", "/api/products/missing", None, None, 404, "PRODUCT_NOT_FOUND"),
        ("PUT", "/api/products", None, None, 405, "METHOD_NOT_ALLOWED"),
    ],
)
def test_http_error_envelope(
    app: Flask,
    method: str,
    path: str,
    body: str | None,
    media_type: str | None,
    status: int,
    code: str,
) -> None:
    response = app.test_client().open(
        path, method=method, data=body, content_type=media_type
    )
    assert response.status_code == status
    assert response.mimetype == "application/json"
    error = response.get_json()["error"]
    assert set(error) == {"code", "message", "fields"}
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"].isascii()
    assert error["fields"] == {}
    if status == 405:
        assert "POST" in response.headers["Allow"]


def test_validation_precedes_conflict(
    app: Flask, product_payload: dict[str, Any]
) -> None:
    client = app.test_client()
    assert client.post("/api/products", json=product_payload).status_code == 201
    assert (
        client.post(
            "/api/products", json={**product_payload, "inventory": -1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/products", data="{", content_type="application/json"
        ).status_code
        == 400
    )
    assert (
        client.post("/api/products", data="{", content_type="text/plain").status_code
        == 415
    )


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_json_numeric_constants_are_parse_errors(
    app: Flask, product_payload: dict[str, Any], constant: str
) -> None:
    body = app.json.dumps(product_payload).replace('"200"', constant)
    response = app.test_client().post(
        "/api/products", data=body, content_type="application/json"
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_JSON"


@pytest.mark.parametrize("field", ["name", "category", "sizes", "colors"])
@pytest.mark.parametrize("text", ["bad\x00text", "bad\ud800text"])
def test_unstorable_unicode_is_rejected(
    app: Flask, product_payload: dict[str, Any], field: str, text: str
) -> None:
    value = [text] if field in ("sizes", "colors") else text
    response = app.test_client().post(
        "/api/products", json={**product_payload, field: value}
    )
    assert response.status_code == 422
    assert field in response.get_json()["error"]["fields"]
