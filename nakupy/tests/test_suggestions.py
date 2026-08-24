"""Doporuceni podle historie a filtrovani platnych slev."""
from __future__ import annotations

import datetime as dt

from app.models import CatalogItem, Price, Purchase, Store
from app.suggestions import active_prices, deals, frequent_items
from app.text_utils import normalize


def _add_purchases(session, name: str, days_ago: list[int]) -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for offset in days_ago:
        session.add(
            Purchase(
                norm_name=normalize(name),
                name=name,
                qty=1,
                unit="ks",
                price=20.0,
                bought_at=now - dt.timedelta(days=offset),
            )
        )
    session.flush()


class TestFrequentItems:
    def test_serazeno_podle_toho_co_uz_melo_dojit(self, db):
        # mleko: kazdych ~7 dni, naposledy pred 8 dny -> uz melo dojit
        _add_purchases(db, "Mléko", [8, 15, 22, 29])
        # ryze: kazdych ~30 dni, koupena vcera -> zatim netreba
        _add_purchases(db, "Rýže", [1, 31, 61])

        result = frequent_items(db, limit=10)
        names = [s.name for s in result]
        assert names[0] == "Mléko"
        assert result[0].is_due is True
        assert next(s for s in result if s.name == "Rýže").is_due is False

    def test_spocita_obvykly_interval(self, db):
        _add_purchases(db, "Máslo", [2, 9, 16, 23])
        suggestion = next(s for s in frequent_items(db) if s.name == "Máslo")
        assert suggestion.avg_interval_days == 7
        assert suggestion.count == 4

    def test_jednorazovy_nakup_nema_interval(self, db):
        _add_purchases(db, "Gril", [40])
        suggestion = next(s for s in frequent_items(db) if s.name == "Gril")
        assert suggestion.avg_interval_days is None
        assert suggestion.is_due is False

    def test_vylouci_polozky_uz_na_seznamu(self, db):
        _add_purchases(db, "Chléb", [3, 10])
        names = [s.name for s in frequent_items(db, exclude_norm={normalize("Chléb")})]
        assert "Chléb" not in names

    def test_stara_historie_se_nepocita(self, db):
        _add_purchases(db, "Vánoční kapr", [400, 760])
        assert not [s for s in frequent_items(db, days=180) if s.name == "Vánoční kapr"]

    def test_vysvetleni_u_dosle_polozky(self, db):
        _add_purchases(db, "Káva", [35, 65, 95])
        suggestion = next(s for s in frequent_items(db) if s.name == "Káva")
        assert suggestion.is_due is True
        assert "kupujete zhruba každých 30 dní" in suggestion.reason

    def test_vysvetleni_u_bezne_polozky(self, db):
        _add_purchases(db, "Rum", [10, 40, 70])
        suggestion = next(s for s in frequent_items(db) if s.name == "Rum")
        assert suggestion.reason == "koupeno 3×, naposledy před 10 dny"


class TestAktivniSlevy:
    def _item(self, db, name: str) -> CatalogItem:
        item = CatalogItem(name=name, norm_name=normalize(name))
        db.add(item)
        db.flush()
        return item

    def test_platna_sleva_se_zobrazi(self, db):
        item = self._item(db, "Máslo v akci")
        today = dt.date.today()
        db.add(
            Price(
                item_id=item.id,
                price=49.9,
                original_price=79.9,
                is_discount=True,
                valid_from=today - dt.timedelta(days=1),
                valid_to=today + dt.timedelta(days=3),
            )
        )
        db.flush()
        assert item.id in active_prices(db)

    def test_prosla_sleva_se_nezobrazi(self, db):
        item = self._item(db, "Staré máslo")
        db.add(
            Price(
                item_id=item.id,
                price=49.9,
                is_discount=True,
                valid_to=dt.date.today() - dt.timedelta(days=1),
            )
        )
        db.flush()
        assert item.id not in active_prices(db)

    def test_budouci_sleva_se_zatim_nezobrazi(self, db):
        item = self._item(db, "Budoucí sleva")
        db.add(
            Price(
                item_id=item.id,
                price=10.0,
                is_discount=True,
                valid_from=dt.date.today() + dt.timedelta(days=2),
            )
        )
        db.flush()
        assert item.id not in active_prices(db)

    def test_nejvyssi_sleva_je_prvni(self, db):
        maly = self._item(db, "Malá sleva")
        velky = self._item(db, "Velká sleva")
        db.add(Price(item_id=maly.id, price=90.0, original_price=100.0, is_discount=True))
        db.add(Price(item_id=velky.id, price=40.0, original_price=100.0, is_discount=True))
        db.flush()
        assert deals(db)[0].item_id == velky.id

    def test_filtr_podle_obchodu(self, db):
        store = db.query(Store).first()
        item = self._item(db, "Sleva jen v Kauflandu")
        db.add(Price(item_id=item.id, price=10.0, is_discount=True, store_id=store.id))
        db.flush()
        assert item.id in active_prices(db, store_id=store.id)
        assert item.id not in active_prices(db, store_id=store.id + 1)
