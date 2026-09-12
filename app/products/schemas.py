import re
from dataclasses import dataclass
from decimal import Decimal
from typing import NoReturn

from app.errors import ApiError
from app.models import Product


@dataclass(frozen=True)
class NewProduct:
    code: str
    name: str
    category: str
    sizes: tuple[str, ...]
    unit_price: Decimal
    inventory: int
    colors: tuple[str, ...]


def invalid_field(field: str, message: str) -> NoReturn:
    raise ApiError(
        422, "VALIDATION_ERROR", "Request validation failed.", {field: [message]}
    )


def trimmed_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        invalid_field(field, "Must be a non-empty string.")
    # PostgreSQL text cannot store NUL or unpaired Unicode surrogates.
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        invalid_field(field, "Must contain valid Unicode text without NUL.")
    return value.strip()


def text_collection(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        invalid_field(field, "Must be a non-empty array of strings.")
    items = tuple(trimmed_text(item, field) for item in value)
    if len(set(items)) != len(items):
        invalid_field(field, "Must not contain duplicate values after trimming.")
    return items


def parse_product(body: object) -> NewProduct:
    if not isinstance(body, dict):
        invalid_field("body", "Must be a JSON object.")
    required = {
        "code",
        "name",
        "category",
        "sizes",
        "unit_price",
        "inventory",
        "colors",
    }
    fields = {field: ["Field is required."] for field in sorted(required - body.keys())}
    fields.update(
        {field: ["Unknown field."] for field in sorted(body.keys() - required)}
    )
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "Request validation failed.", fields)

    code = body["code"]
    if not isinstance(code, str) or re.fullmatch(r"[A-Za-z0-9_-]+", code) is None:
        invalid_field(
            "code", "Must contain only ASCII letters, digits, hyphens or underscores."
        )
    name = trimmed_text(body["name"], "name")
    category = trimmed_text(body["category"], "category")
    sizes = text_collection(body["sizes"], "sizes")
    colors = text_collection(body["colors"], "colors")
    price = body["unit_price"]
    if (
        not isinstance(price, str)
        or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", price) is None
    ):
        invalid_field(
            "unit_price", "Must be a decimal string with at most two decimal places."
        )
    unit_price = Decimal(price)
    if unit_price > Decimal("9999999999.99"):
        invalid_field("unit_price", "Must be from 0 to 9999999999.99.")
    inventory = body["inventory"]
    if type(inventory) is not int or not 0 <= inventory <= 2147483647:
        invalid_field("inventory", "Must be an integer from 0 to 2147483647.")
    return NewProduct(code, name, category, sizes, unit_price, inventory, colors)


def serialize_product(product: Product) -> dict[str, object]:
    return {
        "code": product.code,
        "name": product.name,
        "category": product.category.name,
        "sizes": sorted(item.size for item in product.sizes),
        "unit_price": format(product.unit_price, ".2f"),
        "inventory": product.inventory,
        "colors": sorted(item.color for item in product.colors),
    }
