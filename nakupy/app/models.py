"""Databazovy model nakupni aplikace."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# --- role uzivatelu -------------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_ZADAVATEL = "zadavatel"
ROLE_NAKUPCI = "nakupci"
ROLE_OBOJI = "oboji"
ROLES = {
    ROLE_ADMIN: "Admin (vse)",
    ROLE_ZADAVATEL: "Zadavatel (piše seznam)",
    ROLE_NAKUPCI: "Nákupčí (nakupuje)",
    ROLE_OBOJI: "Zadavatel i nákupčí",
}

# --- stavy ----------------------------------------------------------------
LIST_OPEN = "open"          # seznam se jeste plni
LIST_SHOPPING = "shopping"  # nakupci prave nakupuje
LIST_DONE = "done"          # hotovo
LIST_STATES = {LIST_OPEN: "Otevřený", LIST_SHOPPING: "Nakupuje se", LIST_DONE: "Dokončený"}

ITEM_TODO = "todo"
ITEM_BOUGHT = "bought"
ITEM_MISSING = "missing"      # v obchode nebylo
ITEM_SKIPPED = "skipped"      # nakupci vynechal
ITEM_STATES = {
    ITEM_TODO: "K nákupu",
    ITEM_BOUGHT: "Koupeno",
    ITEM_MISSING: "Nebylo",
    ITEM_SKIPPED: "Vynecháno",
}

DOC_KATALOG = "katalog"
DOC_LETAK = "letak"
DOC_KINDS = {DOC_KATALOG: "Katalog sortimentu", DOC_LETAK: "Leták se slevami"}

DOC_PROCESSING = "processing"
DOC_PARSED = "parsed"
DOC_IMPORTED = "imported"
DOC_FAILED = "failed"
DOC_STATES = {
    DOC_PROCESSING: "Zpracovává se",
    DOC_PARSED: "Připraveno ke kontrole",
    DOC_IMPORTED: "Naimportováno",
    DOC_FAILED: "Chyba",
}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_OBOJI)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def can_shop(self) -> bool:
        return self.role in (ROLE_ADMIN, ROLE_NAKUPCI, ROLE_OBOJI)

    @property
    def can_request(self) -> bool:
        return self.role in (ROLE_ADMIN, ROLE_ZADAVATEL, ROLE_OBOJI)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


class Store(Base):
    """Obchod - Kaufland, Lidl, Albert..."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    section_orders: Mapped[list["StoreSection"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )


class Category(Base):
    """Kategorie sortimentu = usek v obchode (regal)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    icon: Mapped[str] = mapped_column(String(16), default="🛒")
    position: Mapped[int] = mapped_column(Integer, default=100)
    keywords: Mapped[str] = mapped_column(Text, default="")

    items: Mapped[list["CatalogItem"]] = relationship(back_populates="category")


class StoreSection(Base):
    """Poradi kategorie v konkretnim obchode (jak jde clovek uličkami)."""

    __tablename__ = "store_sections"
    __table_args__ = (UniqueConstraint("store_id", "category_id", name="uq_store_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=100)

    store: Mapped[Store] = relationship(back_populates="section_orders")
    category: Mapped[Category] = relationship()


class CatalogItem(Base):
    """Polozka katalogu (z PDF nebo rucne pridana)."""

    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    norm_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(120), default="")
    unit: Mapped[str] = mapped_column(String(32), default="ks")
    package: Mapped[str] = mapped_column(String(64), default="")
    ean: Mapped[str] = mapped_column(String(32), default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    category: Mapped[Category | None] = relationship(back_populates="items")
    prices: Mapped[list["Price"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class Price(Base):
    """Cena polozky v obchode, pripadne akcni cena z letaku."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"))
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    price: Mapped[float] = mapped_column(Float)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_discount: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[CatalogItem] = relationship(back_populates="prices")
    store: Mapped[Store | None] = relationship()

    @property
    def discount_pct(self) -> int | None:
        if self.original_price and self.original_price > 0 and self.price < self.original_price:
            return round((1 - self.price / self.original_price) * 100)
        return None


Index("ix_prices_item_valid", Price.item_id, Price.valid_to)


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=LIST_OPEN)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    shopper_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    store: Mapped[Store | None] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    shopper: Mapped[User | None] = relationship(foreign_keys=[shopper_id])
    items: Mapped[list["ListItem"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )

    @property
    def total_spent(self) -> float:
        return round(
            sum((i.bought_price or 0.0) for i in self.items if i.status == ITEM_BOUGHT), 2
        )

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.status != ITEM_TODO)


class ListItem(Base):
    __tablename__ = "list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(32), default="ks")
    note: Mapped[str] = mapped_column(String(255), default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ITEM_TODO)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_substitute: Mapped[bool] = mapped_column(Boolean, default=True)
    bought_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    bought_note: Mapped[str] = mapped_column(String(255), default="")
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    bought_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    bought_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    shopping_list: Mapped[ShoppingList] = relationship(back_populates="items")
    catalog_item: Mapped[CatalogItem | None] = relationship()
    category: Mapped[Category | None] = relationship()
    requested_by: Mapped[User | None] = relationship(foreign_keys=[requested_by_id])
    bought_by: Mapped[User | None] = relationship(foreign_keys=[bought_by_id])


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "catalog_item_id", name="uq_user_favorite"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE")
    )
    default_qty: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    catalog_item: Mapped[CatalogItem] = relationship()


class Purchase(Base):
    """Historie nakupu - zaklad pro doporuceni."""

    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="SET NULL"), nullable=True
    )
    norm_name: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    list_id: Mapped[int | None] = mapped_column(ForeignKey("shopping_lists.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(32), default="ks")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    bought_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)

    catalog_item: Mapped[CatalogItem | None] = relationship()
    store: Mapped[Store | None] = relationship()


class Document(Base):
    """Nahrane PDF - katalog nebo letak."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(20), default=DOC_KATALOG)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    valid_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=DOC_PARSED)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    store: Mapped[Store | None] = relationship()
    uploaded_by: Mapped[User | None] = relationship()
    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ImportRow(Base):
    """Radek vytazeny z PDF - ceka na potvrzeni pred zapsanim do katalogu."""

    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer, default=0)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    package: Mapped[str] = mapped_column(String(64), default="")
    unit: Mapped[str] = mapped_column(String(32), default="ks")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_discount: Mapped[bool] = mapped_column(Boolean, default=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    imported: Mapped[bool] = mapped_column(Boolean, default=False)
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id"), nullable=True
    )

    document: Mapped[Document] = relationship(back_populates="rows")
    category: Mapped[Category | None] = relationship()
