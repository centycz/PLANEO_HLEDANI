# Nákupy — privátní nákupní aplikace

Webová aplikace pro nasazení na vlastní VPS. Jeden člověk zadá, co je potřeba
koupit, druhý (nákupčí) to v obchodě odškrtá. Aplikace k tomu přidá aktuální
slevy z letáku, seřadí seznam podle úseků obchodu a připomene, co se obvykle
kupuje pravidelně.

Běží vedle stávajících aplikací na stejném serveru — na `127.0.0.1:8081`,
navenek ji pouští nginx jako `nakupy.dalcortile.cz`.

## Co umí

| Funkce | Kde |
|---|---|
| Zadání seznamu, množství, poznámky, priorita, „lze nahradit" | `/seznam/{id}` |
| Hromadné vložení (jedna položka na řádek, `2x mléko`) | `/seznam/{id}` |
| Režim nákupčího — seřazeno podle úseků, odškrtávání jedním klepnutím, zápis ceny | `/nakup/{id}` |
| Průběžné sledování nákupu zadavatelem (kolik je hotovo, kolik utraceno) | `/` a `/seznam/{id}` |
| Aktuální slevy z letáku vč. platnosti a % slevy | `/slevy` |
| Označení položek na seznamu, které jsou zrovna v akci | `/nakup/{id}` |
| Oblíbené položky pro rychlé přidání | `/oblibene` |
| Doporučení podle historie („kupujete každých 7 dní, naposledy před 8 dny") | `/` |
| Načtení katalogu i letáku z nahraného PDF s kontrolou před zápisem | `/import` |
| Historie nákupů a útrata po měsících | `/historie` |
| Trasa obchodem — vlastní pořadí úseků pro každý obchod | `/nastaveni/rozlozeni/{id}` |
| Uživatelé a role (zadavatel / nákupčí / oboje / admin) | `/nastaveni` |

Aplikace je PWA — na telefonu se dá přidat na plochu a chová se jako appka.

## Jak funguje řazení podle obchodu

Každá položka patří do úseku (ovoce a zelenina, pečivo, mléčné…). Úsek se
odhaduje z názvu podle klíčových slov a jde ho ručně přepsat. V nastavení se
u každého obchodu dá určit pořadí úseků tak, jak jimi v tom konkrétním obchodě
procházíš — nákupčímu se pak seznam seřadí do jedné trasy a nemusí se vracet.

## Import PDF

Katalogy a letáky mají u každého řetězce jinou strukturu, takže se import dělá
ve dvou krocích:

1. **Nahrání** — PDF se zpracuje na pozadí (`pdfplumber`, tabulky i prostý text).
   Vytáhnou se dvojice název + cena, u letáku i původní cena a platnost.
2. **Kontrola** — na `/import/{id}` uvidíš nalezené řádky, můžeš je opravit,
   doplnit úsek a zaškrtnout, co se má zapsat. Do katalogu jde jen potvrzené.

U letáku vyplň platnost od–do; po jejím uplynutí se sleva sama přestane
zobrazovat. Sken bez textové vrstvy (obrázkové PDF) přečíst nejde — takové
položky se zadají ručně.

## Doporučení podle historie

Při dokončení nákupu se koupené položky zapíšou do historie. Z ní se počítá,
jak často se položka kupuje (medián intervalu mezi nákupy) a kdy naposledy.
Když od posledního nákupu uplynulo aspoň 80 % obvyklého intervalu, položka se
nabídne zvýrazněná jako „nejspíš došla".

## Vývoj lokálně

```bash
cd nakupy
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # NAKUPY_DATA_DIR=./data pro lokální běh
.venv/bin/uvicorn app.main:app --reload
```

Aplikace poběží na <http://127.0.0.1:8000>, přihlásíš se údaji z `.env`.

Testy:

```bash
.venv/bin/python -m pytest
```

## Nasazení na VPS

Návod krok za krokem je v [`deploy/PRVNI_NASAZENI.md`](deploy/PRVNI_NASAZENI.md).
Ve zkratce: `docker compose up -d --build`, nginx vhost z `deploy/nginx/`,
`certbot --nginx -d nakupy.dalcortile.cz`. Aktualizace pak `./deploy/deploy.sh`.

## Struktura

```
nakupy/
├── app/
│   ├── main.py           # FastAPI aplikace, přehled, health check
│   ├── models.py         # databázový model (SQLite přes SQLAlchemy)
│   ├── routes/           # seznamy, režim nákupčího, katalog, import, nastavení
│   ├── pdf_import.py     # čtení položek z PDF katalogu a letáku
│   ├── suggestions.py    # doporučení z historie, platné slevy, řazení podle obchodu
│   ├── services.py       # operace nad seznamem a historií
│   ├── templates/        # Jinja2 šablony (čeština, mobil na prvním místě)
│   └── static/           # CSS, JS, PWA manifest, service worker
├── deploy/               # nginx, systemd, deploy.sh, návod
├── tests/                # pytest (73 testů)
├── Dockerfile
└── docker-compose.yml
```

## Konfigurace

Vše přes proměnné prostředí, viz [`.env.example`](.env.example). Podstatné:

- `NAKUPY_SECRET_KEY` — podepisuje session cookie, na produkci nastav náhodný
- `NAKUPY_DATA_DIR` — kam se ukládá databáze a nahraná PDF
- `NAKUPY_ADMIN_USER` / `NAKUPY_ADMIN_PASSWORD` — první účet při prvním startu
- `NAKUPY_SECURE_COOKIES` — na produkci za HTTPS nech `true`
