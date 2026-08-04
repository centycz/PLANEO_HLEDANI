# HOPLA — značka

## Pozice

**HOPLA** pronajímá skákací hrady a nafukovací atrakce na dětské oslavy
v Brně a na jižní Moravě. Atrakci přiveze, postaví, zajistí a po skončení
odveze.

Cílová skupina: **rodiče dětí 2–12 let z jižní Moravy**, sekundárně školy,
obce a firmy.

### Slib

> Radost přivezeme až k vám. Vy se staráte jen o oslavu.

### Co značku odlišuje

Běžné české půjčovny prodávají **atrakci**. HOPLA prodává **klid rodiče** —
že se o techniku, bezpečnost i úklid nemusí starat. Odtud plyne celý tón:
věcný, konkrétní, bez nadsázky a bez vykřičníků.

### Tón hlasu

| Ano | Ne |
| --- | --- |
| „Přivezeme, postavíme, odvezeme." | „TA NEJLEPŠÍ ZÁBAVA!!!" |
| Konkrétní čísla: 4,5 × 4,0 m, 8 dětí | „Velký hrad pro spoustu dětí" |
| Přiznaná omezení: „potřebuje 8 × 7 metrů" | Zamlčení nevýhod |
| Klidná jistota | Nadšené superlativy |

Píšeme, jako když vysvětlujeme sousedovi. Krátké věty. Žádný marketingový
žargon. Když něco nejde, řekneme to rovnou.

---

## Logo

Značku nese **oblouk** — vstupní portál nafukovacího hradu — a **bod**,
dítě zachycené uprostřed skoku.

- `assets/img/logo-mark.svg` — samotná značka
- V hlavičce a patičce je značka vložená inline v `index.html`, aby dědila
  barvu textu a nestála žádný request.

### Pravidla

- **Ochranná zóna**: minimálně výška bodu (≈ 21 % šířky značky) ze všech stran.
- **Minimální velikost**: 16 px. Pod 24 px používejte jen značku bez nápisu.
- **Nápis**: Outfit ExtraBold (800), prostrkání −0,045 em, verzálky.
- **Na fotografii**: značka v plné barvě, nápis bílý. Vždy na tmavším místě
  snímku nebo přes ztmavovací vrstvu.
- **Nedělat**: neotáčet, nedeformovat, nepřebarvovat gradient, nepřidávat
  stín ani obrys, nevkládat do rámečku.

---

## Barvy

Koncept **„Letní odpoledne"** — zlatá hodina zahradní oslavy.

| Token | Hex | Role |
| --- | --- | --- |
| `--c-ink` | `#0e1020` | Základ, text, tmavé sekce |
| `--c-coral` | `#ff5c3e` | Primární akce (jen CTA) |
| `--c-mango` | `#ff9e2c` | Světlo, radost, akcenty |
| `--c-aqua` | `#19c9e8` | Voda, svěžest |
| `--c-grape` | `#7c5cff` | Kouzlo, fokus prvků |
| `--c-lime` | `#8be86b` | Tráva, bezpečí, „volno" |
| `--c-cream` | `#fff7ef` | Světlý podklad |

Neutrály jsou **teple tónované** (`--n-*`), nikdy čistě šedé — šedá působí
lacině.

### Gradienty

| Token | Použití |
| --- | --- |
| `--grad-sunset` | Primární tlačítko, hlavní akcenty |
| `--grad-splash` | Voda, atrakce |
| `--grad-meadow` | Bezpečí, potvrzení |
| `--grad-candy` | Doplňkové služby |
| `--grad-text` | Gradientní text (statistiky, akcenty) |

### Pravidlo kontrastu

Veškerý text splňuje **WCAG AA** (4,5 : 1 pro běžný text, 3 : 1 pro velký).
Ověřeno Lighthouse — kategorie Accessibility 100/100.

---

## Typografie

| Řez | Písmo | Použití |
| --- | --- | --- |
| Display | **Outfit** 400–800 | Nadpisy, čísla, ceny, tlačítka, logo |
| Text | **Inter** 300–800 | Běžný text, UI, formuláře |

Obě písma jsou **self-hostovaná** a podmnožena na latin + latin-ext
(kompletní česká diakritika). Dohromady **85 kB, dva requesty**.

Velikostní škála je plynulá (`clamp()`) mezi 360 px a 1440 px — viz
`--fs-*` v `assets/css/tokens.css`.

---

## Ikonografie

Vlastní sada, mřížka 24 × 24, tah 1,75, zakulacené konce. Geometrie
navazuje na tvarosloví značky: oblouky, kruhy, měkké rohy.

Zdroj: `assets/icons/sprite.svg`. Do `index.html` je sada vložená inline,
takže ikony nestojí žádný request a nikdy neproblikávají.

---

## Obrazový styl

Web má **jeden obrazový systém**: sytá gradientová plocha nesoucí motiv
oblouku ze značky, měkké světlo, jemné zrno a ikonu atrakce.

Generuje ho `scripts/build-artwork.py` do `assets/img/art/`.

> **Až budou k dispozici fotografie**, nahradí se dlaždice souborem stejného
> jména: `assets/img/art/<id>-640.webp` a `<id>-1280.webp`, poměr 4 : 3.
> V kódu se nemění nic. Doporučené zadání pro fotografa je v
> `docs/ARCHITECTURE.md`.

Fotografie mají být: reportážní, v protisvětle, s dětmi v pohybu,
bez pózování a bez stock estetiky.
