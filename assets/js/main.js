/**
 * HOPLA — entry point.
 *
 * Wires the feature modules together. Everything here is enhancement: the page
 * is complete, readable and navigable before this file runs, and any module
 * that throws is contained so it cannot take the rest of the page down.
 */
import { createClient } from './lib/api.js';
import { initHeader, initNav, initScrollSpy, initDock, initYear } from './modules/chrome.js';
import { initReveal, initParallax, initSpotlight, initCounters } from './modules/motion.js';
import { initCatalog, initCatalogHandoff } from './modules/catalog.js';
import { initCalendar, initNextSlots } from './modules/calendar.js';
import { initLightbox } from './modules/media.js';
import { initReviews } from './modules/reviews.js';
import { initDeliveryMap, initZoneCheck } from './modules/delivery.js';
import { initBooking } from './modules/booking.js';

/**
 * The one line that moves the site onto a real reservation backend:
 *
 *     createClient({ mode: 'http', baseUrl: '/api/v1' })
 */
const api = createClient();

/** Runs a module, reports a failure, and never lets it break its siblings. */
const safely = (name, fn) => {
  try {
    return fn();
  } catch (error) {
    console.error(`[hopla] module "${name}" failed`, error);
    return undefined;
  }
};

function start() {
  safely('header', initHeader);
  safely('nav', initNav);
  safely('scrollSpy', initScrollSpy);
  safely('dock', initDock);
  safely('year', initYear);

  safely('reveal', initReveal);
  safely('parallax', initParallax);
  safely('spotlight', initSpotlight);
  safely('counters', initCounters);

  safely('catalog', initCatalog);
  safely('lightbox', initLightbox);
  safely('reviews', initReviews);
  safely('deliveryMap', initDeliveryMap);

  // Data-driven modules — the booking form owns the handoff targets.
  const booking = safely('booking', () => initBooking(api));
  safely('calendar', () => initCalendar(api, { onPick: (iso) => booking?.pickDate(iso) }));
  safely('catalogHandoff', () => initCatalogHandoff((id) => booking?.pickAttraction(id)));
  safely('zoneCheck', () => initZoneCheck(api));
  safely('nextSlots', () => initNextSlots(api));
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start, { once: true });
} else {
  start();
}

/* ------------------------------------------------------------ service worker */
if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { scope: '/' })
      .catch((error) => console.warn('[hopla] service worker not registered', error));
  });
}
