"""Exercise public HTTP during the disposable Compose handoff check."""

import json
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REFERENCE = [
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
EDITED = {
    "code": "A-001",
    "name": "Edited Star",
    "category": "custom",
    "sizes": ["XL"],
    "unit_price": "123.45",
    "inventory": 7,
    "colors": ["Purple"],
}


def request(
    method: str, path: str, status: int, body: object = None
) -> tuple[Any, dict[str, str]]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = Request(
        "http://127.0.0.1:8000" + path, data=data, headers=headers, method=method
    )
    try:
        response = urlopen(req, timeout=8)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        assert response.status == status, (method, path, response.status, raw)
        result_headers = dict(response.headers.items())
        if status == 204:
            assert raw == b""
            return None, result_headers
        return json.loads(raw), result_headers


def check_catalog(expected: list[dict[str, Any]]) -> None:
    assert request("GET", "/health", 200)[0] == {"status": "ok"}
    assert request("GET", "/api/products", 200)[0] == {"data": expected}
    for product in expected:
        assert request("GET", f"/api/products/{product['code']}", 200)[0] == product


def exercise_crud() -> None:
    new = {
        "code": "C-001",
        "name": "New",
        "category": "other",
        "sizes": ["M", "S"],
        "unit_price": "9.50",
        "inventory": 3,
        "colors": ["Blue", "Red"],
    }
    created, headers = request("POST", "/api/products", 201, new)
    assert created == new
    assert headers["Location"] == "/api/products/C-001"
    assert request("GET", headers["Location"], 200)[0] == new
    assert (
        request("POST", "/api/products", 409, new)[0]["error"]["code"]
        == "PRODUCT_CODE_EXISTS"
    )
    assert (
        request("PATCH", headers["Location"], 422, {"code": "C-001"})[0]["error"][
            "code"
        ]
        == "VALIDATION_ERROR"
    )
    changes = {"sizes": ["L"], "colors": ["Black"], "inventory": 0}
    assert request("PATCH", headers["Location"], 200, changes)[0] == {**new, **changes}
    assert request("GET", headers["Location"], 200)[0] == {**new, **changes}
    request("DELETE", headers["Location"], 204)
    assert (
        request("GET", headers["Location"], 404)[0]["error"]["code"]
        == "PRODUCT_NOT_FOUND"
    )
    assert (
        request("DELETE", headers["Location"], 404)[0]["error"]["code"]
        == "PRODUCT_NOT_FOUND"
    )
    edits = {key: value for key, value in EDITED.items() if key != "code"}
    assert request("PATCH", "/api/products/A-001", 200, edits)[0] == EDITED
    request("DELETE", "/api/products/B-002", 204)
    check_catalog([EDITED, REFERENCE[1], REFERENCE[2]])


def main() -> None:
    phase = sys.argv[1]
    if phase == "empty":
        check_catalog([])
    elif phase == "seeded":
        check_catalog(REFERENCE)
    elif phase == "crud":
        exercise_crud()
    elif phase == "persisted":
        check_catalog([EDITED, REFERENCE[1], REFERENCE[2]])
        assert (
            request("GET", "/api/products/B-002", 404)[0]["error"]["code"]
            == "PRODUCT_NOT_FOUND"
        )
    elif phase == "reseeded":
        check_catalog([EDITED, *REFERENCE[1:]])
    else:
        raise ValueError(f"Unknown handoff phase: {phase}")
    print(f"PASS: HTTP {phase}")


if __name__ == "__main__":
    main()
