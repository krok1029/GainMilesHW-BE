from decimal import Decimal

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Product
from app.products.schemas import NewProduct
from app.products.service import add_product

DEMO_PRODUCTS = (
    NewProduct(
        code="A-001",
        name="Star",
        category="cloth",
        sizes=("S", "M"),
        unit_price=Decimal("200"),
        inventory=20,
        colors=("Red", "Blue"),
    ),
    NewProduct(
        code="A-002",
        name="Moon",
        category="cloth",
        sizes=("M", "L"),
        unit_price=Decimal("300"),
        inventory=10,
        colors=("Red", "White"),
    ),
    NewProduct(
        code="B-001",
        name="Eagle",
        category="pants",
        sizes=("M", "L"),
        unit_price=Decimal("100"),
        inventory=23,
        colors=("Green",),
    ),
    NewProduct(
        code="B-002",
        name="Bird",
        category="pants",
        sizes=("S", "M", "L"),
        unit_price=Decimal("50"),
        inventory=12,
        colors=("Black",),
    ),
)


def seed_demo() -> tuple[int, int]:
    with db.session.begin():
        existing_codes = set(
            db.session.scalars(
                select(Product.code).where(
                    Product.code.in_([product.code for product in DEMO_PRODUCTS])
                )
            )
        )
        for product in DEMO_PRODUCTS:
            if product.code not in existing_codes:
                add_product(product)
    return len(DEMO_PRODUCTS) - len(existing_codes), len(existing_codes)


@click.command("seed-demo")
@with_appcontext
def seed_demo_command() -> None:
    """Import missing reference products, preserving any existing product."""
    try:
        created, skipped = seed_demo()
    except SQLAlchemyError as error:
        current_app.logger.exception("Demo seed failed")
        raise click.ClickException(
            "Demo seed failed; no products were imported."
        ) from error
    click.echo(f"Created: {created}; skipped: {skipped}.")
