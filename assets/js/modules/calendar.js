/**
 * Availability calendar.
 *
 * Renders a month at a time from `BookingClient.getAvailability()` and, when a
 * bookable day is chosen, hands the date to the reservation form.
 */
import { $, $$, el } from '../lib/dom.js';
import { toISO, fromISO, addDays, formatDate } from '../lib/api.js';

const MONTHS = ['leden', 'únor', 'březen', 'duben', 'květen', 'červen',
  'červenec', 'srpen', 'září', 'říjen', 'listopad', 'prosinec'];

const TONE = { free: 'free', limited: 'limited', full: 'busy', closed: 'off', off: 'off' };
const LABEL = { free: 'volno', limited: 'poslední kusy', full: 'obsazeno', closed: 'nejezdíme', off: 'nelze rezervovat' };

export function initCalendar(api, { onPick } = {}) {
  const root = $('[data-calendar]');
  if (!root) return;

  const grid = $('[data-cal-grid]', root);
  const title = $('[data-cal-title]', root);
  const prev = $('[data-cal-prev]', root);
  const next = $('[data-cal-next]', root);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let cursor = new Date(today.getFullYear(), today.getMonth(), 1);
  let selected = null;
  const cache = new Map();

  const monthKey = (d) => `${d.getFullYear()}-${d.getMonth()}`;

  async function availabilityFor(monthStart) {
    const key = monthKey(monthStart);
    if (!cache.has(key)) {
      const last = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0);
      cache.set(key, api.getAvailability(toISO(monthStart), toISO(last)));
    }
    return cache.get(key);
  }

  async function render() {
    title.textContent = `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`;
    // Never let the user page back before the current month.
    prev.disabled = cursor.getFullYear() === today.getFullYear() && cursor.getMonth() === today.getMonth();

    let data;
    try {
      data = await availabilityFor(cursor);
    } catch {
      grid.replaceChildren(
        el('p', {
          class: 'calendar__error',
          style: { gridColumn: '1 / -1', color: 'var(--text-muted)', textAlign: 'center', padding: '2rem 0' },
          text: 'Kalendář se teď nepodařilo načíst. Zavolejte nám na 730 111 222 — termín ověříme hned.',
        })
      );
      return;
    }

    const cells = [];
    // Monday-first grid: JS getDay() is Sunday-first, so shift it.
    const lead = (new Date(cursor.getFullYear(), cursor.getMonth(), 1).getDay() + 6) % 7;
    for (let i = 0; i < lead; i++) cells.push(el('div', { class: 'day day--pad' }));

    const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(cursor.getFullYear(), cursor.getMonth(), d);
      const iso = toISO(date);
      const past = date < today;
      const status = past ? 'past' : (data[iso] || 'free');
      const tone = past ? 'past' : TONE[status] || 'off';
      const bookable = !past && (status === 'free' || status === 'limited');

      const classes = ['day', `day--${tone}`];
      if (iso === toISO(today)) classes.push('day--today');
      if (iso === selected) classes.push('is-selected');

      const aria = `${formatDate(iso)} — ${past ? 'v minulosti' : LABEL[status] || ''}`;

      cells.push(
        el(bookable ? 'button' : 'div', {
          class: classes.join(' '),
          type: bookable ? 'button' : undefined,
          'data-date': iso,
          'aria-label': aria,
          'aria-pressed': bookable ? String(iso === selected) : undefined,
          disabled: bookable ? undefined : true,
          title: aria,
        }, String(d))
      );
    }

    grid.replaceChildren(...cells);
  }

  grid.addEventListener('click', (e) => {
    const cell = e.target.closest('button.day');
    if (!cell) return;
    selected = cell.dataset.date;
    $$('.day', grid).forEach((n) => {
      const on = n.dataset.date === selected;
      n.classList.toggle('is-selected', on);
      if (n.tagName === 'BUTTON') n.setAttribute('aria-pressed', String(on));
    });
    onPick?.(selected);
  });

  prev.addEventListener('click', () => {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1);
    render();
  });
  next.addEventListener('click', () => {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
    render();
  });

  render();
}

/** The three soonest bookable days, shown in the hero and the contact panel. */
export async function initNextSlots(api) {
  const lists = $$('[data-next-slots]');
  if (!lists.length) return;

  const fallback = () =>
    lists.forEach((list) =>
      list.replaceChildren(el('li', { text: 'Nejbližší termíny ověříme telefonicky.' }))
    );

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let data;
  try {
    data = await api.getAvailability(toISO(today), toISO(addDays(today, 60)));
  } catch {
    fallback();
    return;
  }

  const free = Object.entries(data)
    .filter(([, status]) => status === 'free' || status === 'limited')
    .slice(0, 3);

  if (!free.length) {
    fallback();
    return;
  }

  // Each list gets its own nodes — a DOM node can only live in one place.
  for (const list of lists) {
    list.replaceChildren(
      ...free.map(([iso, status]) =>
        el('li', {},
          el('time', { dateTime: iso, text: formatDate(iso) }),
          el('span', { class: `badge badge--${status === 'free' ? 'ok' : 'warn'}` },
            status === 'free' ? 'Volno' : 'Poslední kusy')
        )
      )
    );
  }
}
