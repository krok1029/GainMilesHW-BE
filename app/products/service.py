from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.errors import ApiError
from app.extensions import db
from app.models import Category, Product, ProductColor, ProductSize
from app.products.schemas import NewProduct, serialize_product


def create_product(data: NewProduct) -> dict[str, object]:
    try:
        with db.session.begin():
            category_id = db.session.scalar(
                insert(Category)
                .values(name=data.category)
                .on_conflict_do_nothing(index_elements=[Category.name])
                .returning(Category.category_id)
            )
            if category_id is None:
                # A separate statement sees a concurrent winner after ON CONFLICT waits.
                category_id = db.session.execute(
                    select(Category.category_id).where(Category.name == data.category)
                ).scalar_one()
            product = Product(
                code=data.code,
                name=data.name,
                category_id=category_id,
                unit_price=data.unit_price,
                inventory=data.inventory,
                sizes=[ProductSize(size=size) for size in data.sizes],
                colors=[ProductColor(color=color) for color in data.colors],
            )
            db.session.add(product)
            db.session.flush()
            result = serialize_product(product)
    except IntegrityError as error:
        if (
            isinstance(error.orig, UniqueViolation)
            and error.orig.diag.constraint_name == "pk_products"
        ):
            raise ApiError(
                409, "PRODUCT_CODE_EXISTS", "Product code already exists."
            ) from error
        raise
    return result


def get_product(code: str) -> dict[str, object] | None:
    product = db.session.get(Product, code)
    return serialize_product(product) if product is not None else None
