"""Cteni katalogu a letaku z PDF.

PDF od ruznych retezcu vypada pokazde jinak, proto se tady nesnazime o
dokonalost: vytahneme kandidaty na polozky (nazev + cena) a uzivatel je pred
zapsanim do katalogu projde a potvrdi na obrazovce /import/{id}.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .text_utils import (
    clean_name,
    default_unit,
    extract_unit,
    find_prices,
    guess_category_name,
    normalize,
    strip_prices,
)

logger = logging.getLogger(__name__)

MAX_PAGES = 400
MIN_NAME_LEN = 3
MAX_NAME_LEN = 120

# radky, ktere nikdy nejsou polozka
_NOISE_RE = re.compile(
    r"^(strana|page|www\.|http|tel\.|ic[oo]:|dic:|platnost|akce plat|obsah|"
    r"cenik|katalog|leták|letak|vydáno|vydano)\b",
    re.IGNORECASE,
)
_LETTERS_RE = re.compile(r"[A-Za-zÁ-Žá-ž]")

# "od 12. 3. do 18. 3. 2025", "12.3.-18.3.2025", "platí od 1. 5. 2025"
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})?\s*(?:-|–|—|do|až)\s*"
    r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})?",
)


@dataclass
class ParsedRow:
    """Jeden kandidat na polozku katalogu."""

    name: str
    price: float | None = None
    original_price: float | None = None
    package: str = ""
    unit: str = "ks"
    page: int = 0
    raw_text: str = ""
    is_discount: bool = False
    category_name: str | None = None


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    page_count: int = 0
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    warnings: list[str] = field(default_factory=list)


def _is_noise(text: str) -> bool:
    if not text or _NOISE_RE.match(text.strip()):
        return True
    letters = len(_LETTERS_RE.findall(text))
    return letters < MIN_NAME_LEN


# reklamni vata kolem ceny - i bez diakritiky, PDF ji casto ztrati
_MARKETING_RE = re.compile(
    r"\b(?:akce|akční cena|akcni cena|nyní|nyni|místo|misto|běžná cena|bezna cena|"
    r"nová cena|nova cena|sleva|ušetříte|usetrite|cena za|jen)\b[:\s]*",
    re.IGNORECASE,
)


def _name_from_line(line: str) -> str:
    """Odstrani z radku ceny a reklamni vatu, zbyde nazev polozky."""
    name = strip_prices(line)
    # koncove cislo bez meny (typicky cena ve sloupci tabulky)
    name = re.sub(r"[\s.·•]+\d+(?:[.,]\d{1,2})\s*$", " ", name)
    name = _MARKETING_RE.sub(" ", name)
    return clean_name(name)[:MAX_NAME_LEN]


def _build_row(name: str, prices: list[float], page: int, raw: str, kind: str) -> ParsedRow | None:
    name = clean_name(name)
    if _is_noise(name):
        return None

    price = original = None
    is_discount = False
    if prices:
        unique = sorted(set(prices))
        price = unique[0]
        if len(unique) > 1:
            highest = unique[-1]
            # dve ruzne ceny na radku = akce (nizsi) proti puvodni (vyssi)
            if highest >= price * 1.05:
                original = highest
                is_discount = True
    if kind == "letak" and price is not None:
        is_discount = True

    package, _package_unit = extract_unit(raw or name)
    category_name = guess_category_name(name)
    return ParsedRow(
        name=name,
        price=price,
        original_price=original,
        package=package,
        unit=default_unit(name, category_name),
        page=page,
        raw_text=(raw or name)[:500],
        is_discount=is_discount,
        category_name=category_name,
    )


def _rows_from_table(table: list[list[str | None]], page: int, kind: str) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    for raw_cells in table or []:
        cells = [clean_name(cell or "") for cell in raw_cells]
        if not any(cells):
            continue
        text_cells = [cell for cell in cells if _LETTERS_RE.search(cell)]
        if not text_cells:
            continue
        name = max(text_cells, key=len)
        prices: list[float] = []
        for cell in cells:
            if cell is name:
                continue
            prices.extend(find_prices(cell))
        if not prices:
            prices = find_prices(" ".join(cells), explicit_only=True)
        row = _build_row(name, prices, page, " | ".join(cells), kind)
        if row:
            rows.append(row)
    return rows


def _rows_from_text(text: str, page: int, kind: str) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or _is_noise(line):
            continue
        prices = find_prices(line, explicit_only=True)
        if not prices:
            continue
        row = _build_row(_name_from_line(line), prices, page, line, kind)
        if row:
            rows.append(row)
    return rows


def _extract_validity(text: str) -> tuple[dt.date | None, dt.date | None]:
    match = _DATE_RANGE_RE.search(text or "")
    if not match:
        return None, None
    d1, m1, y1, d2, m2, y2 = match.groups()
    year2 = int(y2) if y2 else dt.date.today().year
    year1 = int(y1) if y1 else year2
    try:
        return dt.date(year1, int(m1), int(d1)), dt.date(year2, int(m2), int(d2))
    except ValueError:
        return None, None


def _dedupe(rows: list[ParsedRow]) -> list[ParsedRow]:
    """Stejny nazev vicekrat = necháme ten s nejnizsi (akcni) cenou."""
    best: dict[str, ParsedRow] = {}
    for row in rows:
        key = normalize(row.name)
        if not key:
            continue
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        if current.price is None and row.price is not None:
            best[key] = row
        elif row.price is not None and current.price is not None and row.price < current.price:
            row.original_price = row.original_price or current.price
            best[key] = row
    return list(best.values())


def parse_pdf(path: str | Path, kind: str = "katalog") -> ParseResult:
    """Vytahne z PDF kandidaty na polozky katalogu."""
    import pdfplumber  # lazy import - pdfplumber startuje pomalu

    result = ParseResult()
    collected: list[ParsedRow] = []
    validity_text: list[str] = []

    with pdfplumber.open(str(path)) as pdf:
        result.page_count = len(pdf.pages)
        if result.page_count > MAX_PAGES:
            result.warnings.append(
                f"PDF má {result.page_count} stran, zpracovává se prvních {MAX_PAGES}."
            )
        for index, page in enumerate(pdf.pages[:MAX_PAGES], start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # pragma: no cover - poskozene PDF
                logger.warning("Stranu %s se nepodarilo precist: %s", index, exc)
                result.warnings.append(f"Strana {index} se nepodařila přečíst.")
                continue

            if index <= 3:
                validity_text.append(text)

            page_rows: list[ParsedRow] = []
            try:
                for table in page.extract_tables() or []:
                    page_rows.extend(_rows_from_table(table, index, kind))
            except Exception as exc:  # pragma: no cover
                logger.debug("Tabulky na strane %s: %s", index, exc)

            if not page_rows:
                page_rows = _rows_from_text(text, index, kind)
            collected.extend(page_rows)

    result.rows = _dedupe(collected)
    result.rows.sort(key=lambda r: (r.page, normalize(r.name)))
    result.valid_from, result.valid_to = _extract_validity("\n".join(validity_text))
    if not result.rows:
        result.warnings.append(
            "V PDF se nenašly žádné položky s cenou. Bývá to sken bez textové "
            "vrstvy - pak je potřeba položky zadat ručně."
        )
    return result
