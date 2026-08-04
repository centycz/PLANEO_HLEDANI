/**
 * Delivery map: hovering a zone row lights the matching ring, and the lookup
 * box answers "do you come to my town, and what does it cost?".
 */
import { $, $$ } from '../lib/dom.js';
import { formatPrice } from '../lib/api.js';

export function initDeliveryMap() {
  const rows = $$('[data-zone-row]');
  const rings = $$('[data-zone]');
  if (!rows.length || !rings.length) return;

  const highlight = (id) => {
    for (const ring of rings) ring.classList.toggle('is-active', ring.dataset.zone === id);
    for (const row of rows) row.classList.toggle('is-active', row.dataset.zoneRow === id);
  };

  for (const row of rows) {
    row.addEventListener('pointerenter', () => highlight(row.dataset.zoneRow));
    row.addEventListener('pointerleave', () => highlight(null));
  }
}

export function initZoneCheck(api) {
  const form = $('[data-zone-check]');
  if (!form) return;

  const input = $('input[name="town"]', form);
  const result = $('[data-zone-result]', form);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const town = input.value.trim();

    if (!town) {
      result.textContent = 'Napište prosím název města nebo obce.';
      result.removeAttribute('data-tone');
      return;
    }

    result.textContent = 'Hledám…';
    result.removeAttribute('data-tone');

    let zone = null;
    try {
      zone = await api.resolveZone(town);
    } catch {
      result.textContent = 'Ověření se nepodařilo. Zavolejte nám na 730 111 222.';
      return;
    }

    if (!zone) {
      result.innerHTML =
        'Tohle město nemáme v seznamu — ale skoro jistě k vám dojedeme. ' +
        'Napište nám a cenu dopravy potvrdíme obratem.';
      return;
    }

    const price = zone.fee === 0 ? 'doprava zdarma'
      : zone.fee == null ? 'cenu dopravy dohodneme individuálně'
      : `doprava ${formatPrice(zone.fee)}`;

    result.innerHTML = `Ano, jezdíme. <strong>${zone.label}</strong> — ${price}.`;
    result.dataset.tone = zone.fee === 0 ? 'ok' : '';

    // Light up the matching ring so the answer lands on the map too.
    for (const ring of $$('[data-zone]')) ring.classList.toggle('is-active', ring.dataset.zone === zone.id);
    for (const row of $$('[data-zone-row]')) row.classList.toggle('is-active', row.dataset.zoneRow === zone.id);
  });
}
