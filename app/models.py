from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("name = btrim(name) AND name <> ''", name="name_nonempty"),
    )

    category_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, unique=True)
    products: Mapped[list["Product"]] = relationship(
        back_populates="category", passive_deletes="all"
    )


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("code = btrim(code) AND code <> ''", name="code_nonempty"),
        CheckConstraint("name = btrim(name) AND name <> ''", name="name_nonempty"),
        CheckConstraint(
            "unit_price BETWEEN 0 AND 9999999999.99", name="unit_price_range"
        ),
        CheckConstraint("inventory >= 0", name="inventory_nonnegative"),
        Index("idx_products_category_id", "category_id"),
    )

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.category_id", ondelete="RESTRICT")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    inventory: Mapped[int] = mapped_column(Integer)
    category: Mapped[Category] = relationship(back_populates="products")
    sizes: Mapped[list["ProductSize"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
    colors: Mapped[list["ProductColor"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )


class ProductSize(Base):
    __tablename__ = "product_sizes"
    __table_args__ = (
        CheckConstraint("size = btrim(size) AND size <> ''", name="size_nonempty"),
    )

    product_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.code", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    size: Mapped[str] = mapped_column(Text, primary_key=True)
    product: Mapped[Product] = relationship(back_populates="sizes")


class ProductColor(Base):
    __tablename__ = "product_colors"
    __table_args__ = (
        CheckConstraint("color = btrim(color) AND color <> ''", name="color_nonempty"),
    )

    product_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.code", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    color: Mapped[str] = mapped_column(Text, primary_key=True)
    product: Mapped[Product] = relationship(back_populates="colors")
