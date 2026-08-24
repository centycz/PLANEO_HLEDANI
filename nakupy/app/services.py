"""Operace nad seznamy, katalogem a historii."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ITEM_BOUGHT,
    ITEM_TODO,
    LIST_DONE,
    LIST_SHOPPING,
    Category,
    CatalogItem,
    Favorite,
    ListItem,
    Price,
    Purchase,
    ShoppingList,
    User,
    utcnow,
)
from .text_utils import default_unit, extract_unit, guess_category_name, normalize


def naive_utcnow() -> dt.datetime:
    return utcnow().replace(tzinfo=None)


def category_by_name(session: Session, name: str | None) -> Category | None:
    if not name:
        return None
    return session.scalar(select(Category).where(Category.name == name))


def guess_category(session: Session, text: str) -> Category | None:
    return category_by_name(session, guess_category_name(text))


def find_similar_catalog_item(session: Session, name: str) -> CatalogItem | None:
    """Napoji zkraceny nazev na polozku katalogu, kdyz je jednoznacna.

    Uzivatel napise "Jogurt bily Hollandia", v katalogu z letaku je
    "Jogurt bily Hollandia 400 g" - diky tomu se u polozky ukaze akcni cena.
    Kdyz odpovida vic polozek, radeji nespojujeme nic.
    """
    norm = normalize(name)
    if len(norm) < 6:
        return None
    candidates = session.scalars(
        select(CatalogItem)
        .where(CatalogItem.norm_name.startswith(norm), CatalogItem.is_active.is_(True))
        .limit(3)
    ).all()
    return candidates[0] if len(candidates) == 1 else None


def ensure_catalog_item(
    session: Session,
    name: str,
    *,
    unit: str | None = None,
    package: str = "",
    category: Category | None = None,
    create: bool = True,
) -> CatalogItem | None:
    """Najde polozku katalogu podle normalizovaneho nazvu, pripadne ji zalozi."""
    norm = normalize(name)
    if not norm:
        return None
    item = session.scalar(select(CatalogItem).where(CatalogItem.norm_name == norm))
    if item is None:
        item = find_similar_catalog_item(session, name)
    if item or not create:
        return item

    detected_package, _detected_unit = extract_unit(name)
    item = CatalogItem(
        name=name.strip()[:255],
        norm_name=norm,
        unit=unit or default_unit(name),
        package=package or detected_package,
        category=category or guess_category(session, name),
    )
    session.add(item)
    session.flush()
    return item


def add_item_to_list(
    session: Session,
    shopping_list: ShoppingList,
    *,
    name: str,
    qty: float = 1.0,
    unit: str = "",
    note: str = "",
    user: User | None = None,
    catalog_item_id: int | None = None,
    is_urgent: bool = False,
    allow_substitute: bool = True,
    merge: bool = True,
) -> ListItem | None:
    """Prida polozku na seznam; stejnou polozku radeji secte, nez zdvoji."""
    name = (name or "").strip()
    catalog_item: CatalogItem | None = None
    if catalog_item_id:
        catalog_item = session.get(CatalogItem, catalog_item_id)
        if catalog_item and not name:
            name = catalog_item.name
    if not name:
        return None
    if catalog_item is None:
        catalog_item = ensure_catalog_item(session, name)

    norm = normalize(name)
    if merge:
        for existing in shopping_list.items:
            if existing.status == ITEM_TODO and normalize(existing.name) == norm:
                existing.qty = round((existing.qty or 0) + qty, 3)
                if note and note not in existing.note:
                    existing.note = f"{existing.note} {note}".strip()
                return existing

    item = ListItem(
        shopping_list=shopping_list,
        catalog_item=catalog_item,
        name=name[:255],
        qty=qty or 1.0,
        unit=(unit or (catalog_item.unit if catalog_item else "") or default_unit(name))[:32],
        note=note[:255],
        category=(catalog_item.category if catalog_item else None) or guess_category(session, name),
        requested_by=user,
        is_urgent=is_urgent,
        allow_substitute=allow_substitute,
    )
    session.add(item)
    shopping_list.updated_at = naive_utcnow()
    return item


def mark_item(
    session: Session,
    item: ListItem,
    status: str,
    *,
    user: User | None = None,
    price: float | None = None,
    note: str | None = None,
) -> ListItem:
    item.status = status
    if note is not None:
        item.bought_note = note[:255]
    if status == ITEM_BOUGHT:
        item.bought_by = user
        item.bought_at = naive_utcnow()
        if price is not None:
            item.bought_price = price
    elif status == ITEM_TODO:
        item.bought_by = None
        item.bought_at = None
        item.bought_price = None
    item.shopping_list.updated_at = naive_utcnow()
    if item.shopping_list.status == "open" and status != ITEM_TODO:
        start_shopping(item.shopping_list, user)
    return item


def start_shopping(shopping_list: ShoppingList, user: User | None = None) -> ShoppingList:
    if shopping_list.status != LIST_SHOPPING:
        shopping_list.status = LIST_SHOPPING
        shopping_list.started_at = shopping_list.started_at or naive_utcnow()
    if user and shopping_list.shopper_id is None:
        shopping_list.shopper = user
    return shopping_list


def finish_list(session: Session, shopping_list: ShoppingList, user: User | None = None) -> int:
    """Uzavre nakup a zapise koupene polozky do historie."""
    if shopping_list.status == LIST_DONE:
        return 0

    recorded = 0
    for item in shopping_list.items:
        if item.status != ITEM_BOUGHT:
            continue
        catalog_item = item.catalog_item or ensure_catalog_item(session, item.name)
        session.add(
            Purchase(
                catalog_item=catalog_item,
                norm_name=normalize(item.name),
                name=item.name,
                store_id=shopping_list.store_id,
                list_id=shopping_list.id,
                user_id=(item.requested_by_id or shopping_list.created_by_id),
                qty=item.qty or 1.0,
                unit=item.unit or "ks",
                price=item.bought_price,
                bought_at=item.bought_at or naive_utcnow(),
            )
        )
        if catalog_item and item.bought_price:
            session.add(
                Price(
                    item_id=catalog_item.id,
                    store_id=shopping_list.store_id,
                    price=item.bought_price,
                    is_discount=False,
                    note="účtenka",
                )
            )
        recorded += 1

    shopping_list.status = LIST_DONE
    shopping_list.finished_at = naive_utcnow()
    if user and shopping_list.shopper_id is None:
        shopping_list.shopper = user
    return recorded


def toggle_favorite(session: Session, user: User, catalog_item: CatalogItem) -> bool:
    """Vrati True, pokud je polozka po prepnuti mezi oblibenymi."""
    favorite = session.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id, Favorite.catalog_item_id == catalog_item.id
        )
    )
    if favorite:
        session.delete(favorite)
        return False
    session.add(Favorite(user_id=user.id, catalog_item_id=catalog_item.id))
    return True


def active_list(session: Session) -> ShoppingList | None:
    """Posledni rozpracovany seznam."""
    return session.scalar(
        select(ShoppingList)
        .where(ShoppingList.status != LIST_DONE)
        .order_by(ShoppingList.updated_at.desc())
    )
