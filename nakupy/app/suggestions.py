"""Doporuceni podle historie nakupu, aktivni slevy a razeni podle obchodu."""
from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    ITEM_TODO,
    Category,
    CatalogItem,
    Favorite,
    ListItem,
    Price,
    Purchase,
    ShoppingList,
    StoreSection,
)
from .text_utils import normalize


@dataclass
class Suggestion:
    """Polozka, kterou uzivatel nakupuje pravidelne."""

    name: str
    norm_name: str
    catalog_item_id: int | None
    unit: str
    count: int
    last_bought: dt.datetime | None
    avg_interval_days: float | None
    days_since: int | None
    is_due: bool
    score: float
    reason: str


def _reason(count: int, days_since: int | None, avg: float | None, is_due: bool) -> str:
    if is_due and avg:
        return f"kupujete zhruba každých {round(avg)} dní, naposledy před {days_since} dny"
    if days_since is None:
        return f"koupeno {count}×"
    return f"koupeno {count}×, naposledy před {days_since} dny"


def frequent_items(
    session: Session,
    *,
    days: int = 180,
    limit: int = 12,
    user_id: int | None = None,
    exclude_norm: set[str] | None = None,
) -> list[Suggestion]:
    """Nejcasteji nakupovane polozky z historie, serazene podle 'je cas koupit'."""
    since = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=days)
    query = select(Purchase).where(Purchase.bought_at >= since)
    if user_id is not None:
        query = query.where(or_(Purchase.user_id == user_id, Purchase.user_id.is_(None)))

    grouped: dict[str, list[Purchase]] = {}
    for purchase in session.scalars(query).all():
        grouped.setdefault(purchase.norm_name, []).append(purchase)

    exclude = exclude_norm or set()
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    suggestions: list[Suggestion] = []

    for norm_name, purchases in grouped.items():
        if not norm_name or norm_name in exclude:
            continue
        purchases.sort(key=lambda p: p.bought_at)
        count = len(purchases)
        last = purchases[-1].bought_at
        days_since = max((now - last).days, 0)

        avg_interval: float | None = None
        if count >= 2:
            gaps = [
                (b.bought_at - a.bought_at).days
                for a, b in zip(purchases, purchases[1:])
                if (b.bought_at - a.bought_at).days > 0
            ]
            if gaps:
                avg_interval = statistics.median(gaps)

        is_due = bool(avg_interval and days_since >= avg_interval * 0.8)
        # cim castejsi nakup a cim blizsi obvyklemu intervalu, tim vys
        score = count * 1.0
        if avg_interval:
            score += min(days_since / avg_interval, 3.0) * 4.0
        else:
            score += min(days_since / 30.0, 2.0)

        latest = purchases[-1]
        suggestions.append(
            Suggestion(
                name=latest.name,
                norm_name=norm_name,
                catalog_item_id=latest.catalog_item_id,
                unit=latest.unit or "ks",
                count=count,
                last_bought=last,
                avg_interval_days=avg_interval,
                days_since=days_since,
                is_due=is_due,
                score=round(score, 2),
                reason=_reason(count, days_since, avg_interval, is_due),
            )
        )

    suggestions.sort(key=lambda s: (s.is_due, s.score), reverse=True)
    return suggestions[:limit]


def favorite_suggestions(
    session: Session, user_id: int, *, exclude_norm: set[str] | None = None, limit: int = 30
) -> list[Favorite]:
    query = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .options(selectinload(Favorite.catalog_item).selectinload(CatalogItem.category))
        .order_by(Favorite.created_at.desc())
    )
    favorites = session.scalars(query).all()
    exclude = exclude_norm or set()
    return [f for f in favorites if f.catalog_item and f.catalog_item.norm_name not in exclude][
        :limit
    ]


def active_prices(
    session: Session, *, store_id: int | None = None, discounts_only: bool = True
) -> dict[int, Price]:
    """Aktualne platne ceny/slevy podle item_id (nejnizsi cena vyhrava)."""
    today = dt.date.today()
    query = select(Price).options(selectinload(Price.store), selectinload(Price.item))
    if discounts_only:
        query = query.where(Price.is_discount.is_(True))
    if store_id:
        query = query.where(or_(Price.store_id == store_id, Price.store_id.is_(None)))

    best: dict[int, Price] = {}
    for price in session.scalars(query).all():
        if price.valid_from and price.valid_from > today:
            continue
        if price.valid_to and price.valid_to < today:
            continue
        current = best.get(price.item_id)
        if current is None or price.price < current.price:
            best[price.item_id] = price
    return best


def deals(
    session: Session, *, store_id: int | None = None, limit: int = 60, query_text: str = ""
) -> list[Price]:
    """Seznam aktualnich slev serazeny podle vyse slevy."""
    found = list(active_prices(session, store_id=store_id, discounts_only=True).values())
    if query_text:
        needle = normalize(query_text)
        found = [p for p in found if p.item and needle in p.item.norm_name]
    found.sort(key=lambda p: (p.discount_pct or 0), reverse=True)
    return found[:limit]


def category_order(session: Session, store_id: int | None) -> dict[int, int]:
    """Poradi kategorii pro dany obchod (fallback = globalni poradi kategorie)."""
    order = {
        category.id: category.position
        for category in session.scalars(select(Category)).all()
    }
    if store_id:
        for section in session.scalars(
            select(StoreSection).where(StoreSection.store_id == store_id)
        ).all():
            order[section.category_id] = section.position
    return order


def group_by_section(
    session: Session, shopping_list: ShoppingList
) -> list[tuple[Category | None, list[ListItem]]]:
    """Rozdeli polozky seznamu do useku obchodu ve smeru prochazeni."""
    order = category_order(session, shopping_list.store_id)
    buckets: dict[int | None, list[ListItem]] = {}
    categories: dict[int | None, Category | None] = {}

    for item in shopping_list.items:
        category = item.category or (item.catalog_item.category if item.catalog_item else None)
        key = category.id if category else None
        buckets.setdefault(key, []).append(item)
        categories[key] = category

    def sort_key(entry: tuple[int | None, list[ListItem]]) -> tuple[int, str]:
        key = entry[0]
        if key is None:
            return (10_000, "")
        category = categories.get(key)
        return (order.get(key, 999), category.name if category else "")

    grouped: list[tuple[Category | None, list[ListItem]]] = []
    for key, items in sorted(buckets.items(), key=sort_key):
        items.sort(key=lambda i: (i.status != ITEM_TODO, not i.is_urgent, i.name.lower()))
        grouped.append((categories.get(key), items))
    return grouped


def list_progress(shopping_list: ShoppingList) -> dict[str, float | int]:
    total = len(shopping_list.items)
    done = sum(1 for item in shopping_list.items if item.status != ITEM_TODO)
    return {
        "total": total,
        "done": done,
        "todo": total - done,
        "pct": round(done / total * 100) if total else 0,
        "spent": shopping_list.total_spent,
    }


def catalog_search(
    session: Session, query_text: str, *, limit: int = 20, category_id: int | None = None
) -> list[CatalogItem]:
    statement = select(CatalogItem).where(CatalogItem.is_active.is_(True))
    needle = normalize(query_text)
    if needle:
        statement = statement.where(CatalogItem.norm_name.contains(needle))
    if category_id:
        statement = statement.where(CatalogItem.category_id == category_id)
    statement = statement.options(selectinload(CatalogItem.category)).order_by(
        func.length(CatalogItem.name), CatalogItem.name
    ).limit(limit)
    return list(session.scalars(statement).all())
