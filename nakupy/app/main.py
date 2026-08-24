"""Nakupy - privatni nakupni aplikace (FastAPI)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .config import load_settings
from .db import get_db, init_engine, session_scope
from .deps import LoginRequired, current_user, redirect, render, set_settings
from .models import LIST_DONE, ListItem, ShoppingList, Store, User
from .seed import seed
from .suggestions import active_prices, deals, favorite_suggestions, frequent_items, list_progress
from .text_utils import normalize

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("nakupy")

STATIC_DIR = Path(__file__).parent / "static"
settings = load_settings()
set_settings(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine(settings)
    with session_scope() as session:
        seed(session, settings)
    logger.info("Nakupy %s spusteny, data v %s", __version__, settings.data_dir)
    yield


app = FastAPI(title="Nákupy", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="nakupy_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.secure_cookies,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from .routes import admin, auth, catalog, imports, lists, shop  # noqa: E402

app.include_router(auth.router)
app.include_router(lists.router)
app.include_router(shop.router)
app.include_router(catalog.router)
app.include_router(imports.router)
app.include_router(admin.router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, _exc: LoginRequired):
    return redirect(f"/prihlaseni?next={request.url.path}")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    user = request.session.get("user_id")
    return render(
        request, "error.html", status_code=exc.status_code, detail=exc.detail, logged_in=bool(user)
    )


@app.get("/")
def dashboard(
    request: Request, user: User | None = Depends(current_user), db: Session = Depends(get_db)
):
    if user is None:
        return redirect("/prihlaseni")

    open_lists = db.scalars(
        select(ShoppingList)
        .where(ShoppingList.status != LIST_DONE)
        .options(
            selectinload(ShoppingList.items).selectinload(ListItem.catalog_item),
            selectinload(ShoppingList.store),
            selectinload(ShoppingList.shopper),
        )
        .order_by(desc(ShoppingList.updated_at))
        .limit(5)
    ).all()

    on_lists = {normalize(i.name) for sl in open_lists for i in sl.items}
    current = open_lists[0] if open_lists else None

    return render(
        request,
        "index.html",
        user=user,
        open_lists=open_lists,
        current=current,
        progress={sl.id: list_progress(sl) for sl in open_lists},
        suggestions=frequent_items(db, limit=8, exclude_norm=on_lists),
        favorites=favorite_suggestions(db, user.id, exclude_norm=on_lists, limit=8),
        top_deals=deals(db, store_id=current.store_id if current else None, limit=8),
        deal_prices=active_prices(db),
        stores=db.scalars(select(Store).where(Store.is_active.is_(True)).order_by(Store.name)).all(),
        recent_done=db.scalars(
            select(ShoppingList)
            .where(ShoppingList.status == LIST_DONE)
            .options(selectinload(ShoppingList.items))
            .order_by(desc(ShoppingList.finished_at))
            .limit(3)
        ).all(),
    )


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/zdravi")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "version": __version__}
