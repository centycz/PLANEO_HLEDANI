"""Cteni polozek z PDF katalogu a letaku."""
from __future__ import annotations

import pytest

from app.pdf_import import parse_pdf
from app.text_utils import normalize

from pdf_fixture import write_pdf

KATALOG_LINES = [
    "Katalog sortimentu - potraviny",
    "Mleko polotucne 1,5% 1 l 24,90 Kc",
    "Maslo Jihoceske 250 g 59,90 Kc",
    "Rohlik tukovy 43 g 3,50 Kc",
    "Kureci prsni rizek 1 kg 149,90 Kc",
    "Sampon pro normalni vlasy 400 ml 89,90 Kc",
    "www.obchod.cz strana 1",
]

LETAK_LINES = [
    "Letak plati od 12. 3. 2026 do 18. 3. 2026",
    "Maslo Jihoceske 250 g 49,90 Kc misto 79,90 Kc",
    "Kava zrnkova 1 kg 299,00 Kc misto 399,00 Kc",
    "Pivo lezak 0,5 l 14,90 Kc",
]


@pytest.fixture()
def katalog_pdf(tmp_path):
    return write_pdf(tmp_path / "katalog.pdf", [KATALOG_LINES])


@pytest.fixture()
def letak_pdf(tmp_path):
    return write_pdf(tmp_path / "letak.pdf", [LETAK_LINES])


class TestKatalog:
    def test_najde_polozky_s_cenou(self, katalog_pdf):
        result = parse_pdf(katalog_pdf, "katalog")
        names = {normalize(row.name) for row in result.rows}
        assert any("mleko polotucne" in name for name in names)
        assert any("maslo jihoceske" in name for name in names)
        assert len(result.rows) >= 4

    def test_precte_ceny(self, katalog_pdf):
        result = parse_pdf(katalog_pdf, "katalog")
        prices = {
            normalize(row.name): row.price for row in result.rows if row.price is not None
        }
        maslo = next(price for name, price in prices.items() if "maslo" in name)
        assert maslo == 59.90

    def test_odhadne_kategorii(self, katalog_pdf):
        result = parse_pdf(katalog_pdf, "katalog")
        categories = {
            normalize(row.name): row.category_name for row in result.rows
        }
        rohlik = next(value for name, value in categories.items() if "rohlik" in name)
        assert rohlik == "Pečivo"

    def test_preskoci_hlavicky_a_odkazy(self, katalog_pdf):
        result = parse_pdf(katalog_pdf, "katalog")
        assert not any("www" in row.name.lower() for row in result.rows)

    def test_pocet_stran(self, tmp_path):
        pdf = write_pdf(tmp_path / "dve.pdf", [KATALOG_LINES, KATALOG_LINES])
        assert parse_pdf(pdf, "katalog").page_count == 2


class TestLetak:
    def test_rozpozna_akcni_a_puvodni_cenu(self, letak_pdf):
        result = parse_pdf(letak_pdf, "letak")
        row = next(row for row in result.rows if "maslo" in normalize(row.name))
        assert row.price == 49.90
        assert row.original_price == 79.90
        assert row.is_discount is True

    def test_vycte_platnost(self, letak_pdf):
        result = parse_pdf(letak_pdf, "letak")
        assert result.valid_from is not None
        assert (result.valid_from.day, result.valid_from.month) == (12, 3)
        assert (result.valid_to.day, result.valid_to.month) == (18, 3)

    def test_polozka_bez_puvodni_ceny_je_stale_akce(self, letak_pdf):
        result = parse_pdf(letak_pdf, "letak")
        row = next(row for row in result.rows if "pivo" in normalize(row.name))
        assert row.is_discount is True
        assert row.price == 14.90


class TestPrazdnePdf:
    def test_upozorni_kdyz_nic_nenajde(self, tmp_path):
        pdf = write_pdf(tmp_path / "prazdne.pdf", [["Jen nadpis bez cen"]])
        result = parse_pdf(pdf, "katalog")
        assert result.rows == []
        assert result.warnings


class TestNazvyBezCen:
    def test_nazev_neobsahuje_cenu_ani_slovo_misto(self, letak_pdf):
        result = parse_pdf(letak_pdf, "letak")
        row = next(row for row in result.rows if "maslo" in normalize(row.name))
        assert row.name == "Maslo Jihoceske 250 g"

    def test_jednotka_je_kus_u_baleneho_zbozi(self, letak_pdf):
        result = parse_pdf(letak_pdf, "letak")
        row = next(row for row in result.rows if "kava" in normalize(row.name))
        assert row.unit == "ks"
