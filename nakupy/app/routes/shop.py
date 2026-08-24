"""Rezim nakupciho - prochazeni obchodu podle useku."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import flash, redirect, render, require_user
from ..models import (
    ITEM_BOUGHT,
    ITEM_MISSING,
    ITEM_STATES,
    ITEM_TODO,
    LIST_DONE,
    Category,
    ListItem,
    ShoppingList,
    User,
)
from ..services import add_item_to_list, finish_list, mark_item, start_shopping
from ..suggestions import active_prices, group_by_section, list_progress

router = APIRouter()


def _load_list(db: Session, list_id: int) -> ShoppingList:
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.id == list_id)
        .options(
            selectinload(ShoppingList.items).selectinload(ListItem.catalog_item),
            selectinload(ShoppingList.items).selectinload(ListItem.category),
            selectinload(ShoppingList.store),
        )
    )
    if shopping_list is None:
        raise HTTPException(404, "Seznam nenalezen.")
    return shopping_list


def _is_ajax(request: Request) -> bool:
    return request.headers.get("x-ajax") == "1"


@router.get("/nakup/{list_id}")
def shop_view(
    list_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    shopping_list = _load_list(db, list_id)
    if shopping_list.status != LIST_DONE:
        start_shopping(shopping_list, user)
        db.add(shopping_list)

    return render(
        request,
        "shop.html",
        user=user,
        list=shopping_list,
        grouped=group_by_section(db, shopping_list),
        progress=list_progress(shopping_list),
        deal_prices=active_prices(db, store_id=shopping_list.store_id),
        categories=db.scalars(select(Category).order_by(Category.position)).all(),
        item_states=ITEM_STATES,
    )


@router.post("/nakup/polozka/{item_id}/stav")
def set_status(
    item_id: int,
    request: Request,
    status: str = Form(ITEM_BOUGHT),
    price: str = Form(""),
    note: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    item = db.get(ListItem, item_id)
    if item is None:
        raise HTTPException(404, "Položka nenalezena.")
    if status not in ITEM_STATES:
        raise HTTPException(400, "Neznámý stav položky.")

    price_value: float | None = None
    if price.strip():
        try:
            price_value = round(float(price.replace(",", ".")), 2)
        except ValueError:
            price_value = None

    mark_item(db, item, status, user=user, price=price_value, note=note.strip() or None)
    db.flush()

    if _is_ajax(request):
        progress = list_progress(item.shopping_list)
        return JSONResponse(
            {
                "ok": True,
                "id": item.id,
                "status": item.status,
                "price": item.bought_price,
                "progress": progress,
            }
        )
    return redirect(f"/nakup/{item.list_id}")


@router.post("/nakup/{list_id}/pridat")
def add_extra(
    list_id: int,
    request: Request,
    name: str = Form(""),
    qty: str = Form("1"),
    price: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Nakupci koupil neco navic, co na seznamu nebylo."""
    shopping_list = _load_list(db, list_id)
    try:
        qty_value = float(qty.replace(",", ".")) if qty.strip() else 1.0
    except ValueError:
        qty_value = 1.0

    item = add_item_to_list(
        db, shopping_list, name=name, qty=qty_value, user=user, note="přidal nákupčí"
    )
    if item is None:
        flash(request, "Zadej název položky.", "error")
        return redirect(f"/nakup/{list_id}")

    price_value = None
    if price.strip():
        try:
            price_value = round(float(price.replace(",", ".")), 2)
        except ValueError:
            price_value = None
    db.flush()
    mark_item(db, item, ITEM_BOUGHT, user=user, price=price_value)
    flash(request, f"Přidáno a označeno jako koupené: {item.name}")
    return redirect(f"/nakup/{list_id}")


@router.post("/nakup/{list_id}/dokoncit")
def finish(
    list_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    shopping_list = _load_list(db, list_id)
    remaining = [i for i in shopping_list.items if i.status == ITEM_TODO]
    for item in remaining:
        item.status = ITEM_MISSING
        item.bought_note = item.bought_note or "nevyřízeno při dokončení"
    recorded = finish_list(db, shopping_list, user)
    flash(
        request,
        f"Nákup uzavřen: {recorded} položek do historie"
        + (f", {len(remaining)} nevyřízeno." if remaining else "."),
    )
    return redirect(f"/seznam/{list_id}")
