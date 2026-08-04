/**
 * HOPLA — service worker.
 *
 * Strategy per resource kind:
 *   documents      network-first  (content should never be stale)
 *   JSON data      network-first  (availability changes)
 *   static assets  cache-first    (fingerprint-free but content-stable)
 *   media          cache-first, capped, and never precached
 *
 * Bump CACHE_VERSION on deploy to retire the previous generation.
 */
const CACHE_VERSION = 'v1';
const SHELL = `hopla-shell-${CACHE_VERSION}`;
const ASSETS = `hopla-assets-${CACHE_VERSION}`;
const MEDIA = `hopla-media-${CACHE_VERSION}`;
const MEDIA_MAX_ENTRIES = 40;

/** The minimum needed to render something useful without a network. */
const PRECACHE = [
  './',
  'index.html',
  'offline.html',
  'assets/css/hopla.css',
  'assets/js/main.js',
  'assets/js/lib/api.js',
  'assets/js/lib/dom.js',
  'assets/fonts/outfit-var.woff2',
  'assets/fonts/inter-var.woff2',
  'assets/img/logo-mark.svg',
  'manifest.webmanifest',
].map((p) => new URL(p, self.registration.scope).pathname);

/** Path prefix the worker is installed under ('/' at a domain root). */
const BASE = new URL('./', self.registration.scope).pathname;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL)
      // addAll is all-or-nothing; a single 404 must not block activation.
      .then((cache) => Promise.allSettled(PRECACHE.map((url) => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  const keep = new Set([SHELL, ASSETS, MEDIA]);
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/** Keeps a cache from growing without bound, evicting oldest first. */
async function trim(cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length <= maxEntries) return;
  await Promise.all(keys.slice(0, keys.length - maxEntries).map((k) => cache.delete(k)));
}

async function networkFirst(request, cacheName, fallback) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (fallback) {
      const page = await caches.match(fallback);
      if (page) return page;
    }
    throw error;
  }
}

async function cacheFirst(request, cacheName, { max } = {}) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  // Opaque cross-origin responses would poison the cache with unknown sizes.
  if (response.ok && response.type === 'basic') {
    cache.put(request, response.clone());
    if (max) trim(cacheName, max);
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Range requests (video seeking) must reach the network untouched.
  if (request.headers.has('range')) return;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, SHELL, BASE + 'offline.html'));
    return;
  }

  if (url.pathname.startsWith(BASE + 'assets/data/')) {
    event.respondWith(networkFirst(request, ASSETS));
    return;
  }

  if (url.pathname.startsWith(BASE + 'assets/img/art/')) {
    event.respondWith(cacheFirst(request, MEDIA, { max: MEDIA_MAX_ENTRIES }));
    return;
  }

  if (['style', 'script', 'font', 'image'].includes(request.destination)) {
    event.respondWith(cacheFirst(request, ASSETS));
  }
});

self.addEventListener('message', (event) => {
  if (event.data === 'skip-waiting') self.skipWaiting();
});
