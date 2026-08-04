#!/usr/bin/env node
/**
 * HOPLA — raster asset build (stage 1: render).
 *
 * Rasterises the generated SVG artwork at two widths so the page can ship real
 * `srcset` responsive images, and renders the favicon / PWA / Open Graph
 * artwork from the logo mark.
 *
 *   node scripts/build-images.js && python3 scripts/optimise-images.py
 *
 * Requires Playwright's Chromium. Nothing here runs at request time — output
 * is committed, and the site itself has no build step.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const CHROME = process.env.CHROME_PATH || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const ROOT = path.resolve(__dirname, '..');
const ART = path.join(ROOT, 'assets/img/art');
const IMG = path.join(ROOT, 'assets/img');
const ICONS = path.join(ROOT, 'assets/icons');

const ART_WIDTHS = [640, 1280];
const MARK = fs.readFileSync(path.join(IMG, 'logo-mark.svg'), 'utf8');

/** Render arbitrary markup at an exact pixel size. */
async function render(browser, html, width, height, out, scale = 1) {
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: scale,
  });
  await page.setContent(
    `<style>html,body{margin:0;padding:0;overflow:hidden;background:transparent}</style>${html}`,
    { waitUntil: 'load' }
  );
  await page.screenshot({ path: out, omitBackground: true });
  await page.close();
}

/** The mark centred on a rounded brand-gradient tile — used for app icons. */
function iconTile(size, { padding = 0.19, bg = true, radius = 0.225 } = {}) {
  const pad = Math.round(size * padding);
  const r = bg ? Math.round(size * radius) : 0;
  const plate = bg
    ? `<rect width="${size}" height="${size}" rx="${r}" fill="#0e1020"/>`
    : '';
  return `<div style="width:${size}px;height:${size}px;position:relative">
    <svg width="${size}" height="${size}" style="position:absolute;inset:0">${plate}</svg>
    <div style="position:absolute;inset:${pad}px">${MARK.replace(
      '<svg',
      '<svg style="width:100%;height:100%"'
    )}</div>
  </div>`;
}

/** Maskable icons must survive a circular crop, so the mark sits smaller. */
function maskableTile(size) {
  return `<div style="width:${size}px;height:${size}px;background:#0e1020;display:grid;place-items:center">
    <div style="width:${Math.round(size * 0.52)}px">${MARK.replace(
    '<svg',
    '<svg style="width:100%;height:100%"'
  )}</div>
  </div>`;
}

/** Open Graph / Twitter card: 1200×630 brand plate. */
function ogCard() {
  return `<div style="width:1200px;height:630px;position:relative;overflow:hidden;
      background:#0e1020;font-family:system-ui,sans-serif">
    <div style="position:absolute;inset:0;background:
      radial-gradient(52% 62% at 14% 6%, rgba(255,158,44,.34), transparent 62%),
      radial-gradient(48% 58% at 92% 22%, rgba(255,92,62,.30), transparent 60%),
      radial-gradient(62% 68% at 74% 104%, rgba(124,92,255,.34), transparent 64%)"></div>
    <div style="position:absolute;inset:0;display:flex;flex-direction:column;
        justify-content:center;gap:34px;padding:0 82px">
      <div style="display:flex;align-items:center;gap:20px">
        <div style="width:82px">${MARK.replace('<svg', '<svg style="width:100%;height:100%"')}</div>
        <span style="font:800 58px Outfit,system-ui;letter-spacing:-.04em;color:#fff7ef">HOPLA</span>
      </div>
      <div style="font:800 68px/1.08 Outfit,system-ui;letter-spacing:-.045em;color:#fff7ef;max-width:16ch">
        Dětská oslava, na&nbsp;kterou se&nbsp;nezapomíná.
      </div>
      <div style="font:400 27px/1.5 Inter,system-ui;color:rgba(255,247,239,.72);max-width:36ch">
        Skákací hrady a nafukovací atrakce s dovozem po celé jižní Moravě.
        Přivezeme, postavíme, odvezeme.
      </div>
    </div>
  </div>`;
}

const FONT_CSS = `<style>
  @font-face{font-family:Outfit;src:url('file://${path.join(ROOT, 'assets/fonts/outfit-var.woff2')}') format('woff2-variations');font-weight:400 800}
  @font-face{font-family:Inter;src:url('file://${path.join(ROOT, 'assets/fonts/inter-var.woff2')}') format('woff2-variations');font-weight:300 800}
</style>`;

async function main() {
  const browser = await chromium.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--force-color-profile=srgb', '--hide-scrollbars', '--allow-file-access-from-files'],
  });

  // ------------------------------------------------------------- artwork
  const files = fs.readdirSync(ART).filter((f) => f.endsWith('.svg'));
  for (const file of files) {
    const svg = fs.readFileSync(path.join(ART, file), 'utf8');
    const base = file.replace(/\.svg$/, '');
    for (const w of ART_WIDTHS) {
      const h = Math.round((w * 3) / 4);
      const html = `<div style="width:${w}px;height:${h}px">${svg.replace(
        '<svg',
        '<svg style="display:block;width:100%;height:100%"'
      )}</div>`;
      await render(browser, html, w, h, path.join(ART, `${base}-${w}.png`));
    }
  }
  console.log(`✓ artwork: ${files.length} × ${ART_WIDTHS.length} widths`);

  // -------------------------------------------------------------- icons
  for (const size of [180, 192, 256, 512]) {
    await render(browser, iconTile(size), size, size, path.join(ICONS, `icon-${size}.png`));
  }
  await render(browser, maskableTile(512), 512, 512, path.join(ICONS, 'icon-maskable-512.png'));
  for (const size of [16, 32, 48]) {
    await render(browser, iconTile(size, { padding: 0.12, radius: 0.2 }), size, size,
      path.join(ICONS, `favicon-${size}.png`));
  }
  console.log('✓ app icons');

  // ----------------------------------------------------------------- og
  await render(browser, FONT_CSS + ogCard(), 1200, 630, path.join(IMG, 'og-cover.png'));
  console.log('✓ open graph card');

  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
