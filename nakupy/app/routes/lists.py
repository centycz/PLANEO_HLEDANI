"""Nakupni seznamy - zadavatelska cast."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import flash, redirect, render, require_user
from ..models import (
    ITEM_STATES,
    LIST_DONE,
    LIST_OPEN,
    Category,
    ListItem,
    ShoppingList,
    Store,
    User,
)
from ..services import add_item_to_list, finish_list, naive_utcnow
from ..suggestions import (
    active_prices,
    favorite_suggestions,
    frequent_items,
    group_by_section,
    list_progress,
)
from ..text_utils import normalize

router = APIRouter()


def _load_list(db: Session, list_id: int) -> ShoppingList:
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.id == list_id)
        .options(
            selectinload(ShoppingList.items).selectinload(ListItem.catalog_item),
            selectinload(ShoppingList.items).selectinload(ListItem.category),
            selectinload(ShoppingList.items).selectinload(ListItem.requested_by),
            selectinload(ShoppingList.items).selectinload(ListItem.bought_by),
            selectinload(ShoppingList.store),
            selectinload(ShoppingList.created_by),
            selectinload(ShoppingList.shopper),
        )
    )
    if shopping_list is None:
        raise HTTPException(404, "Seznam nenalezen.")
    return shopping_list


@router.get("/seznamy")
def lists_overview(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    lists = db.scalars(
        select(ShoppingList)
        .options(selectinload(ShoppingList.items), selectinload(ShoppingList.store))
        .order_by(ShoppingList.status == LIST_DONE, ShoppingList.updated_at.desc())
        .limit(60)
    ).all()
    stores = db.scalars(select(Store).where(Store.is_active.is_(True)).order_by(Store.name)).all()
    return render(
        request,
        "lists.html",
        user=user,
        lists=lists,
        stores=stores,
        progress={sl.id: list_progress(sl) for sl in lists},
    )


@router.post("/seznamy/novy")
def create_list(
    request: Request,
    title: str = Form(""),
    store_id: str = Form(""),
    budget: str = Form(""),
    note: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    title = title.strip() or f"Nákup {dt.date.today().strftime('%-d. %-m. %Y')}"
    try:
        budget_value = float(budget.replace(",", ".")) if budget.strip() else None
    except ValueError:
        budget_value = None

    shopping_list = ShoppingList(
        title=title[:160],
        store_id=int(store_id) if store_id.strip() else None,
        budget=budget_value,
        note=note.strip(),
        created_by=user,
        status=LIST_OPEN,
    )
    db.add(shopping_list)
    db.flush()
    flash(request, "Seznam založen. Teď do něj přidej, co je potřeba koupit.")
    return redirect(f"/seznam/{shopping_list.id}")


@router.get("/seznam/{list_id}")
def list_detail(
    list_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    shopping_list = _load_list(db, list_id)
    on_list = {normalize(item.name) for item in shopping_list.items}

    return render(
        request,
        "list_detail.html",
        user=user,
        list=shopping_list,
        grouped=group_by_section(db, shopping_list),
        progress=list_progress(shopping_list),
        stores=db.scalars(select(Store).where(Store.is_active.is_(True)).order_by(Store.name)).all(),
        categories=db.scalars(select(Category).order_by(Category.position)).all(),
        users=db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.display_name)).all(),
        suggestions=frequent_items(db, limit=8, exclude_norm=on_list),
        favorites=favorite_suggestions(db, user.id, exclude_norm=on_list, limit=12),
        deal_prices=active_prices(db, store_id=shopping_list.store_id),
        item_states=ITEM_STATES,
    )


@router.post("/seznam/{list_id}/pridat")
def add_item(
    list_id: int,
    request: Request,
    name: str = Form(""),
    qty: str = Form("1"),
    unit: str = Form(""),
    note: str = Form(""),
    catalog_item_id: str = Form(""),
    is_urgent: str = Form(""),
    allow_substitute: str = Form("on"),
    redirect_to: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    shopping_list = _load_list(db, list_id)
    if shopping_list.status == LIST_DONE:
        flash(request, "Dokončený nákup už nejde měnit. Založ nový seznam.", "error")
        return redirect(f"/seznam/{list_id}")

    try:
        qty_value = float(qty.replace(",", ".")) if qty.strip() else 1.0
    except ValueError:
        qty_value = 1.0

    item = add_item_to_list(
        db,
        shopping_list,
        name=name,
        qty=qty_value,
        unit=unit.strip(),
        note=note.strip(),
        user=user,
        catalog_item_id=int(catalog_item_id) if catalog_item_id.strip() else None,
        is_urgent=bool(is_urgent),
        allow_substitute=bool(allow_substitute),
    )
    if item is None:
        flash(request, "Zadej název položky.", "error")
    else:
        flash(request, f"Přidáno: {item.name}")
    return redirect(redirect_to or f"/seznam/{list_id}")


@router.post("/seznam/{list_id}/hromadne")
def add_bulk(
    list_id: int,
    request: Request,
    text: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Vlozeni vice polozek najednou - jedna polozka na radek ('2x mleko')."""
    shopping_list = _load_list(db, list_id)
    added = 0
    for line in (text or "").splitlines():
        line = line.strip(" -•\t")
        if not line:
            continue
        qty = 1.0
        parts = line.split(None, 1)
        if len(parts) == 2:
            head = parts[0].lower().rstrip("xks×").replace(",", ".")
            try:
                qty = float(head)
                line = parts[1].strip()
            except ValueError:
                qty = 1.0
        if add_item_to_list(db, shopping_list, name=line, qty=qty, user=user):
            added += 1
    flash(request, f"Přidáno {added} položek." if added else "Nic k přidání.", "ok" if added else "error")
    return redirect(f"/seznam/{list_id}")


@router.post("/polozka/{item_id}/upravit")
def edit_item(
    item_id: int,
    request: Request,
    qty: str = Form("1"),
    unit: str = Form(""),
    note: str = Form(""),
    category_id: str = Form(""),
    is_urgent: str = Form(""),
    allow_substitute: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    item = db.get(ListItem, item_id)
    if item is None:
        raise HTTPException(404, "Položka nenalezena.")
    try:
        item.qty = float(qty.replace(",", ".")) if qty.strip() else 1.0
    except ValueError:
        pass
    item.unit = unit.strip()[:32] or item.unit
    item.note = note.strip()[:255]
    item.category_id = int(category_id) if category_id.strip() else None
    item.is_urgent = bool(is_urgent)
    item.allow_substitute = bool(allow_substitute)
    item.shopping_list.updated_at = naive_utcnow()
    db.add(item)
    flash(request, "Položka upravena.")
    return redirect(f"/seznam/{item.list_id}")


@router.post("/polozka/{item_id}/smazat")
def delete_item(
    item_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    item = db.get(ListItem, item_id)
    if item is None:
        raise HTTPException(404, "Položka nenalezena.")
    list_id = item.list_id
    db.delete(item)
    flash(request, "Položka smazána.")
    return redirect(f"/seznam/{list_id}")


@router.post("/seznam/{list_id}/nastaveni")
def update_list(
    list_id: int,
    request: Request,
    title: str = Form(""),
    store_id: str = Form(""),
    shopper_id: str = Form(""),
    budget: str = Form(""),
    note: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    shopping_list = _load_list(db, list_id)
    if title.strip():
        shopping_list.title = title.strip()[:160]
    shopping_list.store_id = int(store_id) if store_id.strip() else None
    shopping_list.shopper_id = int(shopper_id) if shopper_id.strip() else None
    try:
        shopping_list.budget = float(budget.replace(",", ".")) if budget.strip() else None
    except ValueError:
        pass
    shopping_list.note = note.strip()
    shopping_list.updated_at = naive_utcnow()
    db.add(shopping_list)
    flash(request, "Seznam upraven.")
    return redirect(f"/seznam/{list_id}")


@router.post("/seznam/{list_id}/dokoncit")
def close_list(
    list_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    shopping_list = _load_list(db, list_id)
    recorded = finish_list(db, shopping_list, user)
    flash(request, f"Nákup dokončen, do historie zapsáno {recorded} položek.")
    return redirect(f"/seznam/{list_id}")


@router.post("/seznam/{list_id}/znovu")
def reopen_list(
    list_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    shopping_list = _load_list(db, list_id)
    shopping_list.status = LIST_OPEN
    shopping_list.finished_at = None
    shopping_list.updated_at = naive_utcnow()
    db.add(shopping_list)
    flash(request, "Seznam znovu otevřen. Historie nákupu zůstává zapsaná.")
    return redirect(f"/seznam/{list_id}")


@router.post("/seznam/{list_id}/smazat")
def delete_list(
    list_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    shopping_list = _load_list(db, list_id)
    db.delete(shopping_list)
    flash(request, "Seznam smazán.")
    return redirect("/seznamy")


@router.post("/seznam/{list_id}/zkopirovat")
def copy_list(
    list_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    """Zalozi novy seznam z nekoupenych polozek (a z celeho, pokud vse koupeno)."""
    source = _load_list(db, list_id)
    new_list = ShoppingList(
        title=f"{source.title} (znovu)",
        store_id=source.store_id,
        budget=source.budget,
        created_by=user,
        status=LIST_OPEN,
    )
    db.add(new_list)
    db.flush()

    pending = [i for i in source.items if i.status != "bought"]
    for item in pending or source.items:
        add_item_to_list(
            db,
            new_list,
            name=item.name,
            qty=item.qty,
            unit=item.unit,
            note=item.note,
            user=user,
            catalog_item_id=item.catalog_item_id,
            merge=False,
        )
    flash(request, "Nový seznam vytvořen.")
    return redirect(f"/seznam/{new_list.id}")


@router.get("/api/seznam/{list_id}/stav")
def list_state(list_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Pouziva stranka seznamu pro prubezne obnoveni behem nakupu."""
    shopping_list = _load_list(db, list_id)
    return {
        "status": shopping_list.status,
        "updated_at": shopping_list.updated_at.isoformat(),
        **list_progress(shopping_list),
        "items": [
            {"id": i.id, "name": i.name, "status": i.status, "price": i.bought_price}
            for i in shopping_list.items
        ],
    }
