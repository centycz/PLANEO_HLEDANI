#!/usr/bin/env node
/**
 * HOPLA — single-file preview build.
 *
 * Inlines the whole site — stylesheet, fonts, artwork, catalogue data and
 * every JavaScript module — into one self-contained HTML file that runs from
 * `file://`, an email attachment or any host with a strict CSP.
 *
 *   node scripts/build-standalone.js   →  dist/hopla-preview.html
 *
 * This is for sharing a preview, not for production: the real site ships
 * separate cacheable files, lazy-loads images and registers a service worker.
 * Here everything is eager and base64, so it is bigger but needs no server.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'dist');
const OUT = path.join(OUT_DIR, 'hopla-preview.html');

// `--artifact` additionally emits a fragment for hosts that supply their own
// <!doctype>/<head>/<body> shell.
const ARTIFACT = process.argv.includes('--artifact');
const OUT_ARTIFACT = path.join(OUT_DIR, 'hopla-artifact.html');

const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const b64 = (p) => fs.readFileSync(path.join(ROOT, p)).toString('base64');

let html = read('index.html');

/* ---------------------------------------------------------------- styles */
let css = read('assets/css/hopla.css');

// Fonts: swap the @font-face URLs for base64 payloads.
for (const font of ['outfit-var', 'inter-var']) {
  css = css.replace(
    new RegExp(`url\\(['"]?\\.\\./fonts/${font}\\.woff2['"]?\\)`, 'g'),
    `url(data:font/woff2;base64,${b64(`assets/fonts/${font}.woff2`)})`
  );
}

// A string replacement would read `$$` and `$&` in the injected content as
// substitution patterns; a function replacement inserts it verbatim.
html = html.replace(
  /<link rel="stylesheet" href="assets\/css\/hopla\.css">/,
  () => `<style>\n${css}\n</style>`
);

// The preload hints point at files that no longer exist here.
html = html.replace(/<link rel="preload"[^>]*>\s*/g, '');
html = html.replace(/<!--[^>]*Both faces are above the fold[\s\S]*?-->\s*/, '');

/* ---------------------------------------------------------------- images */
// Only the 640w renditions are inlined; srcset is dropped so the browser
// cannot ask for a 1280w file that is not here.
html = html.replace(/\s*srcset="[^"]*"/g, '');
html = html.replace(/\s*sizes="[^"]*"/g, '');
html = html.replace(/src="(assets\/img\/art\/[^"]+\.webp)"/g, (_, p) =>
  `src="data:image/webp;base64,${b64(p)}"`);
html = html.replace(/href="(assets\/img\/logo-mark\.svg)"/g, (_, p) =>
  `href="data:image/svg+xml;base64,${b64(p)}"`);

// Everything left that points at a file cannot resolve offline.
html = html.replace(/\s*<link rel="icon"[^>]*favicon\.ico[^>]*>/g, '');
html = html.replace(/\s*<link rel="manifest"[^>]*>/g, '');
html = html.replace(/\s*<link rel="apple-touch-icon"[^>]*>/g, '');
html = html.replace(/\s*<link rel="canonical"[^>]*>/g, '');

// Images must load eagerly: there is no network to lazy-load from, and a
// data: URI costs nothing to fetch.
html = html.replace(/\s*loading="lazy"/g, '');

/* ------------------------------------------------------------------ data */
const DATA_FILES = ['attractions', 'addons', 'availability', 'delivery-zones'];
const inlineData = Object.fromEntries(
  DATA_FILES.map((n) => [n, JSON.parse(read(`assets/data/${n}.json`))])
);

/* -------------------------------------------------------------- scripts */
/** Strips ES module syntax so the files can be concatenated into one script. */
function flatten(file) {
  return read(file)
    .replace(/^\s*import\s+[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm, '')
    .replace(/^\s*export\s+(?=(async\s+)?function|class|const|let|var)/gm, '')
    .replace(/^\s*export\s*\{[^}]*\};?\s*$/gm, '');
}

// Dependency order, since there are no imports to resolve it for us.
const MODULES = [
  'assets/js/lib/api.js',
  'assets/js/lib/dom.js',
  'assets/js/modules/chrome.js',
  'assets/js/modules/motion.js',
  'assets/js/modules/catalog.js',
  'assets/js/modules/calendar.js',
  'assets/js/modules/media.js',
  'assets/js/modules/reviews.js',
  'assets/js/modules/delivery.js',
  'assets/js/modules/booking.js',
];

const bundle = `
(() => {
'use strict';

// The static adapter normally fetches these; in the single-file build they
// are already here, so fetch is shimmed to serve them from memory.
const INLINE_DATA = ${JSON.stringify(inlineData)};
const _fetch = window.fetch.bind(window);
window.fetch = (input, init) => {
  const url = String(input && input.url ? input.url : input);
  const hit = url.match(/([\\w-]+)\\.json(?:\\?|$)/);
  if (hit && INLINE_DATA[hit[1]]) {
    return Promise.resolve(new Response(JSON.stringify(INLINE_DATA[hit[1]]), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }));
  }
  return _fetch(input, init);
};

${MODULES.map(flatten).join('\n')}

${flatten('assets/js/main.js')
  .replace(/if \('serviceWorker' in navigator[\s\S]*$/, '')}
})();
`;

// Must be a function: the bundle contains `$$` (the query-all helper), which
// a string replacement would silently collapse to a single `$`.
html = html.replace(
  /<script type="module" src="assets\/js\/main\.js"><\/script>/,
  () => `<script>\n${bundle}\n</script>`
);

html = html.replace(
  '<title>',
  '<!-- Single-file preview built by scripts/build-standalone.js -->\n<title>'
);

/* ------------------------------------------------------------ demo notice */
// The preview is shareable, and the page otherwise reads as a real company's
// site — working booking form, phone number, address, company number. HOPLA
// is invented for the design, so anyone who lands here has to be told before
// they try to book a bouncy castle from a business that does not exist.
const DEMO_NOTICE = `
<style>
  .demo-flag {
    position: fixed;
    inset-block-end: var(--sp-4);
    inset-inline-start: var(--sp-4);
    z-index: var(--z-toast);
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    max-inline-size: min(22rem, calc(100vw - 2 * var(--sp-4)));
    padding: var(--sp-3) var(--sp-4);
    border-radius: var(--r-pill);
    background: rgb(14 16 32 / 0.88);
    border: 1px solid rgb(255 247 239 / 0.18);
    -webkit-backdrop-filter: blur(16px);
    backdrop-filter: blur(16px);
    box-shadow: var(--sh-xl);
    color: var(--c-cream);
    font-family: var(--font-text);
    font-size: var(--fs-xs);
    line-height: 1.45;
  }
  .demo-flag strong { color: var(--c-mango); font-weight: 600; }
  .demo-flag button {
    margin-inline-start: auto;
    flex: none;
    inline-size: 1.5rem;
    block-size: 1.5rem;
    border-radius: 50%;
    color: rgb(255 247 239 / 0.6);
    display: grid;
    place-items: center;
    font-size: 1rem;
    line-height: 1;
  }
  .demo-flag button:hover { color: var(--c-cream); background: rgb(255 247 239 / 0.12); }
  /* Above the mobile action bar, which owns the bottom edge on small screens. */
  @media (max-width: 620px) {
    .demo-flag { inset-block-end: 5.5rem; }
  }
</style>
<aside class="demo-flag" role="note">
  <span><strong>Ukázkový návrh.</strong> HOPLA není skutečná firma —
    kontakty, ceny i recenze jsou smyšlené.</span>
  <button type="button" aria-label="Skrýt upozornění"
          onclick="this.closest('.demo-flag').remove()">&times;</button>
</aside>`;

html = html.replace('</body>', () => `${DEMO_NOTICE}\n</body>`);

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(OUT, html);

const kb = (n) => (n / 1024).toFixed(0);
console.log(`✓ ${path.relative(ROOT, OUT)}  ${kb(Buffer.byteLength(html))} kB`);
for (const leftover of html.match(/(?:src|href)="(?!data:|#|https?:|mailto:|tel:)[^"]+"/g) || []) {
  console.warn(`  ! unresolved reference: ${leftover}`);
}

/* ------------------------------------------------------------- artifact */
if (ARTIFACT) {
  let frag = html
    .replace(/^[\s\S]*?<body[^>]*>/i, '')       // drop doctype/html/head/body open
    .replace(/<\/body>[\s\S]*$/i, '')            // drop body close and after
    .trim();

  // <head>-only tags cannot travel into the body; the stylesheet can.
  const style = html.match(/<style>[\s\S]*?<\/style>/i);
  frag = (style ? style[0] + '\n' : '') + frag;

  // This site is deliberately light-themed with dark sections it opts into.
  // A host that stamps data-theme="dark" on <html> would otherwise repaint
  // the whole page with a palette the design was never checked against, so
  // the dark tokens are scoped to the sections that ask for them.
  frag = frag.replace(/\[data-theme='dark'\]\{/g, "[data-theme='dark']:not(:root){");

  // The host's shell may not carry a viewport meta, and without one mobile
  // browsers lay the page out at 980px.
  frag += `
<script>
(() => {
  if (!document.querySelector('meta[name="viewport"]')) {
    const m = document.createElement('meta');
    m.name = 'viewport';
    m.content = 'width=device-width, initial-scale=1, viewport-fit=cover';
    document.head.appendChild(m);
  }
  document.documentElement.lang = 'cs';
})();
</script>`;

  fs.writeFileSync(OUT_ARTIFACT, frag);
  console.log(`✓ ${path.relative(ROOT, OUT_ARTIFACT)}  ${kb(Buffer.byteLength(frag))} kB`);
}
