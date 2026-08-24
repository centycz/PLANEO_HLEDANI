"""Nahrani letaku pres formular az po slevy v aplikaci."""
from __future__ import annotations

import re

from pdf_fixture import write_pdf

LETAK = [
    "Letak plati od 12. 3. 2026 do 18. 3. 2026",
    "Maslo Jihoceske 250 g 49,90 Kc misto 79,90 Kc",
    "Kava zrnkova 1 kg 299,00 Kc misto 399,00 Kc",
]


def _upload(client, tmp_path, *, kind="letak", valid_from="", valid_to=""):
    pdf = write_pdf(tmp_path / "letak.pdf", [LETAK])
    with pdf.open("rb") as handle:
        response = client.post(
            "/import",
            files={"file": ("letak.pdf", handle, "application/pdf")},
            data={"kind": kind, "store_id": "1", "valid_from": valid_from, "valid_to": valid_to},
            follow_redirects=False,
        )
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[1])


def _rows(page: str) -> dict[str, str]:
    """Vrati {id_radku: nazev} z kontrolni obrazovky."""
    found = re.findall(r'name="name_(\d+)" value="([^"]*)"', page)
    return {row_id: name for row_id, name in found}


class TestNahraniLetaku:
    def test_vytazene_polozky_ceji_na_potvrzeni(self, logged_in, tmp_path):
        document_id = _upload(logged_in, tmp_path)
        page = logged_in.get(f"/import/{document_id}").text
        names = list(_rows(page).values())
        assert any("Maslo" in name for name in names)
        assert any("Kava" in name for name in names)

    def test_pred_potvrzenim_neni_v_katalogu(self, logged_in, tmp_path):
        _upload(logged_in, tmp_path)
        assert "Maslo" not in logged_in.get("/katalog").text

    def test_potvrzeni_zapise_katalog_i_slevy(self, logged_in, tmp_path):
        document_id = _upload(logged_in, tmp_path, valid_from="2026-03-12", valid_to="2099-12-31")
        page = logged_in.get(f"/import/{document_id}").text
        rows = _rows(page)

        form = {"select": list(rows)}
        for row_id, name in rows.items():
            form[f"name_{row_id}"] = name
            price = re.search(rf'name="price_{row_id}" value="([^"]*)"', page).group(1)
            original = re.search(
                rf'name="original_{row_id}"\s*value="([^"]*)"', page
            ).group(1)
            form[f"price_{row_id}"] = price
            form[f"original_{row_id}"] = original
            form[f"category_{row_id}"] = ""

        logged_in.post(f"/import/{document_id}/potvrdit", data=form, follow_redirects=False)

        katalog = logged_in.get("/katalog").text
        assert "Maslo Jihoceske" in katalog

        slevy = logged_in.get("/slevy").text
        assert "Maslo Jihoceske" in slevy
        assert "49,90" in slevy
        assert "−38 %" in slevy or "38 %" in slevy

    def test_prosla_platnost_slevu_skryje(self, logged_in, tmp_path):
        document_id = _upload(logged_in, tmp_path, valid_from="2020-01-01", valid_to="2020-01-07")
        page = logged_in.get(f"/import/{document_id}").text
        rows = _rows(page)
        form = {"select": list(rows)}
        for row_id, name in rows.items():
            form[f"name_{row_id}"] = name
            form[f"price_{row_id}"] = re.search(
                rf'name="price_{row_id}"\s*value="([^"]*)"', page
            ).group(1)
            form[f"original_{row_id}"] = ""
            form[f"category_{row_id}"] = ""
        logged_in.post(f"/import/{document_id}/potvrdit", data=form, follow_redirects=False)

        assert "Maslo Jihoceske" in logged_in.get("/katalog").text
        assert "Maslo Jihoceske" not in logged_in.get("/slevy").text

    def test_neoznacene_radky_se_nezapisou(self, logged_in, tmp_path):
        document_id = _upload(logged_in, tmp_path)
        page = logged_in.get(f"/import/{document_id}").text
        rows = _rows(page)
        form = {}
        for row_id, name in rows.items():
            form[f"name_{row_id}"] = name
            form[f"price_{row_id}"] = "10"
            form[f"category_{row_id}"] = ""
        logged_in.post(f"/import/{document_id}/potvrdit", data=form, follow_redirects=False)
        assert "Maslo Jihoceske" not in logged_in.get("/katalog").text

    def test_odmitne_jiny_nez_pdf(self, logged_in, tmp_path):
        path = tmp_path / "seznam.txt"
        path.write_text("mleko")
        with path.open("rb") as handle:
            response = logged_in.post(
                "/import",
                files={"file": ("seznam.txt", handle, "text/plain")},
                data={"kind": "letak"},
                follow_redirects=False,
            )
        assert response.headers["location"] == "/import"
        # hlaska se ukaze az na nasledujici strance (flash v session)
        assert "formátu PDF" in logged_in.get("/import").text
