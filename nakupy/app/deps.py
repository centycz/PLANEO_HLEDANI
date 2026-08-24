"""Sdilene zavislosti: prihlaseny uzivatel, sablony, flash hlasky."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import Settings, load_settings
from .db import get_db
from .models import ITEM_STATES, LIST_STATES, ROLES, User

TEMPLATES_DIR = Path(__file__).parent / "templates"
_settings: Settings = load_settings()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class LoginRequired(Exception):
    """Uzivatel neni prihlasen - middleware ho posle na /prihlaseni."""


def get_settings() -> Settings:
    return _settings


def set_settings(settings: Settings) -> None:
    global _settings
    _settings = settings


# --- formatovaci filtry ---------------------------------------------------
def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(_settings.timezone)
    except Exception:  # pragma: no cover - chybejici tzdata
        return ZoneInfo("UTC")


def fmt_datetime(value: dt.datetime | None, fmt: str = "%-d. %-m. %Y %H:%M") -> str:
    if not value:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(_tz()).strftime(fmt)


def fmt_date(value: dt.date | None) -> str:
    if not value:
        return "—"
    return value.strftime("%-d. %-m. %Y")


def fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " Kč"


def fmt_qty(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def relative_days(value: dt.datetime | None) -> str:
    if not value:
        return "nikdy"
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    days = (dt.datetime.now(dt.timezone.utc) - value).days
    if days <= 0:
        return "dnes"
    if days == 1:
        return "včera"
    if days < 31:
        return f"před {days} dny"
    months = days // 30
    return f"před {months} měs."


templates.env.filters["dt"] = fmt_datetime
templates.env.filters["d"] = fmt_date
templates.env.filters["money"] = fmt_money
templates.env.filters["qty"] = fmt_qty
templates.env.filters["ago"] = relative_days
templates.env.globals["ITEM_STATES"] = ITEM_STATES
templates.env.globals["LIST_STATES"] = LIST_STATES
templates.env.globals["ROLES"] = ROLES


# --- prihlaseni -----------------------------------------------------------
def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        return None
    return user


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise LoginRequired()
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Jen pro administrátora.")
    return user


# --- flash hlasky ---------------------------------------------------------
def flash(request: Request, message: str, level: str = "ok") -> None:
    """Ulozi hlasku do session.

    Klic se prirazuje znovu zamerne - Starlette pozna zmenu session jen pres
    __setitem__, takze pripsani do existujiciho seznamu by se neulozilo.
    """
    messages = list(request.session.get("_flash", []))
    messages.append({"message": message, "level": level})
    request.session["_flash"] = messages


def pop_flashes(request: Request) -> list[dict[str, str]]:
    return request.session.pop("_flash", [])


def render(request: Request, template: str, user: User | None = None, **context):
    """Vykresli sablonu s beznym kontextem (uzivatel, hlasky)."""
    context.setdefault("user", user)
    context.setdefault("flashes", pop_flashes(request))
    context.setdefault("settings", _settings)
    return templates.TemplateResponse(request, template, context)


def redirect(url: str, code: int = status.HTTP_303_SEE_OTHER) -> RedirectResponse:
    return RedirectResponse(url, status_code=code)
