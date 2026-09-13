"""Create normalized product catalog

Revision ID: 0001
Revises:
Create Date: 2026-09-12 15:29:36.890278

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column(
            "category_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "name = btrim(name) AND name <> ''",
            name=op.f("ck_categories_name_nonempty"),
        ),
        sa.PrimaryKeyConstraint("category_id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )
    op.create_table(
        "products",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("inventory", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "code = btrim(code) AND code <> ''", name=op.f("ck_products_code_nonempty")
        ),
        sa.CheckConstraint(
            "name = btrim(name) AND name <> ''", name=op.f("ck_products_name_nonempty")
        ),
        sa.CheckConstraint(
            "inventory >= 0", name=op.f("ck_products_inventory_nonnegative")
        ),
        sa.CheckConstraint(
            "unit_price BETWEEN 0 AND 9999999999.99",
            name=op.f("ck_products_unit_price_range"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.category_id"],
            name=op.f("fk_products_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_products")),
    )
    op.create_index(
        "idx_products_category_id", "products", ["category_id"], unique=False
    )
    op.create_table(
        "product_colors",
        sa.Column("product_code", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "color = btrim(color) AND color <> ''",
            name=op.f("ck_product_colors_color_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["product_code"],
            ["products.code"],
            name=op.f("fk_product_colors_product_code_products"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "product_code", "color", name=op.f("pk_product_colors")
        ),
    )
    op.create_table(
        "product_sizes",
        sa.Column("product_code", sa.Text(), nullable=False),
        sa.Column("size", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "size = btrim(size) AND size <> ''",
            name=op.f("ck_product_sizes_size_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["product_code"],
            ["products.code"],
            name=op.f("fk_product_sizes_product_code_products"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_code", "size", name=op.f("pk_product_sizes")),
    )


def downgrade() -> None:
    op.drop_table("product_sizes")
    op.drop_table("product_colors")
    op.drop_index("idx_products_category_id", table_name="products")
    op.drop_table("products")
    op.drop_table("categories")
