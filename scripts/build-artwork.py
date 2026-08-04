#!/usr/bin/env python3
"""
HOPLA — artwork generator.

Produces the abstract brand tiles used wherever a photograph will eventually
go: attraction cards, gallery, section art. Each tile is a saturated gradient
field carrying the logo's arch motif, a soft bloom, fine grain and the
attraction's own icon — so a visitor reads the product type instantly while
the page keeps a single, deliberate visual language.

Replacing a tile with real photography is a file drop: save a photo as
assets/img/art/<id>-640.webp and <id>-1280.webp. Nothing else changes.

    python3 scripts/build-artwork.py && node scripts/build-images.js \
        && python3 scripts/optimise-images.py
"""
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "img" / "art"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1200, 900

# The icon paths are copied from assets/icons/sprite.svg so a tile is a single
# self-contained file — it must render correctly outside the page too.
ICONS = {
    "i-castle": '<path d="M3.4 20.4V8.6l2.3 1.4V6.4l2.6 1.5V5.2l3.7 2 3.7-2v2.7l2.6-1.5V10l2.3-1.4v11.8z"/><path d="M9.8 20.4v-4.2a2.2 2.2 0 0 1 4.4 0v4.2"/>',
    "i-slide": '<path d="M4.6 20.4V7.2h4.6"/><path d="M4.6 11.8h3.2M4.6 16.2h3.2"/><path d="M9.2 7.2c0 7.4 3.6 11 10.2 11"/><path d="M2.8 20.4h18.4"/>',
    "i-ballpit": '<path d="M3.6 10.6h16.8v5.8a3.6 3.6 0 0 1-3.6 3.6H7.2a3.6 3.6 0 0 1-3.6-3.6z"/><circle cx="7.8" cy="7.6" r="2.2"/><circle cx="13.4" cy="6.2" r="2"/><circle cx="17.8" cy="8.4" r="1.8"/>',
    "i-obstacle": '<path d="M2.8 19.8v-4.6a3.2 3.2 0 0 1 6.4 0v4.6"/><path d="M14.8 19.8v-6.6a3.6 3.6 0 0 1 7.2 0v6.6"/><path d="M2.8 19.8h19.2"/><path d="M11.4 19.8V4.6l4.2 1.6-4.2 1.8"/>',
    "i-arch": '<path d="M5.4 20.4V12a6.6 6.6 0 0 1 13.2 0v8.4"/><circle cx="12" cy="12.6" r="2.3"/>',
    "i-rings": '<circle cx="9" cy="14.4" r="5.4"/><circle cx="15" cy="14.4" r="5.4"/><path d="m12 4.4 2 2.4h-4z"/>',
    "i-droplet": '<path d="M12 3.2s6 6.2 6 10.2a6 6 0 1 1-12 0c0-4 6-10.2 6-10.2z"/>',
    "i-sparkles": '<path d="M12 3.5 13.6 8 18 9.6 13.6 11.2 12 15.7 10.4 11.2 6 9.6 10.4 8z"/><path d="M18.4 15.2l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7zM5.4 3.8l.5 1.3 1.3.5-1.3.5-.5 1.3-.5-1.3L3.6 5.6l1.3-.5z"/>',
    "i-cake": '<path d="M4.2 20.4v-5.6a2.4 2.4 0 0 1 2.4-2.4h10.8a2.4 2.4 0 0 1 2.4 2.4v5.6z"/><path d="M4.2 16.6c1.6 0 1.6 1.4 3.2 1.4s1.6-1.4 3.2-1.4 1.6 1.4 3.2 1.4 1.6-1.4 3.2-1.4 1.4 1.4 3 1.4"/><path d="M9 12.4V9.6M15 12.4V9.6M12 12.4V8.4"/><path d="M9 7.4h.01M12 6.2h.01M15 7.4h.01"/>',
    "i-users": '<circle cx="9.4" cy="8.4" r="3.4"/><path d="M3.4 19.4a6 6 0 0 1 12 0"/><path d="M16 5.4a3.4 3.4 0 0 1 0 6.5M17.2 14.2a6 6 0 0 1 3.4 5.2"/>',
    # Ship — so the pirate castle does not repeat the plain castle mark
    "i-ship": '<path d="M3.4 14.6h17.2l-2.2 5a2.4 2.4 0 0 1-2.2 1.4H7.8a2.4 2.4 0 0 1-2.2-1.4z"/><path d="M12 14.6V3.2"/><path d="M12 4.4l6.4 2.6L12 9.6z"/><path d="M12 10.6 6.6 12.4 12 14"/>',
}


def esc(v):
    return f"{v:.1f}"


def tile(name, c1, c2, c3, icon_id, *, seed=1, motif="arch", dark_text=False):
    """One artwork tile: gradient field + motif + bloom + grain + icon."""
    rng = random.Random(seed)
    uid = abs(hash(name)) % 99991
    ink = "#0e1020" if dark_text else "#ffffff"

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">']

    # ---- defs ------------------------------------------------------------
    parts.append(f'''<defs>
<linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{c1}"/>
  <stop offset="0.52" stop-color="{c2}"/>
  <stop offset="1" stop-color="{c3}"/>
</linearGradient>
<radialGradient id="bloomA{uid}" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="#ffffff" stop-opacity="0.55"/>
  <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</radialGradient>
<radialGradient id="bloomB{uid}" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="{c1}" stop-opacity="0.75"/>
  <stop offset="1" stop-color="{c1}" stop-opacity="0"/>
</radialGradient>
<radialGradient id="vig{uid}" cx="0.5" cy="0.46" r="0.72">
  <stop offset="0.55" stop-color="#0e1020" stop-opacity="0"/>
  <stop offset="1" stop-color="#0e1020" stop-opacity="0.34"/>
</radialGradient>
<filter id="grain{uid}" x="0" y="0" width="100%" height="100%">
  <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="{seed}" result="n"/>
  <feColorMatrix in="n" type="saturate" values="0"/>
</filter>
<filter id="soft{uid}" x="-30%" y="-30%" width="160%" height="160%">
  <feGaussianBlur stdDeviation="42"/>
</filter>
</defs>''')

    # ---- gradient field --------------------------------------------------
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#g{uid})"/>')

    # ---- blooms: light sources that give the flat field depth -------------
    parts.append(f'<ellipse cx="{esc(W*0.76)}" cy="{esc(H*0.18)}" rx="380" ry="330" '
                 f'fill="url(#bloomA{uid})" opacity="0.55"/>')
    parts.append(f'<ellipse cx="{esc(W*0.14)}" cy="{esc(H*0.92)}" rx="420" ry="360" '
                 f'fill="url(#bloomB{uid})" opacity="0.7"/>')

    # ---- motif: concentric arches, the logo mark scaled up ----------------
    if motif == "arch":
        cx, cy = W * 0.5, H * 0.94
        g = []
        for i in range(7):
            r = 120 + i * 88
            op = 0.16 - i * 0.017
            if op <= 0.01:
                continue
            g.append(f'<path d="M{esc(cx-r)} {esc(cy)} V{esc(cy-r*0.62)} '
                     f'a{esc(r)} {esc(r*0.86)} 0 0 1 {esc(r*2)} 0 V{esc(cy)}" '
                     f'fill="none" stroke="#ffffff" stroke-opacity="{op:.3f}" stroke-width="2.5"/>')
        parts.append("".join(g))
    elif motif == "rings":
        cx, cy = W * 0.5, H * 0.5
        g = []
        for i in range(8):
            r = 90 + i * 74
            op = 0.15 - i * 0.015
            if op <= 0.01:
                continue
            g.append(f'<circle cx="{esc(cx)}" cy="{esc(cy)}" r="{esc(r)}" fill="none" '
                     f'stroke="#ffffff" stroke-opacity="{op:.3f}" stroke-width="2.5"/>')
        parts.append("".join(g))

    # ---- floating orbs: a few soft shapes for depth of field --------------
    orbs = []
    for _ in range(4):
        ox = rng.uniform(W * 0.05, W * 0.95)
        oy = rng.uniform(H * 0.08, H * 0.9)
        orr = rng.uniform(40, 120)
        orbs.append(f'<circle cx="{esc(ox)}" cy="{esc(oy)}" r="{esc(orr)}" fill="#ffffff" '
                    f'opacity="{rng.uniform(0.05, 0.12):.3f}"/>')
    parts.append(f'<g filter="url(#soft{uid})">' + "".join(orbs) + "</g>")

    # ---- the product icon, large and unmistakable ------------------------
    path = ICONS.get(icon_id, ICONS["i-arch"])
    scale = 15.5                              # 24-unit grid → ~372px tall
    ox = W * 0.5 - 12 * scale
    oy = H * 0.5 - 12 * scale - H * 0.03
    parts.append(
        f'<g transform="translate({esc(ox)} {esc(oy)}) scale({scale})" '
        f'fill="none" stroke="{ink}" stroke-opacity="0.92" stroke-width="1.15" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</g>'
    )

    # ---- finish: vignette then grain -------------------------------------
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#vig{uid})"/>')
    parts.append(f'<rect width="{W}" height="{H}" filter="url(#grain{uid})" '
                 f'opacity="0.16" style="mix-blend-mode:overlay"/>')

    parts.append("</svg>")
    (OUT / f"{name}.svg").write_text("".join(parts), encoding="utf-8")


# Each attraction owns a colour identity, so the grid reads as a set rather
# than a rainbow. Neighbouring cards never share a dominant hue.
TILES = [
    # name,               c1,        c2,        c3,        icon,          seed, motif
    ("hrad-kralovsky",   "#ff7a3d", "#ff5c3e", "#c9285f", "i-castle",     11, "arch"),
    ("aqua-rush",        "#28d7ef", "#1b8ee8", "#3b3ce0", "i-droplet",    12, "arch"),
    ("hrad-jednorozec",  "#ff8fc4", "#e75fae", "#8b5cf6", "i-sparkles",   13, "arch"),
    ("adventure-draha",  "#9ceb6f", "#22b98c", "#0d7a86", "i-obstacle",   14, "arch"),
    ("bublina-bazen",    "#ffc247", "#ff8a4c", "#ef5da8", "i-ballpit",    15, "rings"),
    ("tobogan-xxl",      "#ffb03a", "#f4643c", "#c62f52", "i-slide",      16, "arch"),
    ("piratska-lod",     "#4f6bf0", "#3b3ce0", "#1a1c4d", "i-ship",       17, "arch"),
    ("sportik-arena",    "#5ce0c0", "#17a8a0", "#155b8a", "i-obstacle",   18, "rings"),
    ("mini-hrad",        "#a78bfa", "#7c5cff", "#2b3bd0", "i-castle",     19, "arch"),
    ("svatebni-oblouk",  "#f0c6dd", "#c9a2e8", "#8f6fd0", "i-rings",      20, "arch"),

    # gallery frames — the same language, different colour beats
    ("galerie-01",       "#ffb03a", "#ff5c3e", "#a32a6e", "i-droplet",    31, "arch"),
    ("galerie-02",       "#6f8cff", "#5b46e0", "#191a45", "i-castle",     32, "arch"),
    ("galerie-03",       "#ffd05c", "#ff8a4c", "#e0407c", "i-ballpit",    33, "rings"),
    ("galerie-04",       "#8fe86f", "#1eab8e", "#0f5f7d", "i-obstacle",   34, "arch"),
    ("galerie-05",       "#3ad9ef", "#1b8ee8", "#4536d8", "i-slide",      35, "arch"),
    ("galerie-06",       "#ffc9dd", "#d9a3ee", "#8f74e0", "i-sparkles",   36, "rings"),
]

if __name__ == "__main__":
    for name, c1, c2, c3, icon, seed, motif in TILES:
        # The pale wedding tile needs dark line-work to stay legible.
        tile(name, c1, c2, c3, icon, seed=seed, motif=motif,
             dark_text=name in {"svatebni-oblouk", "galerie-06"})
    print(f"generated {len(TILES)} artwork tiles -> {OUT}")
