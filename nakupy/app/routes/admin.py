"""Nastaveni - uzivatele, obchody, kategorie a rozlozeni obchodu."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import flash, redirect, render, require_admin, require_user
from ..models import (
    ROLE_OBOJI,
    ROLES,
    CatalogItem,
    Category,
    Price,
    Purchase,
    Store,
    StoreSection,
    User,
)
from ..security import hash_password

router = APIRouter()


@router.get("/nastaveni")
def settings_view(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    return render(
        request,
        "settings.html",
        user=user,
        users=db.scalars(select(User).order_by(User.display_name)).all(),
        stores=db.scalars(select(Store).order_by(Store.name)).all(),
        categories=db.scalars(select(Category).order_by(Category.position)).all(),
        roles=ROLES,
        stats={
            "catalog": db.scalar(select(func.count(CatalogItem.id))) or 0,
            "prices": db.scalar(select(func.count(Price.id))) or 0,
            "purchases": db.scalar(select(func.count(Purchase.id))) or 0,
        },
    )


# --- uzivatele ------------------------------------------------------------
@router.post("/nastaveni/uzivatel")
def create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(""),
    password: str = Form(...),
    role: str = Form(ROLE_OBOJI),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    if not username or len(password) < 6:
        flash(request, "Zadej přihlašovací jméno a heslo aspoň o 6 znacích.", "error")
        return redirect("/nastaveni")
    if db.scalar(select(User).where(User.username == username)):
        flash(request, "Uživatel s tímto jménem už existuje.", "error")
        return redirect("/nastaveni")

    db.add(
        User(
            username=username[:64],
            display_name=(display_name.strip() or username)[:120],
            password_hash=hash_password(password),
            role=role if role in ROLES else ROLE_OBOJI,
        )
    )
    flash(request, f"Uživatel {username} vytvořen.")
    return redirect("/nastaveni")


@router.post("/nastaveni/uzivatel/{user_id}")
def update_user(
    user_id: int,
    request: Request,
    display_name: str = Form(""),
    role: str = Form(ROLE_OBOJI),
    is_active: str = Form(""),
    new_password: str = Form(""),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "Uživatel nenalezen.")

    if display_name.strip():
        target.display_name = display_name.strip()[:120]
    if role in ROLES:
        target.role = role
    target.is_active = bool(is_active)
    if target.id == admin.id and not target.is_active:
        target.is_active = True
        flash(request, "Vlastní účet nejde deaktivovat.", "error")
    if new_password.strip():
        if len(new_password) < 6:
            flash(request, "Heslo musí mít aspoň 6 znaků.", "error")
        else:
            target.password_hash = hash_password(new_password)
            flash(request, f"Heslo uživatele {target.username} změněno.")
    db.add(target)
    return redirect("/nastaveni")


# --- obchody --------------------------------------------------------------
@router.post("/nastaveni/obchod")
def create_store(
    request: Request,
    name: str = Form(...),
    note: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if not name:
        flash(request, "Zadej název obchodu.", "error")
    elif db.scalar(select(Store).where(Store.name == name)):
        flash(request, "Takový obchod už existuje.", "error")
    else:
        db.add(Store(name=name[:120], note=note.strip()[:255]))
        flash(request, f"Obchod {name} přidán.")
    return redirect("/nastaveni")


@router.post("/nastaveni/obchod/{store_id}")
def update_store(
    store_id: int,
    request: Request,
    name: str = Form(""),
    note: str = Form(""),
    is_active: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(404, "Obchod nenalezen.")
    if name.strip():
        store.name = name.strip()[:120]
    store.note = note.strip()[:255]
    store.is_active = bool(is_active)
    db.add(store)
    flash(request, "Obchod upraven.")
    return redirect("/nastaveni")


# --- kategorie ------------------------------------------------------------
@router.post("/nastaveni/kategorie")
def create_category(
    request: Request,
    name: str = Form(...),
    icon: str = Form("🛒"),
    position: str = Form("100"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if not name:
        flash(request, "Zadej název kategorie.", "error")
    elif db.scalar(select(Category).where(Category.name == name)):
        flash(request, "Kategorie už existuje.", "error")
    else:
        try:
            pos = int(position)
        except ValueError:
            pos = 100
        db.add(Category(name=name[:120], icon=(icon or "🛒")[:16], position=pos))
        flash(request, f"Kategorie {name} přidána.")
    return redirect("/nastaveni")


@router.post("/nastaveni/kategorie/poradi")
async def reorder_categories(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    """Globalni poradi kategorii = vychozi trasa obchodem."""
    form = await request.form()
    for category in db.scalars(select(Category)).all():
        raw = form.get(f"position_{category.id}")
        if raw is None:
            continue
        try:
            category.position = int(str(raw))
        except ValueError:
            continue
        db.add(category)
    flash(request, "Pořadí úseků uloženo.")
    return redirect("/nastaveni")


# --- rozlozeni konkretniho obchodu ---------------------------------------
@router.get("/nastaveni/rozlozeni/{store_id}")
def store_layout(
    store_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(404, "Obchod nenalezen.")

    categories = db.scalars(select(Category).order_by(Category.position)).all()
    sections = {
        section.category_id: section
        for section in db.scalars(
            select(StoreSection).where(StoreSection.store_id == store_id)
        ).all()
    }
    rows = sorted(
        (
            {
                "category": category,
                "position": sections[category.id].position
                if category.id in sections
                else category.position,
                "custom": category.id in sections,
            }
            for category in categories
        ),
        key=lambda row: row["position"],
    )
    return render(request, "store_layout.html", user=user, store=store, rows=rows)


@router.post("/nastaveni/rozlozeni/{store_id}")
async def save_store_layout(
    store_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(404, "Obchod nenalezen.")

    form = await request.form()
    sections = {
        section.category_id: section
        for section in db.scalars(
            select(StoreSection).where(StoreSection.store_id == store_id)
        ).all()
    }
    for category in db.scalars(select(Category)).all():
        raw = form.get(f"position_{category.id}")
        if raw is None:
            continue
        try:
            position = int(str(raw))
        except ValueError:
            continue
        section = sections.get(category.id)
        if section is None:
            db.add(
                StoreSection(store_id=store_id, category_id=category.id, position=position)
            )
        else:
            section.position = position
            db.add(section)
    flash(request, f"Trasa obchodem {store.name} uložena.")
    return redirect(f"/nastaveni/rozlozeni/{store_id}")


@router.post("/nastaveni/rozlozeni/{store_id}/vychozi")
def reset_store_layout(
    store_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    for section in db.scalars(
        select(StoreSection).where(StoreSection.store_id == store_id)
    ).all():
        db.delete(section)
    flash(request, "Trasa obchodem vrácena na výchozí pořadí.")
    return redirect(f"/nastaveni/rozlozeni/{store_id}")
