# HOPLA — web půjčovny skákacích hradů

Prémiový web pro pronájem skákacích hradů a nafukovacích atrakcí.
Brno a jižní Morava.

**Statický web bez runtime závislostí.** Prohlížeč dostane HTML, jeden CSS
soubor, ES moduly a WebP obrázky — žádný framework, žádný build při nasazení.

## Spuštění

```bash
python3 -m http.server 8000     # jakýkoli statický server
```

Otevřete `http://localhost:8000`. Service worker se registruje jen přes
HTTPS, takže lokálně nepřekáží.

## Výkon

Naměřeno Lighthouse proti serveru s gzipem a cache hlavičkami:

| | Performance | Accessibility | Best Practices | SEO |
| --- | --- | --- | --- | --- |
| Desktop | **100** | **100** | **100** | **100** |
| Mobil | **99** | **100** | **100** | **100** |

FCP 0,3 s · LCP 0,5 s · TBT 0 ms · CLS 0 (desktop).

## Co web umí

- Fullscreen hero (čisté CSS — nula bajtů obrázků nad ohybem)
- Filtrovatelný katalog 10 atrakcí
- Interaktivní kalendář obsazenosti napojený na datovou vrstvu
- Třístupňový rezervační formulář s průběžným výpočtem ceny
- Mapa rozvozových zón s ověřením města
- Fotogalerie s lightboxem, recenze, FAQ
- PWA — manifest, service worker, offline stránka
- Mouse parallax, glassmorphism, reveal animace, mikrointerakce
- Plně respektuje `prefers-reduced-motion`

## Struktura

```
index.html            web (obsah přímo v HTML kvůli SEO a LCP)
design-system.html    živý přehled designového systému
assets/css/           tokens → base → components → sections  (+ generovaný bundle)
assets/js/lib/api.js  ★ datová vrstva rezervací
assets/data/*.json    katalog, doplňky, dostupnost, zóny, recenze, FAQ
scripts/              build nástroje (nespouští se za běhu)
docs/                 značka, designový systém, architektura
```

## Napojení na rezervační systém

Žádná část UI nesahá na `fetch` ani na JSON přímo — všechno jde přes
`BookingClient`. Přepnutí na backend je **jedna řádka** v `assets/js/main.js`:

```js
const api = createClient({ mode: 'http', baseUrl: '/api/v1' });
```

Kontrakt, který má backend splnit, je v [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md);
soubory v `assets/data/` slouží zároveň jako specifikace API.

## Přidání atrakce nebo služby

Bez zásahu do kódu — stačí záznam v `assets/data/attractions.json`
(resp. `addons.json`). Objeví se v rezervačním formuláři i ve výpočtu ceny.

## Build nástroje

Spouští se ručně po změně zdrojů, výstup je commitnutý:

```bash
node scripts/build-css.js          # CSS zdroje → assets/css/hopla.css
python3 scripts/build-artwork.py   # → assets/img/art/*.svg
node scripts/build-images.js       # SVG → PNG, PWA ikony, OG karta
python3 scripts/optimise-images.py # PNG → WebP, favicon.ico
```

## Obrázky

Dlaždice v `assets/img/art/` jsou **zástupné**. Skutečné fotografie se vloží
jako soubory stejného jména (`<id>-640.webp`, `<id>-1280.webp`, poměr 4 : 3) —
v kódu se nemění nic. Podrobnosti a zadání pro fotografa v
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Dokumentace

- [`docs/BRAND.md`](docs/BRAND.md) — pozice, tón, logo, barvy, typografie
- [`docs/DESIGN-SYSTEM.md`](docs/DESIGN-SYSTEM.md) — tokeny, komponenty, přístupnost
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — datová vrstva, výkon, rozšiřitelnost

## Licence

Písma Outfit a Inter — SIL Open Font License 1.1 (`assets/fonts/OFL.txt`).
