import re
from dataclasses import dataclass
from decimal import Decimal
from typing import NoReturn, TypeGuard

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


def is_product_code(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value) is not None


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


def parse_unit_price(price: object) -> Decimal:
    if (
        not isinstance(price, str)
        or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", price) is None
    ):
        invalid_field(
            "unit_price", "Must be a decimal string with at most two decimal places."
        )
    value = Decimal(price)
    if value > Decimal("9999999999.99"):
        invalid_field("unit_price", "Must be from 0 to 9999999999.99.")
    return value


def parse_inventory(inventory: object) -> int:
    if type(inventory) is not int or not 0 <= inventory <= 2147483647:
        invalid_field("inventory", "Must be an integer from 0 to 2147483647.")
    return inventory


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
    if not is_product_code(code):
        invalid_field(
            "code", "Must contain only ASCII letters, digits, hyphens or underscores."
        )
    name = trimmed_text(body["name"], "name")
    category = trimmed_text(body["category"], "category")
    sizes = text_collection(body["sizes"], "sizes")
    colors = text_collection(body["colors"], "colors")
    unit_price = parse_unit_price(body["unit_price"])
    inventory = parse_inventory(body["inventory"])
    return NewProduct(code, name, category, sizes, unit_price, inventory, colors)


@dataclass(frozen=True)
class ProductChanges:
    # None denotes omission; explicit JSON null is rejected during parsing.
    name: str | None = None
    category: str | None = None
    sizes: tuple[str, ...] | None = None
    unit_price: Decimal | None = None
    inventory: int | None = None
    colors: tuple[str, ...] | None = None


def parse_product_changes(body: object) -> ProductChanges:
    if not isinstance(body, dict):
        invalid_field("body", "Must be a JSON object.")
    if not body:
        invalid_field("body", "Must provide at least one writable field.")
    if "code" in body:
        invalid_field("code", "Product code cannot be changed.")
    writable = {"name", "category", "sizes", "unit_price", "inventory", "colors"}
    unknown = {field: ["Unknown field."] for field in sorted(body.keys() - writable)}
    if unknown:
        raise ApiError(422, "VALIDATION_ERROR", "Request validation failed.", unknown)
    return ProductChanges(
        name=trimmed_text(body["name"], "name") if "name" in body else None,
        category=trimmed_text(body["category"], "category")
        if "category" in body
        else None,
        sizes=text_collection(body["sizes"], "sizes") if "sizes" in body else None,
        unit_price=parse_unit_price(body["unit_price"])
        if "unit_price" in body
        else None,
        inventory=parse_inventory(body["inventory"]) if "inventory" in body else None,
        colors=text_collection(body["colors"], "colors") if "colors" in body else None,
    )


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
