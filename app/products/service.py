from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.errors import ApiError
from app.extensions import db
from app.models import Category, Product, ProductColor, ProductSize
from app.products.schemas import NewProduct, serialize_product


def add_product(data: NewProduct) -> Product:
    """Add a complete product to the caller's transaction without committing."""
    category = db.session.scalar(
        insert(Category)
        .values(name=data.category)
        .on_conflict_do_nothing(index_elements=[Category.name])
        .returning(Category)
    )
    if category is None:
        # A separate statement sees a concurrent winner after ON CONFLICT waits.
        category = db.session.execute(
            select(Category).where(Category.name == data.category)
        ).scalar_one()
    product = Product(
        code=data.code,
        name=data.name,
        category=category,
        unit_price=data.unit_price,
        inventory=data.inventory,
        sizes=[ProductSize(size=size) for size in data.sizes],
        colors=[ProductColor(color=color) for color in data.colors],
    )
    db.session.add(product)
    db.session.flush()
    return product


def create_product(data: NewProduct) -> dict[str, object]:
    try:
        with db.session.begin():
            product = add_product(data)
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
    product = db.session.get(
        Product,
        code,
        options=[
            joinedload(Product.category),
            selectinload(Product.sizes),
            selectinload(Product.colors),
        ],
    )
    return serialize_product(product) if product is not None else None


def list_products() -> list[dict[str, object]]:
    products = db.session.scalars(
        select(Product).options(
            joinedload(Product.category),
            selectinload(Product.sizes),
            selectinload(Product.colors),
        )
    ).all()
    return [
        serialize_product(product)
        for product in sorted(products, key=lambda product: product.code)
    ]
