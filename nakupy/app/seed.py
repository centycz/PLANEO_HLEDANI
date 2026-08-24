"""Prvni naplneni databaze - kategorie, obchody, admin ucet."""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import ROLE_ADMIN, Category, Store, User
from .security import hash_password
from .text_utils import DEFAULT_CATEGORIES

logger = logging.getLogger(__name__)

DEFAULT_STORES = ["Kaufland", "Lidl", "Albert", "Billa", "Penny", "Tesco", "Globus"]


def ensure_categories(session: Session) -> None:
    existing = {c.name for c in session.scalars(select(Category)).all()}
    for name, icon, position, keywords in DEFAULT_CATEGORIES:
        if name in existing:
            continue
        session.add(
            Category(name=name, icon=icon, position=position, keywords=", ".join(keywords))
        )
    session.flush()


def ensure_stores(session: Session) -> None:
    if session.scalar(select(func.count(Store.id))):
        return
    for name in DEFAULT_STORES:
        session.add(Store(name=name))
    session.flush()


def ensure_admin(session: Session, settings: Settings) -> None:
    if session.scalar(select(func.count(User.id))):
        return
    session.add(
        User(
            username=settings.admin_user,
            display_name=settings.admin_name,
            password_hash=hash_password(settings.admin_password),
            role=ROLE_ADMIN,
        )
    )
    logger.info("Vytvoren prvni admin ucet '%s'.", settings.admin_user)


def seed(session: Session, settings: Settings) -> None:
    ensure_categories(session)
    ensure_stores(session)
    ensure_admin(session, settings)
