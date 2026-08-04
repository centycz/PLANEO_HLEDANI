/**
 * Three-step reservation form.
 *
 * Options come from the catalogue via `BookingClient`, pricing comes from
 * `api.quote()`, and submission goes through `api.createReservation()` — so
 * the day a real reservation service exists, nothing in this file changes.
 */
import { $, $$, el, icon, toast, debounce } from '../lib/dom.js';
import { formatPrice, formatDate, toISO, addDays } from '../lib/api.js';

/** Czech writes decimals with a comma, and drops a trailing ",0". */
const metres = (n) => new Intl.NumberFormat('cs-CZ', { maximumFractionDigits: 1 }).format(n);

const REQUIRED_MESSAGE = {
  date: 'Vyberte prosím datum akce.',
  town: 'Napište prosím město nebo obec.',
  name: 'Napište prosím své jméno.',
  phone: 'Napište prosím telefon, ať se vám můžeme ozvat.',
  email: 'Napište prosím e-mail pro potvrzení.',
  consent: 'Bez souhlasu bohužel nemůžeme poptávku zpracovat.',
};

export function initBooking(api) {
  const form = $('[data-booking]');
  if (!form) return null;

  const draft = { attractions: [], addons: [], date: '', town: '' };

  const steps = $$('[data-step]', form);
  const dots = $$('[data-step-dot]', form);
  const totalNode = $('[data-booking-total]', form);
  const summaryNode = $('[data-booking-summary]', form);
  const doneNode = $('[data-booking-done]', form);
  const progress = $('[data-booking-progress]', form);
  const dateInput = $('[data-booking-date]', form);
  const townInput = $('#b-town', form);
  const zoneHint = $('[data-booking-zone]', form);

  /* ------------------------------------------------------------- stepping */
  let current = 1;

  const showStep = (n, { focus = true } = {}) => {
    current = n;
    for (const step of steps) step.classList.toggle('is-active', Number(step.dataset.step) === n);
    for (const dot of dots) {
      const i = Number(dot.dataset.stepDot);
      dot.classList.toggle('is-current', i === n);
      dot.classList.toggle('is-done', i < n);
    }
    if (focus) {
      const first = $('.booking__step.is-active', form)?.querySelector('input, select, textarea, button');
      first?.focus({ preventScroll: true });
    }
  };

  /* -------------------------------------------------------------- options */
  async function renderOptions() {
    const attractionsHost = $('[data-booking-attractions]', form);
    const addonsHost = $('[data-booking-addons]', form);

    let catalogue, addons;
    try {
      [catalogue, addons] = await Promise.all([api.getAttractions(), api.getAddons()]);
    } catch {
      attractionsHost.replaceChildren(
        el('p', { class: 'field__hint', text:
          'Nabídku se teď nepodařilo načíst. Zavolejte nám na 730 111 222 a vyřešíme to hned.' })
      );
      addonsHost.replaceChildren();
      return;
    }

    attractionsHost.replaceChildren(
      ...catalogue.items.map((a) =>
        el('label', { class: 'option-card' },
          el('input', {
            type: 'checkbox', name: 'attraction', value: a.id,
            onChange: (e) => {
              toggle(draft.attractions, a.id, e.target.checked);
              refresh();
            },
          }),
          el('span', { class: 'option-card__figure' }, icon(iconFor(a.category), 'icon icon--lg')),
          el('span', { class: 'option-card__main' },
            el('span', { class: 'option-card__name', text: a.name }),
            el('span', { class: 'option-card__meta',
              text: `${metres(a.size.w)} × ${metres(a.size.d)} m · ${a.ages[0]}–${a.ages[1]} let` })
          ),
          el('span', { class: 'option-card__price', text: formatPrice(a.price) }),
          el('span', { class: 'option-card__check' }, icon('i-check'))
        )
      )
    );

    const allAddons = addons.groups.flatMap((g) => g.items);
    addonsHost.replaceChildren(
      ...allAddons.map((x) =>
        el('label', { class: 'option-card' },
          el('input', {
            type: 'checkbox', name: 'addon', value: x.id,
            onChange: (e) => {
              toggle(draft.addons, x.id, e.target.checked);
              refresh();
            },
          }),
          el('span', { class: 'option-card__figure' }, icon(x.icon, 'icon icon--lg')),
          el('span', { class: 'option-card__main' },
            el('span', { class: 'option-card__name', text: x.name }),
            el('span', { class: 'option-card__meta', text: x.note || '' })
          ),
          el('span', { class: 'option-card__price', text: formatPrice(x.price) }),
          el('span', { class: 'option-card__check' }, icon('i-check'))
        )
      )
    );
  }

  const iconFor = (category) => ({
    hrady: 'i-castle', skluzavky: 'i-slide', sport: 'i-obstacle',
    mini: 'i-ballpit', svatby: 'i-rings',
  }[category] || 'i-arch');

  const toggle = (list, value, on) => {
    const i = list.indexOf(value);
    if (on && i === -1) list.push(value);
    if (!on && i !== -1) list.splice(i, 1);
  };

  /* --------------------------------------------------------------- prices */
  async function refresh() {
    let quote;
    try {
      quote = await api.quote(draft);
    } catch {
      return;
    }

    if (!quote.lines.length) {
      totalNode.textContent = 'Zatím nic nevybráno';
    } else {
      totalNode.replaceChildren(
        document.createTextNode(quote.openEnded ? `od ${formatPrice(quote.total)}` : formatPrice(quote.total)),
        el('small', { text: quote.weekend ? 'víkendová sazba · orientační cena' : 'orientační cena' })
      );
    }

    summaryNode.replaceChildren(
      quote.lines.length
        ? el('dl', {},
            ...quote.lines.flatMap((line) => [
              el('dt', { text: line.label }),
              el('dd', { text: line.amount == null ? line.note : formatPrice(line.amount) }),
            ]),
            el('dt', { class: 'is-total', text: 'Celkem' }),
            el('dd', { class: 'is-total', text: quote.openEnded ? `od ${formatPrice(quote.total)}` : formatPrice(quote.total) })
          )
        : el('p', { class: 'field__hint', text: 'Vyberte atrakci v prvním kroku a cena se dopočítá.' })
    );
  }

  /* ----------------------------------------------------------- validation */
  const setError = (name, message) => {
    const slot = $(`[data-error-for="${name}"]`, form);
    const field = form.elements[name];
    if (slot) slot.textContent = message || '';
    if (field && field.setAttribute) {
      if (message) field.setAttribute('aria-invalid', 'true');
      else field.removeAttribute('aria-invalid');
    }
  };

  const validate = (names) => {
    let ok = true;
    let firstBad = null;

    for (const name of names) {
      const field = form.elements[name];
      if (!field) continue;
      const value = field.type === 'checkbox' ? field.checked : field.value.trim();
      let message = '';

      if (!value) message = REQUIRED_MESSAGE[name];
      else if (name === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value))
        message = 'Zkontrolujte prosím tvar e-mailu.';
      else if (name === 'phone' && value.replace(/\D/g, '').length < 9)
        message = 'Telefon vypadá na příliš krátký.';
      else if (name === 'date') {
        const earliest = toISO(addDays(new Date(), 2));
        if (value < earliest) message = `Nejbližší možný termín je ${formatDate(earliest)}.`;
      }

      setError(name, message);
      if (message) { ok = false; firstBad ??= field; }
    }

    firstBad?.focus();
    return ok;
  };

  /* ------------------------------------------------------------- wiring */
  for (const button of $$('[data-step-next]', form)) {
    button.addEventListener('click', () => {
      const target = Number(button.dataset.stepNext);
      if (current === 1 && !draft.attractions.length) {
        toast('Vyberte prosím alespoň jednu atrakci.', 'err');
        return;
      }
      if (current === 2 && !validate(['date', 'town'])) return;
      showStep(target);
    });
  }
  for (const button of $$('[data-step-prev]', form)) {
    button.addEventListener('click', () => showStep(Number(button.dataset.stepPrev)));
  }

  dateInput.min = toISO(addDays(new Date(), 2));
  dateInput.addEventListener('change', () => {
    draft.date = dateInput.value;
    setError('date', '');
    refresh();
  });

  townInput.addEventListener('input', debounce(async () => {
    draft.town = townInput.value.trim();
    setError('town', '');
    if (!draft.town) { zoneHint.textContent = ''; refresh(); return; }
    try {
      const zone = await api.resolveZone(draft.town);
      zoneHint.textContent = zone
        ? `${zone.label} — doprava ${zone.fee === 0 ? 'zdarma' : zone.fee == null ? 'dle domluvy' : formatPrice(zone.fee)}`
        : 'Toto město nemáme v seznamu — cenu dopravy potvrdíme e-mailem.';
    } catch {
      zoneHint.textContent = '';
    }
    refresh();
  }, 320));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validate(['name', 'phone', 'email', 'consent'])) return;

    const submit = $('[data-booking-submit]', form);
    submit.disabled = true;
    submit.textContent = 'Odesílám…';

    const payload = {
      ...draft,
      from: form.elements.from?.value,
      to: form.elements.to?.value,
      surface: form.elements.surface?.value,
      kids: form.elements.kids?.value ? Number(form.elements.kids.value) : null,
      power: form.elements.power?.checked ?? null,
      name: form.elements.name.value.trim(),
      phone: form.elements.phone.value.trim(),
      email: form.elements.email.value.trim(),
      note: form.elements.note?.value.trim() || '',
    };

    try {
      const reservation = await api.createReservation(payload);
      for (const step of steps) step.classList.remove('is-active');
      progress.hidden = true;
      doneNode.hidden = false;
      const text = $('[data-booking-done-text]', doneNode);
      if (text) {
        text.textContent =
          `Poptávku vedeme pod číslem ${reservation.id}. Shrnutí posíláme na ${payload.email}. ` +
          'Pokud by cokoli nesedělo, stačí odpovědět na zprávu nebo zavolat.';
      }
      doneNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
      toast('Rezervace odeslána. Ozveme se do dvou hodin.');
    } catch {
      submit.disabled = false;
      submit.textContent = 'Odeslat nezávaznou rezervaci';
      toast('Odeslání se nepodařilo. Zkuste to prosím znovu nebo zavolejte.', 'err');
    }
  });

  renderOptions().then(refresh);

  /** Lets the catalogue and the calendar push their choices into the form. */
  return {
    pickAttraction(id) {
      const box = form.querySelector(`input[name="attraction"][value="${CSS.escape(id)}"]`);
      if (!box || box.checked) return;
      box.checked = true;
      toggle(draft.attractions, id, true);
      refresh();
      showStep(1, { focus: false });
    },
    pickDate(iso) {
      dateInput.value = iso;
      draft.date = iso;
      setError('date', '');
      refresh();
      toast(`Termín ${formatDate(iso)} přenesen do formuláře.`);
      document.getElementById('rezervace')?.scrollIntoView({ behavior: 'smooth' });
      showStep(2, { focus: false });
    },
  };
}
