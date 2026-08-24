"""Katalog, slevy z letaku, oblibene polozky a historie."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import flash, redirect, render, require_user
from ..models import (
    LIST_DONE,
    LIST_OPEN,
    CatalogItem,
    Category,
    Favorite,
    Purchase,
    ShoppingList,
    Store,
    User,
)
from ..services import active_list, add_item_to_list, ensure_catalog_item, toggle_favorite
from ..suggestions import active_prices, catalog_search, deals, frequent_items
from ..text_utils import normalize

router = APIRouter()

PAGE_SIZE = 60


def _favorite_ids(db: Session, user: User) -> set[int]:
    return set(
        db.scalars(select(Favorite.catalog_item_id).where(Favorite.user_id == user.id)).all()
    )


def _target_list(db: Session, list_id: str | None) -> ShoppingList | None:
    if list_id and str(list_id).strip():
        return db.get(ShoppingList, int(list_id))
    return active_list(db)


@router.get("/katalog")
def catalog_view(
    request: Request,
    q: str = "",
    category_id: str = "",
    page: int = 1,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    statement = select(CatalogItem).where(CatalogItem.is_active.is_(True))
    needle = normalize(q)
    if needle:
        statement = statement.where(CatalogItem.norm_name.contains(needle))
    if category_id.strip():
        statement = statement.where(CatalogItem.category_id == int(category_id))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    page = max(page, 1)
    items = db.scalars(
        statement.options(selectinload(CatalogItem.category))
        .order_by(CatalogItem.name)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()

    return render(
        request,
        "catalog.html",
        user=user,
        items=items,
        total=total,
        page=page,
        pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
        q=q,
        category_id=category_id,
        categories=db.scalars(select(Category).order_by(Category.position)).all(),
        favorites=_favorite_ids(db, user),
        deal_prices=active_prices(db),
        lists=db.scalars(
            select(ShoppingList).where(ShoppingList.status != LIST_DONE)
            .order_by(desc(ShoppingList.updated_at)).limit(10)
        ).all(),
    )


@router.post("/katalog/nova")
def create_catalog_item(
    request: Request,
    name: str = Form(...),
    unit: str = Form("ks"),
    category_id: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    category = db.get(Category, int(category_id)) if category_id.strip() else None
    item = ensure_catalog_item(db, name.strip(), unit=unit.strip() or "ks", category=category)
    if item is None:
        flash(request, "Zadej název položky.", "error")
    else:
        flash(request, f"Položka '{item.name}' je v katalogu.")
    return redirect("/katalog")


@router.post("/katalog/{item_id}/upravit")
def update_catalog_item(
    item_id: int,
    request: Request,
    name: str = Form(""),
    unit: str = Form(""),
    category_id: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    item = db.get(CatalogItem, item_id)
    if item is None:
        raise HTTPException(404, "Položka nenalezena.")
    if name.strip():
        item.name = name.strip()[:255]
        item.norm_name = normalize(item.name)
    if unit.strip():
        item.unit = unit.strip()[:32]
    item.category_id = int(category_id) if category_id.strip() else None
    db.add(item)
    flash(request, "Položka upravena.")
    return redirect(request.headers.get("referer") or "/katalog")


@router.post("/katalog/{item_id}/oblibene")
def favorite_toggle(
    item_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    item = db.get(CatalogItem, item_id)
    if item is None:
        raise HTTPException(404, "Položka nenalezena.")
    added = toggle_favorite(db, user, item)
    flash(request, "Přidáno do oblíbených." if added else "Odebráno z oblíbených.")
    return redirect(request.headers.get("referer") or "/katalog")


@router.post("/katalog/{item_id}/na-seznam")
def add_catalog_item_to_list(
    item_id: int,
    request: Request,
    list_id: str = Form(""),
    qty: str = Form("1"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    item = db.get(CatalogItem, item_id)
    if item is None:
        raise HTTPException(404, "Položka nenalezena.")

    shopping_list = _target_list(db, list_id)
    if shopping_list is None:
        shopping_list = ShoppingList(
            title=f"Nákup {dt.date.today().strftime('%-d. %-m. %Y')}",
            created_by=user,
            status=LIST_OPEN,
        )
        db.add(shopping_list)
        db.flush()

    try:
        qty_value = float(qty.replace(",", ".")) if qty.strip() else 1.0
    except ValueError:
        qty_value = 1.0

    add_item_to_list(
        db, shopping_list, name=item.name, qty=qty_value, user=user, catalog_item_id=item.id
    )
    flash(request, f"'{item.name}' přidáno na seznam {shopping_list.title}.")
    return redirect(request.headers.get("referer") or f"/seznam/{shopping_list.id}")


@router.post("/rychle-pridat")
def quick_add(
    request: Request,
    name: str = Form(""),
    catalog_item_id: str = Form(""),
    list_id: str = Form(""),
    qty: str = Form("1"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Prida polozku na rozpracovany seznam; kdyz zadny neni, zalozi novy."""
    shopping_list = _target_list(db, list_id)
    if shopping_list is None or shopping_list.status == LIST_DONE:
        shopping_list = ShoppingList(
            title=f"Nákup {dt.date.today().strftime('%-d. %-m. %Y')}",
            created_by=user,
            status=LIST_OPEN,
        )
        db.add(shopping_list)
        db.flush()

    try:
        qty_value = float(qty.replace(",", ".")) if qty.strip() else 1.0
    except ValueError:
        qty_value = 1.0

    item = add_item_to_list(
        db,
        shopping_list,
        name=name,
        qty=qty_value,
        user=user,
        catalog_item_id=int(catalog_item_id) if catalog_item_id.strip() else None,
    )
    if item is None:
        flash(request, "Zadej název položky.", "error")
    else:
        flash(request, f"'{item.name}' přidáno na seznam {shopping_list.title}.")
    return redirect(request.headers.get("referer") or f"/seznam/{shopping_list.id}")


@router.get("/slevy")
def deals_view(
    request: Request,
    store_id: str = "",
    q: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    store = int(store_id) if store_id.strip() else None
    found = deals(db, store_id=store, query_text=q, limit=200)
    return render(
        request,
        "deals.html",
        user=user,
        deals=found,
        stores=db.scalars(select(Store).order_by(Store.name)).all(),
        store_id=store_id,
        q=q,
        favorites=_favorite_ids(db, user),
        lists=db.scalars(
            select(ShoppingList).where(ShoppingList.status != LIST_DONE)
            .order_by(desc(ShoppingList.updated_at)).limit(10)
        ).all(),
        today=dt.date.today(),
    )


@router.get("/oblibene")
def favorites_view(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    favorites = db.scalars(
        select(Favorite)
        .where(Favorite.user_id == user.id)
        .options(
            selectinload(Favorite.catalog_item).selectinload(CatalogItem.category)
        )
        .order_by(Favorite.created_at.desc())
    ).all()
    return render(
        request,
        "favorites.html",
        user=user,
        favorites=favorites,
        deal_prices=active_prices(db),
        lists=db.scalars(
            select(ShoppingList).where(ShoppingList.status != LIST_DONE)
            .order_by(desc(ShoppingList.updated_at)).limit(10)
        ).all(),
    )


@router.post("/oblibene/{favorite_id}/smazat")
def favorite_delete(
    favorite_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    favorite = db.get(Favorite, favorite_id)
    if favorite is None or favorite.user_id != user.id:
        raise HTTPException(404, "Oblíbená položka nenalezena.")
    db.delete(favorite)
    flash(request, "Odebráno z oblíbených.")
    return redirect("/oblibene")


@router.get("/historie")
def history_view(
    request: Request,
    q: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    statement = select(Purchase).options(selectinload(Purchase.store))
    needle = normalize(q)
    if needle:
        statement = statement.where(Purchase.norm_name.contains(needle))
    purchases = db.scalars(statement.order_by(Purchase.bought_at.desc()).limit(300)).all()

    monthly: dict[str, float] = {}
    for purchase in purchases:
        key = purchase.bought_at.strftime("%Y-%m")
        monthly[key] = round(monthly.get(key, 0.0) + (purchase.price or 0.0), 2)

    return render(
        request,
        "history.html",
        user=user,
        purchases=purchases,
        q=q,
        monthly=sorted(monthly.items(), reverse=True)[:12],
        frequent=frequent_items(db, limit=20, days=365),
    )


@router.get("/api/navrhy")
def suggest_api(
    q: str = "",
    limit: int = 10,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Naseptavac pro pole 'co koupit' - katalog + historie + oblibene."""
    items = catalog_search(db, q, limit=limit)
    prices = active_prices(db)
    favorites = _favorite_ids(db, user)

    results = []
    for item in items:
        price = prices.get(item.id)
        results.append(
            {
                "id": item.id,
                "name": item.name,
                "unit": item.unit,
                "package": item.package,
                "category": item.category.name if item.category else None,
                "favorite": item.id in favorites,
                "deal": None
                if price is None
                else {
                    "price": price.price,
                    "original": price.original_price,
                    "pct": price.discount_pct,
                    "store": price.store.name if price.store else None,
                },
            }
        )
    return {"items": results}
