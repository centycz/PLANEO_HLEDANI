#!/usr/bin/env python3
"""
HOPLA — raster asset build (stage 2: optimise).

Converts the PNGs produced by build-images.js into WebP, assembles the
multi-resolution favicon.ico, and drops the intermediate PNGs that the site
does not ship. Run after `node scripts/build-images.js`.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets/img/art"
IMG = ROOT / "assets/img"
ICONS = ROOT / "assets/icons"

QUALITY = 82


def to_webp(png: Path, quality: int = QUALITY, keep_png: bool = False) -> Path:
    out = png.with_suffix(".webp")
    with Image.open(png) as im:
        im = im.convert("RGB") if im.mode in ("RGBA", "P") and not keep_png else im
        im.save(out, "WEBP", quality=quality, method=6)
    if not keep_png:
        png.unlink()
    return out


def main() -> None:
    total_before = total_after = 0

    # Artwork → WebP (the site never loads the PNG)
    for png in sorted(ART.glob("*-*.png")):
        total_before += png.stat().st_size
        out = to_webp(png)
        total_after += out.stat().st_size
    print(f"✓ artwork → webp   {total_before/1024:.0f} kB → {total_after/1024:.0f} kB")

    # Open Graph card: keep PNG too — a few crawlers still refuse WebP.
    og = IMG / "og-cover.png"
    if og.exists():
        with Image.open(og) as im:
            im.convert("RGB").save(IMG / "og-cover.webp", "WEBP", quality=88, method=6)
        print("✓ og card")

    # favicon.ico from the small square renders
    sizes = [16, 32, 48]
    frames = []
    for s in sizes:
        p = ICONS / f"favicon-{s}.png"
        if p.exists():
            frames.append(Image.open(p).convert("RGBA"))
    if frames:
        frames[0].save(ROOT / "favicon.ico", format="ICO",
                       sizes=[(s, s) for s in sizes])
        for s in sizes:
            (ICONS / f"favicon-{s}.png").unlink(missing_ok=True)
        print(f"✓ favicon.ico ({', '.join(f'{s}×{s}' for s in sizes)})")

    # PWA icons stay PNG — the manifest spec is best supported that way.
    for p in sorted(ICONS.glob("icon-*.png")):
        with Image.open(p) as im:
            im.save(p, "PNG", optimize=True)
    print("✓ pwa icons optimised")


if __name__ == "__main__":
    main()
