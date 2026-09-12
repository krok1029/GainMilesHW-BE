from flask import Blueprint, Response, abort, jsonify, request, url_for

from app.errors import ApiError
from app.products.schemas import is_product_code, parse_product
from app.products.service import create_product, get_product, list_products

products = Blueprint("products", __name__, url_prefix="/api/products")


@products.get("")
def list_catalog() -> Response:
    return jsonify(data=list_products())


@products.post("")
def create() -> Response:
    if request.mimetype != "application/json":
        abort(415)
    product = create_product(parse_product(request.get_json()))
    response = jsonify(product)
    response.status_code = 201
    response.headers["Location"] = url_for("products.get", code=product["code"])
    return response


@products.get("/<string:code>")
def get(code: str) -> Response:
    product = get_product(code) if is_product_code(code) else None
    if product is None:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return jsonify(product)
