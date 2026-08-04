/**
 * HOPLA — end-to-end smoke test.
 *
 * Drives the page the way a visitor does: filter the catalogue, pick an
 * attraction, watch the price update, walk the three booking steps, submit,
 * then exercise the calendar, the delivery lookup and the lightbox.
 *
 *   node scripts/serve.js . 8877 &
 *   node tests/smoke.js
 *
 * Requires Playwright's Chromium. Exits non-zero if any check fails.
 */
const { chromium } = require('playwright');
const CHROME = process.env.CHROME_PATH || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const BASE = process.env.BASE_URL || 'http://localhost:8877';
const ok = [], bad = [];
const check = (name, cond, detail='') => (cond ? ok : bad).push(name + (detail ? ` — ${detail}` : ''));

(async () => {
  const b = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));
  p.on('console', m => m.type() === 'error' && errors.push(m.text()));
  await p.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });

  // 1. catalogue filter
  await p.click('.chip[data-filter="skluzavky"]');
  await p.waitForTimeout(250);
  const visible = await p.$$eval('.attraction:not([hidden])', n => n.map(x => x.dataset.id || 'cta'));
  check('filtr katalogu', visible.includes('aqua-rush') && visible.includes('tobogan-xxl') && !visible.includes('hrad-kralovsky'), visible.join(','));
  check('CTA karta přežije filtr', visible.includes('cta'));
  const label = await p.textContent('[data-catalog-count]');
  check('počítadlo výsledků', /2 atrakce/.test(label), label);
  await p.click('.chip[data-filter="all"]');

  // 2. booking options loaded from JSON
  const opts = await p.$$eval('[data-booking-attractions] input', n => n.length);
  const addons = await p.$$eval('[data-booking-addons] input', n => n.length);
  check('atrakce ve formuláři z JSON', opts === 10, `${opts}`);
  check('doplňky ve formuláři z JSON', addons === 10, `${addons}`);

  // 3. price quote
  // Real users click the label; the input itself is visually hidden.
  await p.click('[data-booking-attractions] label.option-card:has(input[value="hrad-kralovsky"])');
  await p.click('[data-booking-addons] label.option-card:has(input[value="popcorn"])');
  check('výběr přes label zaškrtne input',
    await p.isChecked('[data-booking-attractions] input[value="hrad-kralovsky"]'));
  await p.waitForTimeout(350);
  const total = await p.textContent('[data-booking-total]');
  check('výpočet ceny (2900+1200)', /4\s?100/.test(total.replace(/ /g,' ')), total.trim());

  // 4. step navigation + validation
  await p.click('[data-step-next="2"]');
  await p.waitForTimeout(200);
  check('krok 2 aktivní', await p.isVisible('[data-step="2"].is-active'));
  await p.click('[data-step-next="3"]');
  await p.waitForTimeout(200);
  const dateErr = await p.textContent('[data-error-for="date"]');
  check('validace blokuje prázdné datum', dateErr.trim().length > 0, dateErr.trim());

  // 5. zone lookup feeds the quote
  await p.fill('#b-date', '2026-09-19');
  await p.fill('#b-town', 'Vyškov');
  await p.waitForTimeout(700);
  const zone = await p.textContent('[data-booking-zone]');
  check('rozpoznání zóny z města', /Zóna 2/.test(zone), zone.trim());
  const total2 = await p.textContent('[data-booking-total]');
  check('víkendová sazba + doprava', /víkendová/.test(total2), total2.replace(/\s+/g,' ').trim());

  // 6. full submit
  await p.click('[data-step-next="3"]');
  await p.fill('#b-name', 'Petra Nováková');
  await p.fill('#b-phone', '730111222');
  await p.fill('#b-email', 'petra@example.cz');
  await p.click('label.check:has(input[name="consent"])');
  await p.click('[data-booking-submit]');
  await p.waitForTimeout(600);
  check('potvrzení rezervace', await p.isVisible('[data-booking-done]'));
  const done = await p.textContent('[data-booking-done-text]');
  check('číslo rezervace vygenerováno', /HOP-/.test(done), done.slice(0, 60));

  // 7. calendar
  await p.click('a[href="#terminy"]');
  await p.waitForTimeout(500);
  const days = await p.$$eval('.calendar__grid button.day', n => n.length);
  check('kalendář vykreslen', days > 20, `${days} klikatelných dní`);
  const statuses = await p.$$eval('.calendar__grid .day', n => [...new Set(n.map(x => x.className.match(/day--(\w+)/)?.[1]))]);
  check('kalendář má více stavů', statuses.filter(Boolean).length >= 3, statuses.join(','));

  // 8. zone checker
  await p.fill('#zone-town', 'Znojmo');
  await p.click('[data-zone-check] button[type="submit"]');
  await p.waitForTimeout(500);
  const res = await p.textContent('[data-zone-result]');
  check('ověřovač měst', /Zóna 3/.test(res), res.trim());

  // 9. lightbox
  await p.click('[data-lightbox="0"]');
  await p.waitForTimeout(400);
  check('lightbox otevřen', await p.isVisible('[data-lightbox-dialog][open]'));
  await p.keyboard.press('ArrowRight');
  await p.waitForTimeout(200);
  const cap = await p.textContent('[data-lightbox-caption]');
  check('lightbox listování', /2 \/ 6/.test(cap), cap);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(300);
  check('lightbox zavřen Escapem', !(await p.isVisible('[data-lightbox-dialog][open]')));

  // 10. hero availability card shares data with contact panel
  const heroSlots = await p.$$eval('.hero__slots li', n => n.length);
  const contactSlots = await p.$$eval('.contact__slots li', n => n.length);
  check('termíny v hero i v kontaktu', heroSlots === 3 && contactSlots === 3, `${heroSlots}/${contactSlots}`);

  check('žádné chyby v konzoli', errors.length === 0, errors.slice(0,3).join(' | '));

  console.log('\nPASS ' + ok.length);
  ok.forEach(x => console.log('  ✓ ' + x));
  if (bad.length) { console.log('\nFAIL ' + bad.length); bad.forEach(x => console.log('  ✗ ' + x)); }
  await b.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.error('CRASH', e.message); process.exit(1); });
