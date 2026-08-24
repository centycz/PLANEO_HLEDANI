"""Normalizace nazvu a odhad kategorie podle klicovych slov."""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

# jednotky, ktere se objevuji v nazvech ("Mleko 1,5% 1 l")
_UNIT_RE = re.compile(
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|l|ml|ks|balení|bal\.|ks\.)\b",
    re.IGNORECASE,
)

# ceny: "24,90", "1 249,00", "119.-", "89,90 Kč"
_NUMBER_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[\u00a0 ]\d{3})+|\d+)(?:[.,](\d{1,2}))?(?![\d])"
)
_CURRENCY_RE = re.compile(r"^\s*(?:Kč\b|Kc\b|CZK\b|,-|\.-|-,)", re.IGNORECASE)
# co za cislem znamena, ze to cena neni: "1,5 %", "500 g", "3 x 1 l", "40 cm"
_NOT_PRICE_AFTER_RE = re.compile(
    r"^\s*(?:%|x\b|ks\b|g\b|kg\b|ml\b|dl\b|l\b|cm\b|mm\b|m\b|°|st\b|W\b)",
    re.IGNORECASE,
)


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def normalize(text: str) -> str:
    """Klic pro porovnavani nazvu: bez diakritiky, malymi, bez interpunkce."""
    text = strip_accents(text or "").lower()
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def clean_name(text: str) -> str:
    """Uklidi nazev z PDF - zbytecne mezery, tecky, opakovane znaky."""
    text = (text or "").replace(" ", " ")
    text = re.sub(r"[.•·]{2,}", " ", text)
    text = _WS.sub(" ", text).strip(" -–—:;,.")
    return text


def extract_unit(text: str) -> tuple[str, str]:
    """Vrati (balení, jednotka) nalezene v nazvu, napr. ("1 l", "l")."""
    match = _UNIT_RE.search(text or "")
    if not match:
        return "", "ks"
    unit = match.group("unit").lower().rstrip(".")
    if unit in {"balení", "bal"}:
        unit = "ks"
    return f"{match.group('amount')} {unit}", unit


def _iter_prices(text: str):
    """Projde text a vrati (hodnota, ma_menu) pro vse, co vypada jako cena."""
    for match in _NUMBER_RE.finditer(text or ""):
        tail = text[match.end():]
        if _NOT_PRICE_AFTER_RE.match(tail):
            continue
        whole = match.group(1).replace("\u00a0", "").replace(" ", "")
        cents = match.group(2)
        try:
            value = round(float(f"{whole}.{(cents or '0').ljust(2, '0')}"), 2)
        except ValueError:
            continue
        if not 0.5 <= value <= 200_000:
            continue
        has_currency = bool(_CURRENCY_RE.match(tail))
        yield value, has_currency or cents is not None


def parse_price(text: str) -> float | None:
    """Prevede cenovy retezec na float ('1 249,90' -> 1249.9)."""
    for value, _explicit in _iter_prices(str(text or "")):
        return value
    return None


def strip_prices(text: str) -> str:
    """Odstrani z textu vse, co je cena, a necha nazev polozky.

    Gramaz ani procenta se nemazou - "Maslo 250 g 49,90 Kc" da "Maslo 250 g".
    """
    text = text or ""
    parts: list[str] = []
    last = 0
    for match in _NUMBER_RE.finditer(text):
        tail = text[match.end():]
        if _NOT_PRICE_AFTER_RE.match(tail):
            continue
        currency = _CURRENCY_RE.match(tail)
        if not currency and match.group(2) is None:
            continue  # holé číslo bez halířů a bez měny necháme být
        parts.append(text[last:match.start()])
        last = match.end() + (currency.end() if currency else 0)
    parts.append(text[last:])
    return _WS.sub(" ", "".join(parts)).strip()


def find_prices(text: str, *, explicit_only: bool = False) -> list[float]:
    """Najde vsechny ceny v radku (letak ma casto puvodni + akcni cenu).

    ``explicit_only`` propusti jen cisla, ktera maji halere nebo menu - to
    hodne pomaha u letaku, kde se v nazvu miha gramaz a procenta tuku.
    """
    values = [value for value, explicit in _iter_prices(text or "") if explicit or not explicit_only]
    return values


# --- odhad kategorie ------------------------------------------------------
# poradi odpovida beznemu prochazeni obchodem (ovoce u vchodu, drogerie na konci)
DEFAULT_CATEGORIES: list[tuple[str, str, int, list[str]]] = [
    ("Ovoce a zelenina", "🥬", 10, [
        "jablk", "banan", "hrusk", "pomeranc", "citron", "mandarink", "hrozn", "jahod",
        "boruvk", "melou", "brambor", "cibul", "cesnek", "mrkev", "rajc", "papri",
        "okurk", "salat", "zeli", "brokolic", "kvetak", "houb", "avokad", "zelenina",
        "ovoce", "bylink", "petrzel", "kedluben", "dyne", "cukety",
    ]),
    ("Pečivo", "🥖", 20, [
        "chleb", "rohlik", "houska", "baget", "pecivo", "kaiserk", "croissant",
        "kobliha", "vecka", "toustov", "stridka", "buchta", "kolac", "dalamank",
    ]),
    ("Mléčné výrobky", "🥛", 30, [
        "mleko", "jogurt", "syr", "tvaroh", "smetan", "maslo", "kefir", "podmasli",
        "eidam", "hermelin", "mozzarell", "cottage", "zervy", "lucin", "pomazank",
        "vejce", "smetanov", "acidofil", "skyr",
    ]),
    ("Maso a uzeniny", "🍖", 40, [
        "maso", "kure", "kureci", "veprov", "hovezi", "krut", "salam", "sunk",
        "parek", "klobas", "spekac", "slanin", "mlet", "rybi", "losos", "tunak",
        "vurt", "pastik", "kridla", "krkovic", "bok", "rizek",
    ]),
    ("Lahůdky a hotová jídla", "🥗", 50, [
        "lahudk", "salat majone", "chlebicek", "obloz", "hotov jidl", "polevka cerstv",
        "sushi", "pizza cerstv",
    ]),
    ("Mražené", "🧊", 60, [
        "mrazen", "zmrzlin", "hranolk", "spenat mrazen", "pizza mrazen", "knedlik mrazen",
        "led ", "nanuk",
    ]),
    ("Trvanlivé potraviny", "🥫", 70, [
        "mouka", "cukr", "ryze", "testovin", "olej", "ocet", "sul", "koreni", "kecup",
        "horcice", "majonez", "konzerv", "kompot", "luste", "cocka", "fazol", "hrach",
        "musli", "ovesn", "kase", "med", "dzem", "marmelad", "paste", "bujon", "polevka",
        "kroupy", "kus kus", "kuskus", "strouhank", "kakao", "kava", "caj", "kvasnic",
    ]),
    ("Sladkosti a snacky", "🍫", 80, [
        "cokolad", "sladk", "bonbon", "susenk", "oplatk", "chips", "brambork", "tycink",
        "zelatinov", "zele ", "orisk", "arasid", "mandle", "popcorn", "krekr", "lentilk",
    ]),
    ("Nápoje", "🥤", 90, [
        "voda", "mineraln", "dzus", "juice", "limonad", "kola", "sirup", "napoj",
        "energet", "tonic", "ledovy caj", "ice tea", "malinovk", "perliv",
    ]),
    ("Alkohol", "🍷", 100, [
        "pivo", "vino", "rum", "vodka", "whisk", "becherovk", "likér", "liker",
        "sekt", "prosecco", "gin", "slivovic", "alkohol",
    ]),
    ("Drogerie", "🧴", 110, [
        "sampon", "mydl", "zubn", "pasta zub", "sprchov", "deodor", "holic", "krem",
        "toaletni papir", "papirov kapesnik", "ubrousk", "plen", "vlozk", "tampon",
        "vata", "kartacek",
    ]),
    ("Domácnost a úklid", "🧽", 120, [
        "prasek na prani", "praci prasek", "praci gel", "kapsle na prani", "persil",
        "ariel", "avivaz", "saponat", "jar ", "cistic", "houbick", "hadr", "savo",
        "domestos", "pur ",
        "pytle na odpad", "sacky", "alobal", "papir na peceni", "svicka", "baterie",
        "zarovk", "utěrk", "uterk", "wc ", "odpadk",
    ]),
    ("Zvířata", "🐾", 130, [
        "granul", "kapsick", "krmiv", "stelivo", "pamlsk pro", "pro psy", "pro kocky",
    ]),
    ("Ostatní", "🛒", 900, []),
]


def guess_category_name(text: str) -> str | None:
    """Vrati nazev kategorie odhadnuty podle klicovych slov v nazvu polozky."""
    norm = normalize(text)
    if not norm:
        return None
    best: tuple[int, str] | None = None
    for name, _icon, _pos, keywords in DEFAULT_CATEGORIES:
        for keyword in keywords:
            if keyword in norm:
                score = len(keyword)
                if best is None or score > best[0]:
                    best = (score, name)
    return best[1] if best else None

# zbozi, ktere se bezne kupuje na vahu
BULK_CATEGORIES = {"Ovoce a zelenina", "Maso a uzeniny"}


def default_unit(name: str, category_name: str | None = None) -> str:
    """Jednotka, ve ktere se polozka nakupuje.

    Velikost baleni v nazvu ("Mleko 1 l") znamena, ze se kupuji kusy - tri
    krabice mleka jsou 3 ks, ne 3 litry. Vahove zbozi bez baleni je v kg.
    """
    package, _unit = extract_unit(name)
    if package:
        return "ks"
    if (category_name or guess_category_name(name)) in BULK_CATEGORIES:
        return "kg"
    return "ks"
