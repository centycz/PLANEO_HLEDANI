# Architektura

Statický web bez runtime závislostí. Prohlížeč dostane HTML, jeden CSS
soubor, ES moduly a WebP obrázky — žádný framework, žádný server.

```
/
├── index.html                 jednostránkový web, obsah přímo v HTML (SEO, LCP)
├── offline.html               fallback service workeru
├── manifest.webmanifest       PWA
├── sw.js                      service worker
├── robots.txt, sitemap.xml
├── assets/
│   ├── css/
│   │   ├── tokens.css         ← designové tokeny (zdroj pravdy)
│   │   ├── base.css           ← reset, typografie, layout utility
│   │   ├── components.css     ← tlačítka, karty, formuláře, glass
│   │   ├── sections.css       ← jednotlivé sekce stránky
│   │   └── hopla.css          ← generovaný bundle (linkuje se ze stránek)
│   ├── js/
│   │   ├── main.js            vstupní bod
│   │   ├── lib/
│   │   │   ├── api.js         ★ datová vrstva rezervací
│   │   │   └── dom.js         DOM pomocníci
│   │   └── modules/           chrome, motion, catalog, calendar,
│   │                          media, reviews, delivery, booking
│   ├── data/                  attractions, addons, availability,
│   │                          delivery-zones, reviews, faq  (JSON)
│   ├── img/art/               generované dlaždice (SVG + WebP 640/1280)
│   ├── icons/sprite.svg       ikonová sada + PWA ikony
│   └── fonts/                 Outfit + Inter (woff2, podmnožené)
├── scripts/                   build nástroje (nespouští se za běhu)
└── docs/
```

---

## Připravenost na vlastní rezervační systém

Tohle je nosná část architektury. **Žádná část UI nesahá na `fetch` ani na
JSON přímo.** Všechno mluví s `BookingClient` z `assets/js/lib/api.js`.

```
UI moduly  →  BookingClient  →  Adapter  →  data
                                  ├── StaticAdapter  (dnes: /assets/data/*.json)
                                  └── HttpAdapter    (zítra: /api/v1/*)
```

### Přepnutí na backend

Jediná změna v celém projektu — `assets/js/main.js`:

```js
// dnes
const api = createClient();

// po nasazení rezervační služby
const api = createClient({ mode: 'http', baseUrl: '/api/v1' });
```

### Kontrakt, který musí backend splnit

| Metoda | HTTP | Odpověď |
| --- | --- | --- |
| `getAttractions()` | `GET /attractions` | `{ categories, items }` |
| `getAddons()` | `GET /addons` | `{ groups }` |
| `getDeliveryZones()` | `GET /delivery-zones` | `{ depot, zones }` |
| `getAvailability(from, to)` | `GET /availability?from=&to=` | `{ "2026-08-14": "free", … }` |
| `createReservation(draft)` | `POST /reservations` | `{ id, status, receivedAt }` |

Tvar odpovědí je přesně ten, který dnes leží v `assets/data/*.json` — soubory
slouží zároveň jako **specifikace API**.

Konvence:

- Datum vždy `YYYY-MM-DD` v lokálním čase. Rezervace na 14. srpna je 14. srpna
  bez ohledu na časové pásmo prohlížeče.
- Ceny celá čísla v Kč.
- Stavy dostupnosti: `free`, `limited`, `full`, `closed`, `off`.

### Ceny

`BookingClient.quote(draft)` počítá cenu na klientovi, aby se souhrn
přepočítával okamžitě při výběru. Vrací ale **stejný tvar**, jaký bude
vracet server (`{ lines, total, openEnded, weekend, currency }`), takže
přesun výpočtu na backend je záměna jedné metody — UI se nemění.

Po nasazení backendu je serverový výpočet **závazný**; klientský slouží jen
jako okamžitá indikace.

---

## Rozšiřitelnost nabídky

Přidání atrakce nebo služby **nevyžaduje zásah do kódu**:

| Co přidat | Kam | Co se stane |
| --- | --- | --- |
| Atrakci | `assets/data/attractions.json` → `items[]` | Objeví se v rezervačním formuláři a v ceníku |
| Doplňkovou službu | `assets/data/addons.json` → `groups[].items[]` | Objeví se ve formuláři |
| Novou kategorii | `attractions.json` → `categories[]` | Nový filtr |
| Rozvozovou zónu | `delivery-zones.json` → `zones[]` | Promítne se do ceny dopravy i do ověřovače měst |

Marketingová karta v `index.html` je zvlášť — je psaná ručně, aby text
i obrázek šly ladit nezávisle na datech. Kartu a záznam v JSON spojuje
`data-id`.

Pro **svatby, firemní akce a další segmenty** stačí přidat kategorii
a atrakce; sekce Doplňkové služby je připravená na libovolný počet skupin.

---

## Výkon

Naměřeno Lighthouse proti serveru s gzipem a cache hlavičkami (tedy tak, jak
se web chová v produkci — `scripts/` obsahuje i testovací server):

| | Performance | Accessibility | Best Practices | SEO |
| --- | --- | --- | --- | --- |
| Desktop | **100** | **100** | **100** | **100** |
| Mobil | **99** | **100** | **100** | **100** |

FCP 0,3 s · LCP 0,5 s · TBT 0 ms · CLS 0 (desktop).

Jak se toho dosáhlo:

- Obsah je **přímo v HTML** — nic se nedorenderovává JavaScriptem.
- CSS je **jeden soubor** (13,7 kB gzip), generovaný z rozdělených zdrojů.
- JS jsou **ES moduly s `type="module"`**, tedy odložené — nic neblokuje
  vykreslení. Selhání jednoho modulu nepoloží ostatní (`safely()` v `main.js`).
- Fonty **self-hostované a podmnožené** (85 kB, 2 requesty), s `preload`
  a `font-display: swap`.
- Ikony **inline v HTML** — nula requestů, nula probliknutí.
- Obrázky **WebP se `srcset`**, `loading="lazy"`, `width`/`height` u všech →
  CLS 0.
- Hero je **čisté CSS** (gradienty + SVG motiv), takže největší vykreslený
  prvek je rovnou nadpis.

### Rozpočet

| Položka | Limit |
| --- | --- |
| HTML (gzip) | 25 kB |
| CSS (gzip) | 16 kB |
| JS celkem (gzip) | 20 kB |
| Fonty | 90 kB |
| Obrázek nad ohybem | 0 |
| LCP mobil (slow 4G) | < 2,5 s |
| CLS | < 0,02 |

---

## Build nástroje

Web **nemá build step** — všechno je commitnuté. Skripty se pouštějí ručně
při změně zdrojů.

```bash
node scripts/build-css.js        # 4 CSS zdroje → assets/css/hopla.css
python3 scripts/build-artwork.py # → assets/img/art/*.svg
node scripts/build-images.js     # SVG → PNG (Chromium) + PWA ikony + OG karta
python3 scripts/optimise-images.py # PNG → WebP, favicon.ico
```

`build-css.js` má po minifikaci **ověřovací krok**: pokud v bundlu nesedí
počet složených závorek, at-pravidel, custom properties nebo data URI, build
selže a soubor se nepřepíše.

Vyžaduje Playwright Chromium (`node scripts/*`) a Pillow (`python3 scripts/*`).

---

## Až přijdou fotografie

Obrazové dlaždice jsou **zástupné**. Nahrazují se souborem stejného jména:

```
assets/img/art/hrad-kralovsky-640.webp    (640 × 480)
assets/img/art/hrad-kralovsky-1280.webp   (1280 × 960)
```

Poměr **4 : 3**, WebP kvalita 82. V kódu se nemění nic — `srcset` už na oba
soubory odkazuje.

Zadání pro fotografa:

- Reportáž, ne aranžmá. Děti v pohybu, ne pózující.
- Protisvětlo a zlatá hodina; atrakce nesmí splynout s pozadím.
- Atrakce vždy celá v záběru, s okolím zahrady — zákazník potřebuje odhadnout
  velikost.
- Vodorovný formát, hlavní motiv ve středních dvou třetinách (karty se ořezávají).
- Souhlas rodičů s použitím podobizny dětí je nutný.

### Sekce Videa z akcí

Sekce byla ze stránky odstraněna, protože bez skutečných záběrů by na
prémiovém webu působila jako výplň. Až budou záběry k dispozici, obnoví se
podle vzoru sekce Fotogalerie — komponenty (`card`, `card__media`, lightbox)
jsou v `components.css` a `media.js` připravené.
