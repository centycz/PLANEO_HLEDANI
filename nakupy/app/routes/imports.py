"""Nahrani PDF katalogu / letaku, kontrola vytazenych radku a import."""
from __future__ import annotations

import datetime as dt
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db, session_scope
from ..deps import flash, get_settings, redirect, render, require_user
from ..models import (
    DOC_FAILED,
    DOC_IMPORTED,
    DOC_KATALOG,
    DOC_KINDS,
    DOC_LETAK,
    DOC_PARSED,
    DOC_PROCESSING,
    DOC_STATES,
    Category,
    Document,
    ImportRow,
    Price,
    Store,
    User,
)
from ..pdf_import import parse_pdf
from ..services import ensure_catalog_item

logger = logging.getLogger(__name__)
router = APIRouter()

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _parse_date(value: str) -> dt.date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _process_document(document_id: int) -> None:
    """Bezi na pozadi - precte PDF a ulozi kandidaty na polozky."""
    try:
        with session_scope() as session:
            document = session.get(Document, document_id)
            if document is None:
                return
            path = Path(document.stored_path)
            kind = document.kind

        result = parse_pdf(path, kind)

        with session_scope() as session:
            document = session.get(Document, document_id)
            if document is None:
                return
            categories = {c.name: c.id for c in session.scalars(select(Category)).all()}
            for row in result.rows:
                session.add(
                    ImportRow(
                        document_id=document.id,
                        page=row.page,
                        raw_text=row.raw_text,
                        name=row.name,
                        package=row.package,
                        unit=row.unit,
                        price=row.price,
                        original_price=row.original_price,
                        category_id=categories.get(row.category_name or ""),
                        is_discount=row.is_discount,
                        selected=bool(row.name and row.price),
                    )
                )
            document.page_count = result.page_count
            document.row_count = len(result.rows)
            document.status = DOC_PARSED
            document.error = " ".join(result.warnings)[:2000]
            if document.valid_from is None:
                document.valid_from = result.valid_from
            if document.valid_to is None:
                document.valid_to = result.valid_to
    except Exception as exc:  # pragma: no cover - zavisi na konkretnim PDF
        logger.exception("Zpracovani dokumentu %s selhalo", document_id)
        with session_scope() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.status = DOC_FAILED
                document.error = f"{type(exc).__name__}: {exc}"[:2000]


@router.get("/import")
def import_view(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.store), selectinload(Document.uploaded_by))
        .order_by(Document.uploaded_at.desc())
        .limit(40)
    ).all()
    return render(
        request,
        "import.html",
        user=user,
        documents=documents,
        stores=db.scalars(select(Store).order_by(Store.name)).all(),
        kinds=DOC_KINDS,
        states=DOC_STATES,
        today=dt.date.today(),
    )


@router.post("/import")
async def upload_pdf(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    kind: str = Form(DOC_KATALOG),
    store_id: str = Form(""),
    valid_from: str = Form(""),
    valid_to: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    filename = file.filename or "dokument.pdf"
    if not filename.lower().endswith(".pdf"):
        flash(request, "Nahraj prosím soubor ve formátu PDF.", "error")
        return redirect("/import")
    if kind not in DOC_KINDS:
        kind = DOC_KATALOG

    safe = _SAFE_NAME.sub("_", Path(filename).name)[-80:]
    target = settings.uploads_dir / f"{uuid.uuid4().hex}_{safe}"
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    with target.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                handle.close()
                target.unlink(missing_ok=True)
                flash(request, f"Soubor je větší než {settings.max_upload_mb} MB.", "error")
                return redirect("/import")
            handle.write(chunk)

    document = Document(
        filename=filename[:255],
        stored_path=str(target),
        kind=kind,
        store_id=int(store_id) if store_id.strip() else None,
        valid_from=_parse_date(valid_from),
        valid_to=_parse_date(valid_to),
        status=DOC_PROCESSING,
        uploaded_by=user,
    )
    db.add(document)
    # commit pred spustenim ulohy na pozadi - jinak by ji vlastni session nevidela
    db.commit()
    document_id = document.id

    background.add_task(_process_document, document_id)
    flash(request, "PDF se zpracovává. Za chvíli si položky zkontroluj a potvrď.")
    return redirect(f"/import/{document_id}")


@router.get("/import/{document_id}")
def review_view(
    document_id: int,
    request: Request,
    only_selected: int = 0,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Dokument nenalezen.")

    statement = select(ImportRow).where(ImportRow.document_id == document_id)
    if only_selected:
        statement = statement.where(ImportRow.selected.is_(True))
    rows = db.scalars(statement.order_by(ImportRow.page, ImportRow.name).limit(1500)).all()

    return render(
        request,
        "import_review.html",
        user=user,
        document=document,
        rows=rows,
        categories=db.scalars(select(Category).order_by(Category.position)).all(),
        states=DOC_STATES,
        kinds=DOC_KINDS,
        only_selected=only_selected,
    )


@router.get("/api/import/{document_id}/stav")
def import_state(
    document_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Dokument nenalezen.")
    return {
        "status": document.status,
        "rows": document.row_count,
        "pages": document.page_count,
        "imported": document.imported_count,
        "error": document.error,
    }


@router.post("/import/{document_id}/potvrdit")
async def confirm_import(
    document_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Zapise potvrzene radky do katalogu a zalozi k nim ceny."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Dokument nenalezen.")

    form = await request.form()
    selected_ids = {int(value) for value in form.getlist("select")}
    rows = db.scalars(select(ImportRow).where(ImportRow.document_id == document_id)).all()

    imported = 0
    for row in rows:
        row.selected = row.id in selected_ids
        name = str(form.get(f"name_{row.id}", row.name) or "").strip()
        price_raw = str(form.get(f"price_{row.id}", "") or "").replace(",", ".").strip()
        original_raw = str(form.get(f"original_{row.id}", "") or "").replace(",", ".").strip()
        category_raw = str(form.get(f"category_{row.id}", "") or "").strip()

        row.name = name[:255]
        try:
            row.price = round(float(price_raw), 2) if price_raw else None
        except ValueError:
            pass
        try:
            row.original_price = round(float(original_raw), 2) if original_raw else None
        except ValueError:
            pass
        row.category_id = int(category_raw) if category_raw else None

        if not row.selected or not row.name or row.price is None:
            continue

        category = db.get(Category, row.category_id) if row.category_id else None
        item = ensure_catalog_item(
            db, row.name, unit=row.unit, package=row.package, category=category
        )
        if item is None:
            continue
        if category and item.category_id != category.id:
            item.category_id = category.id
        if row.package and not item.package:
            item.package = row.package

        is_discount = bool(row.is_discount or document.kind == DOC_LETAK or row.original_price)
        db.add(
            Price(
                item_id=item.id,
                store_id=document.store_id,
                price=row.price,
                original_price=row.original_price,
                is_discount=is_discount,
                valid_from=document.valid_from,
                valid_to=document.valid_to,
                document_id=document.id,
                note=DOC_KINDS.get(document.kind, ""),
            )
        )
        row.imported = True
        row.catalog_item_id = item.id
        imported += 1

    document.imported_count = imported
    document.status = DOC_IMPORTED if imported else document.status
    db.add(document)
    flash(request, f"Do katalogu zapsáno {imported} položek.")
    return redirect(f"/import/{document_id}")


@router.post("/import/{document_id}/oznacit")
async def bulk_select(
    document_id: int,
    request: Request,
    action: str = Form("all"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(ImportRow).where(ImportRow.document_id == document_id)).all()
    for row in rows:
        if action == "all":
            row.selected = bool(row.name and row.price is not None)
        elif action == "none":
            row.selected = False
        elif action == "discounts":
            row.selected = bool(row.is_discount and row.name and row.price is not None)
    return redirect(f"/import/{document_id}")


@router.post("/import/{document_id}/smazat")
def delete_document(
    document_id: int,
    request: Request,
    keep_catalog: str = Form("on"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Dokument nenalezen.")

    if not keep_catalog:
        for price in db.scalars(select(Price).where(Price.document_id == document_id)).all():
            db.delete(price)
    else:
        db.query(Price).filter(Price.document_id == document_id).update({"document_id": None})

    Path(document.stored_path).unlink(missing_ok=True)
    db.delete(document)
    flash(request, "Dokument smazán.")
    return redirect("/import")
