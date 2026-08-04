/**
 * HOPLA — booking data layer.
 *
 * Every part of the UI talks to `BookingClient` and never to a fetch call or a
 * JSON file directly. The client delegates to an adapter, and swapping the
 * adapter is the entire migration path to a real reservation backend:
 *
 *     // today — reads the committed JSON in /assets/data
 *     const api = createClient();
 *
 *     // tomorrow — same methods, same shapes, real server
 *     const api = createClient({ mode: 'http', baseUrl: '/api/v1' });
 *
 * The contract both adapters implement:
 *
 *     getAttractions()            → { categories, items }
 *     getAddons()                 → { groups }
 *     getDeliveryZones()          → { depot, zones }
 *     getAvailability(from, to)   → { '2026-08-14': 'free', … }
 *     quote(draft)                → { lines, total, currency }
 *     createReservation(draft)    → { id, status, receivedAt }
 *
 * Dates are always ISO `YYYY-MM-DD` strings in local time. Money is always
 * an integer in the minor-unit-free CZK the business actually invoices in.
 */

const DATA = 'assets/data';

/* -------------------------------------------------------------------------
   Date helpers — deliberately timezone-naive. A booking on 14 August is the
   14th of August regardless of where the browser thinks it is.
   ---------------------------------------------------------------------- */
export const toISO = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export const fromISO = (s) => {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
};

export const addDays = (d, n) => {
  const out = new Date(d);
  out.setDate(out.getDate() + n);
  return out;
};

const isWeekend = (d) => d.getDay() === 0 || d.getDay() === 6;

/** Deterministic 0…1 hash — the same date always yields the same load. */
function hash01(seed, str) {
  let h = seed >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h / 4294967296;
}

/* -------------------------------------------------------------------------
   Static adapter — the shipping default
   ---------------------------------------------------------------------- */
class StaticAdapter {
  #cache = new Map();

  async #json(name) {
    if (!this.#cache.has(name)) {
      this.#cache.set(
        name,
        fetch(`${DATA}/${name}.json`, { credentials: 'same-origin' }).then((r) => {
          if (!r.ok) throw new Error(`${name}.json → HTTP ${r.status}`);
          return r.json();
        })
      );
    }
    return this.#cache.get(name);
  }

  getAttractions() { return this.#json('attractions'); }
  getAddons() { return this.#json('addons'); }
  getDeliveryZones() { return this.#json('delivery-zones'); }

  /**
   * Derives a plausible occupancy from the rules in availability.json so the
   * calendar is populated whenever the page is opened, then lets explicit
   * overrides win. A real backend returns the same map from its bookings table.
   */
  async getAvailability(fromISODate, toISODate) {
    const cfg = await this.#json('availability');
    const { rules, overrides } = cfg;
    const out = {};

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const earliest = addDays(today, rules.leadTimeDays);
    const horizon = addDays(today, rules.horizonDays);

    let cur = fromISO(fromISODate);
    const end = fromISO(toISODate);

    while (cur <= end) {
      const iso = toISO(cur);

      if (overrides[iso]) {
        out[iso] = overrides[iso];
      } else if (cur < earliest || cur > horizon) {
        out[iso] = 'off';
      } else if (rules.closedWeekdays.includes(cur.getDay())) {
        out[iso] = 'closed';
      } else {
        const high = rules.seasonHighMonths.includes(cur.getMonth() + 1);
        let load = isWeekend(cur) ? rules.weekendLoad : rules.weekdayLoad;
        if (!high) load *= 0.45;
        const roll = hash01(rules.seed, iso);
        out[iso] = roll < load ? 'full' : roll < load + 0.18 ? 'limited' : 'free';
      }
      cur = addDays(cur, 1);
    }
    return out;
  }

  /** No server to talk to, so the draft is persisted locally and echoed back. */
  async createReservation(draft) {
    const id = `HOP-${Date.now().toString(36).toUpperCase()}`;
    const record = { id, status: 'pending', receivedAt: new Date().toISOString(), draft };
    try {
      const key = 'hopla:reservations';
      const all = JSON.parse(localStorage.getItem(key) || '[]');
      all.push(record);
      localStorage.setItem(key, JSON.stringify(all.slice(-20)));
    } catch {
      /* private browsing — the reservation still returns, it just is not kept */
    }
    return record;
  }
}

/* -------------------------------------------------------------------------
   HTTP adapter — ready for the reservation service
   ---------------------------------------------------------------------- */
class HttpAdapter {
  constructor({ baseUrl = '/api/v1', headers = {} } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.headers = { Accept: 'application/json', ...headers };
  }

  async #req(path, init = {}) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      credentials: 'same-origin',
      ...init,
      headers: { ...this.headers, ...(init.headers || {}) },
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      throw new Error(`${init.method || 'GET'} ${path} → ${res.status} ${detail}`.trim());
    }
    return res.status === 204 ? null : res.json();
  }

  getAttractions() { return this.#req('/attractions'); }
  getAddons() { return this.#req('/addons'); }
  getDeliveryZones() { return this.#req('/delivery-zones'); }
  getAvailability(from, to) {
    return this.#req(`/availability?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
  }
  createReservation(draft) {
    return this.#req('/reservations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft),
    });
  }
}

/* -------------------------------------------------------------------------
   Client
   ---------------------------------------------------------------------- */
export class BookingClient {
  constructor(adapter) { this.adapter = adapter; }

  getAttractions() { return this.adapter.getAttractions(); }
  getAddons() { return this.adapter.getAddons(); }
  getDeliveryZones() { return this.adapter.getDeliveryZones(); }
  getAvailability(from, to) { return this.adapter.getAvailability(from, to); }

  /** Finds the delivery zone whose town list contains `town`, ignoring diacritics. */
  async resolveZone(town) {
    if (!town) return null;
    const { zones } = await this.getDeliveryZones();
    const norm = (s) =>
      s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim();
    const q = norm(town);
    if (!q) return null;
    return (
      zones.find((z) => z.towns.some((t) => norm(t) === q)) ||
      zones.find((z) => z.towns.some((t) => norm(t).startsWith(q) || q.startsWith(norm(t)))) ||
      null
    );
  }

  /**
   * Prices a draft. Kept on the client so the total updates as the user picks,
   * but the shape matches what the server will return so the UI never changes.
   */
  async quote(draft) {
    const [{ items }, { groups }] = await Promise.all([
      this.getAttractions(),
      this.getAddons(),
    ]);
    const addonIndex = new Map(groups.flatMap((g) => g.items.map((i) => [i.id, i])));

    const weekend = draft.date ? isWeekend(fromISO(draft.date)) : false;
    const lines = [];

    for (const id of draft.attractions || []) {
      const a = items.find((i) => i.id === id);
      if (!a) continue;
      const price = weekend ? a.priceWeekend : a.price;
      lines.push({ kind: 'attraction', id, label: a.name, amount: price });
    }

    for (const id of draft.addons || []) {
      const x = addonIndex.get(id);
      if (!x) continue;
      lines.push({ kind: 'addon', id, label: x.name, amount: x.price });
    }

    const zone = await this.resolveZone(draft.town);
    if (zone) {
      lines.push({
        kind: 'delivery',
        id: zone.id,
        label: `Doprava — ${zone.label}`,
        amount: zone.fee,           // null means "quoted individually"
        note: zone.feeLabel,
      });
    }

    const total = lines.reduce((sum, l) => sum + (l.amount || 0), 0);
    const openEnded = lines.some((l) => l.amount === null);

    return { lines, total, openEnded, weekend, currency: 'CZK' };
  }

  createReservation(draft) { return this.adapter.createReservation(draft); }
}

/**
 * Picks the adapter. `mode` is the only thing that has to change when the
 * reservation service goes live.
 */
export function createClient({ mode = 'static', ...opts } = {}) {
  return new BookingClient(mode === 'http' ? new HttpAdapter(opts) : new StaticAdapter());
}

/* ---------------------------------------------------------------- format -- */
const czk = new Intl.NumberFormat('cs-CZ', {
  style: 'currency', currency: 'CZK', maximumFractionDigits: 0,
});
export const formatPrice = (n) => (n == null ? 'dle domluvy' : czk.format(n));

const longDate = new Intl.DateTimeFormat('cs-CZ', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
});
export const formatDate = (iso) => longDate.format(fromISO(iso));

const shortDate = new Intl.DateTimeFormat('cs-CZ', { day: 'numeric', month: 'long' });
export const formatDateShort = (iso) => shortDate.format(fromISO(iso));
