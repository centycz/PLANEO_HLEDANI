"""Prihlaseni a odhlaseni."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, flash, redirect, render, require_user
from ..models import User
from ..security import hash_password, verify_password

router = APIRouter()


@router.get("/prihlaseni")
def login_form(request: Request, next: str = "/", user: User | None = Depends(current_user)):
    if user:
        return redirect("/")
    return render(request, "login.html", next_url=next)


@router.post("/prihlaseni")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        flash(request, "Špatné jméno nebo heslo.", "error")
        return redirect(f"/prihlaseni?next={next}")

    request.session.clear()
    request.session["user_id"] = user.id
    flash(request, f"Vítej zpátky, {user.display_name}!")
    return redirect(next if next.startswith("/") else "/")


@router.get("/odhlaseni")
def logout(request: Request):
    request.session.clear()
    return redirect("/prihlaseni")


@router.get("/ucet")
def account(request: Request, user: User = Depends(require_user)):
    return render(request, "account.html", user=user)


@router.post("/ucet/heslo")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not verify_password(current_password, user.password_hash):
        flash(request, "Současné heslo nesouhlasí.", "error")
    elif len(new_password) < 6:
        flash(request, "Nové heslo musí mít aspoň 6 znaků.", "error")
    elif new_password != new_password2:
        flash(request, "Nová hesla se neshodují.", "error")
    else:
        user.password_hash = hash_password(new_password)
        db.add(user)
        flash(request, "Heslo změněno.")
    return redirect("/ucet")


@router.post("/ucet/jmeno")
def change_name(
    request: Request,
    display_name: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    display_name = display_name.strip()
    if display_name:
        user.display_name = display_name[:120]
        db.add(user)
        flash(request, "Jméno uloženo.")
    return redirect("/ucet")
