"""Prubeh nakupu od zadani po historii."""
from __future__ import annotations

import re


def _list_state(client, list_id):
    return client.get(f"/api/seznam/{list_id}/stav").json()


class TestPrihlaseni:
    def test_neprihlaseny_jde_na_prihlaseni(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/prihlaseni"

    def test_chybne_heslo_neprihlasi(self, client):
        response = client.post(
            "/prihlaseni", data={"username": "admin", "password": "spatne"},
            follow_redirects=False,
        )
        assert response.headers["location"].startswith("/prihlaseni")

    def test_prihlaseny_vidi_prehled(self, logged_in):
        assert logged_in.get("/").status_code == 200


class TestSeznam:
    def test_pridani_polozky(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat",
            data={"name": "Mléko polotučné 1 l", "qty": "2"},
            follow_redirects=False,
        )
        detail = logged_in.get(f"/seznam/{shopping_list_id}")
        assert "Mléko polotučné 1 l" in detail.text

    def test_stejna_polozka_se_secte(self, logged_in, shopping_list_id):
        for _ in range(2):
            logged_in.post(
                f"/seznam/{shopping_list_id}/pridat",
                data={"name": "Chléb konzumní", "qty": "1"},
                follow_redirects=False,
            )
        items = _list_state(logged_in, shopping_list_id)["items"]
        assert len(items) == 1

    def test_hromadne_vlozeni(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/hromadne",
            data={"text": "2x jogurt bílý\nchléb konzumní\n3 banány"},
            follow_redirects=False,
        )
        assert _list_state(logged_in, shopping_list_id)["total"] == 3

    def test_prazdny_nazev_nic_neprida(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat", data={"name": "  "}, follow_redirects=False
        )
        assert _list_state(logged_in, shopping_list_id)["total"] == 0

    def test_smazani_polozky(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat", data={"name": "Sůl"}, follow_redirects=False
        )
        item_id = _list_state(logged_in, shopping_list_id)["items"][0]["id"]
        logged_in.post(f"/polozka/{item_id}/smazat", follow_redirects=False)
        assert _list_state(logged_in, shopping_list_id)["total"] == 0


class TestRazeniPodleObchodu:
    def test_polozky_jdou_v_poradi_useku(self, logged_in, shopping_list_id):
        for name in ["Šampon", "Rohlík tukový", "Jablka", "Mléko 1 l"]:
            logged_in.post(
                f"/seznam/{shopping_list_id}/pridat", data={"name": name}, follow_redirects=False
            )
        page = logged_in.get(f"/nakup/{shopping_list_id}").text
        sections = [s.strip() for s in re.findall(r'section-title">\s*\S+ ([^\n<]+)', page)]
        assert sections == ["Ovoce a zelenina", "Pečivo", "Mléčné výrobky", "Drogerie"]

    def test_vlastni_trasa_obchodu_meni_poradi(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/nastaveni",
            data={"title": "Test", "store_id": "1"},
            follow_redirects=False,
        )
        for name in ["Rohlík tukový", "Jablka"]:
            logged_in.post(
                f"/seznam/{shopping_list_id}/pridat", data={"name": name}, follow_redirects=False
            )
        layout = logged_in.get("/nastaveni/rozlozeni/1").text
        pecivo_id = re.search(r'name="position_(\d+)"[^>]*>\s*<span>🥖', layout)
        ovoce_id = re.search(r'name="position_(\d+)"[^>]*>\s*<span>🥬', layout)
        assert pecivo_id and ovoce_id
        logged_in.post(
            "/nastaveni/rozlozeni/1",
            data={f"position_{pecivo_id.group(1)}": "1", f"position_{ovoce_id.group(1)}": "2"},
            follow_redirects=False,
        )
        page = logged_in.get(f"/nakup/{shopping_list_id}").text
        sections = [s.strip() for s in re.findall(r'section-title">\s*\S+ ([^\n<]+)', page)]
        assert sections[0] == "Pečivo"


class TestNakup:
    def test_odskrtnuti_polozky(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat", data={"name": "Máslo"}, follow_redirects=False
        )
        item_id = _list_state(logged_in, shopping_list_id)["items"][0]["id"]
        response = logged_in.post(
            f"/nakup/polozka/{item_id}/stav",
            data={"status": "bought", "price": "59,90"},
            headers={"X-Ajax": "1"},
        )
        payload = response.json()
        assert payload["status"] == "bought"
        assert payload["price"] == 59.90
        assert payload["progress"]["pct"] == 100

    def test_polozka_nebyla_skladem(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat", data={"name": "Kvasnice"}, follow_redirects=False
        )
        item_id = _list_state(logged_in, shopping_list_id)["items"][0]["id"]
        logged_in.post(
            f"/nakup/polozka/{item_id}/stav",
            data={"status": "missing", "note": "vyprodáno"},
            follow_redirects=False,
        )
        assert _list_state(logged_in, shopping_list_id)["items"][0]["status"] == "missing"

    def test_nakupci_prida_polozku_navic(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/nakup/{shopping_list_id}/pridat",
            data={"name": "Čokoláda", "qty": "1", "price": "29,90"},
            follow_redirects=False,
        )
        items = _list_state(logged_in, shopping_list_id)["items"]
        assert items[0]["status"] == "bought"
        assert items[0]["price"] == 29.90

    def test_dokonceni_zapise_historii(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat", data={"name": "Mléko 1 l"}, follow_redirects=False
        )
        item_id = _list_state(logged_in, shopping_list_id)["items"][0]["id"]
        logged_in.post(
            f"/nakup/polozka/{item_id}/stav",
            data={"status": "bought", "price": "24,90"},
            follow_redirects=False,
        )
        logged_in.post(f"/nakup/{shopping_list_id}/dokoncit", follow_redirects=False)

        assert _list_state(logged_in, shopping_list_id)["status"] == "done"
        historie = logged_in.get("/historie").text
        assert "Mléko 1 l" in historie
        assert "24,90" in historie


class TestOblibene:
    def test_pridani_a_odebrani(self, logged_in, shopping_list_id):
        logged_in.post(
            f"/seznam/{shopping_list_id}/pridat", data={"name": "Káva zrnková"},
            follow_redirects=False,
        )
        katalog = logged_in.get("/katalog").text
        item_id = re.search(r'/katalog/(\d+)/oblibene', katalog).group(1)

        logged_in.post(f"/katalog/{item_id}/oblibene", follow_redirects=False)
        assert "Káva zrnková" in logged_in.get("/oblibene").text

        favorite_id = re.search(r'/oblibene/(\d+)/smazat', logged_in.get("/oblibene").text).group(1)
        logged_in.post(f"/oblibene/{favorite_id}/smazat", follow_redirects=False)
        assert "Káva zrnková" not in logged_in.get("/oblibene").text


class TestZdravi:
    def test_health_endpoint(self, client):
        assert client.get("/zdravi").json()["status"] == "ok"


class TestNapojeniNaKatalog:
    def test_zkraceny_nazev_se_napoji_na_polozku_z_letaku(self, db):
        from app.models import CatalogItem
        from app.services import find_similar_catalog_item
        from app.text_utils import normalize

        name = "Jogurt bílý Hollandia 400 g"
        db.add(CatalogItem(name=name, norm_name=normalize(name)))
        db.flush()

        found = find_similar_catalog_item(db, "Jogurt bílý Hollandia")
        assert found is not None and found.name == name

    def test_nejednoznacny_nazev_se_nenapoji(self, db):
        from app.models import CatalogItem
        from app.services import find_similar_catalog_item
        from app.text_utils import normalize

        for name in ["Mléko polotučné 1 l", "Mléko plnotučné 1 l"]:
            db.add(CatalogItem(name=name, norm_name=normalize(name)))
        db.flush()
        # "Mléko p" sedí na obě položky, takže se radši nenapojí ani na jednu
        assert find_similar_catalog_item(db, "Mléko p") is None

    def test_prilis_kratky_nazev_se_nenapoji(self, db):
        from app.models import CatalogItem
        from app.services import find_similar_catalog_item
        from app.text_utils import normalize

        db.add(CatalogItem(name="Sůl kamenná", norm_name=normalize("Sůl kamenná")))
        db.flush()
        assert find_similar_catalog_item(db, "Sůl") is None
