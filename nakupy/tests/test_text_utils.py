from app.text_utils import (
    clean_name,
    extract_unit,
    find_prices,
    guess_category_name,
    normalize,
    parse_price,
)


class TestParsePrice:
    def test_ceska_desetinna_carka(self):
        assert parse_price("119,90 Kč") == 119.90

    def test_tisice_s_mezerou(self):
        assert parse_price("1 249,00") == 1249.00

    def test_zapis_s_pomlckou(self):
        assert parse_price("89,-") == 89.0

    def test_bez_ceny(self):
        assert parse_price("bez ceny") is None


class TestFindPrices:
    def test_ignoruje_procenta_a_gramaz(self):
        line = "Mléko Pilos 1,5% 1 l  24,90  akce 19,90"
        assert find_prices(line, explicit_only=True) == [24.90, 19.90]

    def test_ignoruje_baleni(self):
        line = "Toaletní papír 8 ks 3 x 100 listů 129,-"
        assert find_prices(line, explicit_only=True) == [129.0]

    def test_puvodni_i_akcni_cena(self):
        assert find_prices("Máslo 250 g 59,90 Kč místo 79,90 Kč", explicit_only=True) == [
            59.90,
            79.90,
        ]


class TestNormalize:
    def test_odstrani_diakritiku_a_interpunkci(self):
        assert normalize("Máslo Jihočeské, 250 g!") == "maslo jihoceske 250 g"

    def test_prazdny_vstup(self):
        assert normalize("") == ""

    def test_clean_name_orizne_vypln(self):
        assert clean_name("Chléb konzumní ....... ") == "Chléb konzumní"


class TestExtractUnit:
    def test_litry(self):
        assert extract_unit("Mléko polotučné 1 l") == ("1 l", "l")

    def test_gramy(self):
        assert extract_unit("Máslo 250 g") == ("250 g", "g")

    def test_bez_jednotky(self):
        assert extract_unit("Chléb konzumní") == ("", "ks")


class TestGuessCategory:
    def test_pecivo(self):
        assert guess_category_name("Rohlík tukový") == "Pečivo"

    def test_drogerie(self):
        assert guess_category_name("Šampon Head&Shoulders") == "Drogerie"

    def test_mlecne(self):
        assert guess_category_name("Jogurt bílý 150 g") == "Mléčné výrobky"

    def test_nezname(self):
        assert guess_category_name("Xyzzy 42") is None


class TestStripPrices:
    def test_odstrani_cenu_i_bez_diakritiky(self):
        from app.text_utils import strip_prices

        assert strip_prices("Maslo Jihoceske 250 g 49,90 Kc") == "Maslo Jihoceske 250 g"

    def test_zachova_gramaz_a_procenta(self):
        from app.text_utils import strip_prices

        assert strip_prices("Mléko Pilos 1,5% 1 l 24,90") == "Mléko Pilos 1,5% 1 l"

    def test_zachova_hole_cislo_bez_haleru(self):
        from app.text_utils import strip_prices

        assert strip_prices("Toaletní papír 8 ks") == "Toaletní papír 8 ks"


class TestDefaultUnit:
    def test_baleni_se_kupuje_po_kusech(self):
        from app.text_utils import default_unit

        assert default_unit("Mléko polotučné 1 l") == "ks"

    def test_ovoce_bez_baleni_je_v_kilech(self):
        from app.text_utils import default_unit

        assert default_unit("Jablka Golden") == "kg"

    def test_maso_bez_baleni_je_v_kilech(self):
        from app.text_utils import default_unit

        assert default_unit("Kuřecí prsní řízek") == "kg"

    def test_ostatni_je_v_kusech(self):
        from app.text_utils import default_unit

        assert default_unit("Rohlík tukový") == "ks"


class TestKategorieDrogerie:
    def test_praci_prasek(self):
        assert guess_category_name("Prací prášek Persil 3 kg") == "Domácnost a úklid"
