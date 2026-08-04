/**
 * Attraction catalogue: category filtering.
 *
 * The ten cards are in the HTML so they are indexable and paint with the
 * document; this only shows and hides them.
 */
import { $, $$ } from '../lib/dom.js';

const plural = (n) => (n === 1 ? 'atrakce' : n >= 2 && n <= 4 ? 'atrakce' : 'atrakcí');

export function initCatalog() {
  const grid = $('[data-catalog-grid]');
  if (!grid) return;

  const chips = $$('.catalog__bar .chip');
  const cards = $$('.attraction', grid);
  const count = $('[data-catalog-count]');
  const empty = $('[data-catalog-empty]');

  const apply = (filter) => {
    let shown = 0;
    for (const card of cards) {
      // `*` marks the closing call-to-action: it survives every filter and is
      // never part of the result count.
      const always = card.dataset.category === '*';
      const match = always || filter === 'all' || card.dataset.category === filter;
      card.hidden = !match;
      if (match && !always) shown++;
    }
    if (count) count.textContent = `Zobrazeno ${shown} ${plural(shown)}`;
    if (empty) empty.hidden = shown !== 0;
  };

  for (const chip of chips) {
    chip.addEventListener('click', () => {
      for (const other of chips) {
        const on = other === chip;
        other.classList.toggle('is-active', on);
        other.setAttribute('aria-pressed', String(on));
      }
      apply(chip.dataset.filter);
    });
  }

  apply('all');
}

/**
 * A click on an attraction card carries the choice into the booking form.
 * The link still points at #rezervace, so this only enriches the jump.
 */
export function initCatalogHandoff(onPick) {
  document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-pick]');
    if (!link) return;
    onPick?.(link.dataset.pick);
  });
}
