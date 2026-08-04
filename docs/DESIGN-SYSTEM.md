# Designový systém

Zdroj pravdy je `assets/css/tokens.css`. **Nikde v kódu nesmí být natvrdo
zapsaná barva, rádius, stín ani doba trvání animace** — vždy token.

Živý přehled: [`design-system.html`](../design-system.html).

---

## 1. Barvy

Primitivy (`--c-*`) se nikdy nemění. Mění se jen jejich **sémantické
přiřazení** — proto stačí u tmavých bloků přepnout `[data-theme="dark"]`
a všechno ostatní funguje beze změny.

```
--c-ink --c-coral --c-mango --c-aqua --c-grape --c-lime --c-cream
        ↓ sémantika
--surface-page  --surface-raised  --surface-sunken  --surface-inverse
--text-strong   --text-body       --text-muted      --text-faint
--border-subtle --border-default  --border-strong
--status-ok / -warn / -busy / -info
```

Kanály jsou uložené i jako trojice (`--rgb-coral: 255 92 62`), takže lze
skládat průhlednost bez druhé proměnné:

```css
background: rgb(var(--rgb-coral) / 0.12);
```

## 2. Typografie

```
--fs-2xs  11px       --fs-xl   22→28    Nadpis karty
--fs-xs   12px       --fs-2xl  26→38    H3 sekce
--fs-sm   13px       --fs-3xl  32→52    H2 sekce
--fs-base 15→16px    --fs-4xl  40→72    Prohlášení
--fs-md   16→18px    --fs-hero 44→100   H1 hero
--fs-lg   18→22px
```

Vše `clamp()` mezi 360 px a 1440 px — mezi breakpointy nikdy „neskáče".

Prostrkání se s velikostí **utahuje**: `--tracking-tighter` (−0,045 em) pro
hero, `--tracking-normal` pro běžný text.

## 3. Mřížka a prostor

Základ 4 px. `--sp-1` … `--sp-40`.

```
--container       1240px
--container-wide  1440px
--container-text  68ch
--gutter          18→40px  (clamp)
--section-y       72→144px (clamp)
```

## 4. Rádiusy

`6 · 10 · 14 · 20 · 28 · 36 · 48 · 999 px` — štědré a měkké. Tvarosloví
značky je „skákavé", proto se ostré rohy nepoužívají nikde.

## 5. Elevace

Stíny jsou **teple tónované** (`rgb(var(--rgb-ink) / …)`), nikdy neutrálně
šedé. Šedý stín působí lacině.

`--sh-xs` … `--sh-2xl`, plus `--sh-glow-warm` / `--sh-glow-cool` pro
svítící CTA.

## 6. Sklo (glassmorphism)

Jeden recept, jeden token:

```css
.glass {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  backdrop-filter: var(--glass-blur);   /* saturate(180%) blur(20px) */
}
```

Varianta `.glass--dark` pro tmavý podklad. Kde `backdrop-filter` chybí,
`@supports` degraduje na neprůhledné pozadí — nikdy nečitelný text.

## 7. Pohyb

```
--dur-instant  90ms    --ease-out     cubic-bezier(.16,1,.30,1)   expo, „Apple"
--dur-fast    160ms    --ease-in-out  cubic-bezier(.65,0,.35,1)
--dur-base    240ms    --ease-spring  cubic-bezier(.34,1.56,.64,1) přestřel
--dur-slow    420ms    --ease-soft    cubic-bezier(.32,.72,0,1)
--dur-slower  680ms
--dur-reveal  900ms
```

Pravidla:

- **Hover na tlačítku** `--dur-fast` + `--ease-spring` (posun −2 px).
- **Reveal při scrollu** `--dur-reveal` + `--ease-out`, prodleva po 60–80 ms.
- **Mouse parallax** píše JS jen `--px` / `--py`; tlumení dělá CSS.
- `prefers-reduced-motion` přepíše **všechny** doby na 1 ms. Každá animace je
  psaná tak, že její odebrání nechá správný, plně viditelný koncový stav.

## 8. Hladiny (z-index)

Jediný žebřík, nikde jinde se magická čísla nepoužívají:

```
behind −1 · base 1 · raised 10 · sticky 100 · header 200
drawer 300 · overlay 400 · modal 500 · toast 600
```

## 9. Fokus

Jedna definice pro celý web (`--focus-ring`), viditelná jen pro klávesnici
(`:focus-visible`). Na tmavém podkladu se automaticky přepne na
`--focus-ring-dark`.

---

## Komponenty

| Komponenta | Třída | Varianty |
| --- | --- | --- |
| Tlačítko | `.btn` | `--primary` `--secondary` `--glass` `--ghost` `--ink` `--lg` `--sm` `--icon` `--block` |
| Karta | `.card` | `--interactive` `--glass` `--ink` `--spotlight` |
| Odznak | `.badge` | `--ok` `--warn` `--busy` `--info` `--brand` `--glass` |
| Filtr | `.chip` | `aria-pressed` |
| Pole | `.input` `.select` `.textarea` | `aria-invalid` |
| Volba | `.option-card` | `:has(input:checked)` |
| Sklo | `.glass` | `--dark` |
| Ikona | `.icon` | `--lg` `--xl` `--fill` |
| Dlaždice ikony | `.icon-tile` | `--splash` `--meadow` `--candy` `--soft` |
| Skeleton | `.skeleton` | — |
| Toast | `.toast` | `--ok` `--err` |

### Zásady

1. **Jedna primární akce na obrazovku.** `.btn--primary` je vyhrazené pro
   rezervaci; nikde jinde se dvě primární tlačítka vedle sebe neobjeví.
2. **Karta je klikatelná celá**, ale odkaz je jen jeden (`.card__link::after`)
   — čtečka obrazovky tak ohlásí jeden cíl, ne pět.
3. **Ikona nikdy nenese význam sama.** Vždy má vedle sebe text nebo
   `aria-label`.
4. **Formulář validuje až při odeslání kroku**, ne při psaní — a chybu
   pojmenuje česky a konkrétně („Telefon vypadá na příliš krátký."), nikdy
   obecně („Neplatná hodnota").

---

## Přístupnost

Ověřeno: **Lighthouse Accessibility 100/100** (desktop i mobil).

- Kontrast textu splňuje WCAG AA všude.
- Celý web je ovladatelný klávesnicí; `.skip-link` přeskočí na obsah.
- Lightbox drží fokus (`trapFocus`), zavírá se Escapem a vrací fokus na
  spouštěč.
- Kalendář je skupina tlačítek; každé má popisek s celým datem i stavem
  („čtvrtek 6. srpna 2026 — volno"), ne jen číslo.
- Dekorativní SVG mají `aria-hidden="true"`, obsahová `role="img"`
  s `aria-label`.
- Živé oblasti: počet výsledků filtru, výsledek ověření města a stav
  odeslání formuláře jsou `role="status"`.
- Bez JavaScriptu zůstává stránka čitelná a průchodná — mizí jen animace,
  filtrování, kalendář a odeslání formuláře (kontakt telefonem je vždy k dispozici).
