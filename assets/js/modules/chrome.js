/** Page chrome: sticky header, mobile navigation, scroll-spy, mobile dock. */
import { $, $$, raf } from '../lib/dom.js';

export function initHeader() {
  const header = $('[data-header]');
  if (!header) return;

  const onScroll = raf(() => {
    header.classList.toggle('is-stuck', window.scrollY > 24);
  });
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
}

export function initNav() {
  const toggle = $('[data-nav-toggle]');
  const nav = $('#nav');
  if (!toggle || !nav) return;

  const label = toggle.querySelector('.visually-hidden');
  const use = toggle.querySelector('use');

  const setOpen = (open) => {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    if (use) use.setAttribute('href', open ? '#i-close' : '#i-menu');
    if (label) label.textContent = open ? 'Zavřít menu' : 'Otevřít menu';
  };

  toggle.addEventListener('click', () =>
    setOpen(toggle.getAttribute('aria-expanded') !== 'true')
  );

  // Any in-page jump closes the panel; so does Escape and a click outside it.
  nav.addEventListener('click', (e) => {
    if (e.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('is-open')) {
      setOpen(false);
      toggle.focus();
    }
  });
  document.addEventListener('click', (e) => {
    if (!nav.classList.contains('is-open')) return;
    if (!nav.contains(e.target) && !toggle.contains(e.target)) setOpen(false);
  });
}

/** Marks the nav link whose section currently owns the viewport. */
export function initScrollSpy() {
  const links = $$('#nav a[href^="#"]');
  if (!links.length || !('IntersectionObserver' in window)) return;

  const byId = new Map();
  for (const link of links) {
    const section = document.getElementById(link.getAttribute('href').slice(1));
    if (section) byId.set(section, link);
  }
  if (!byId.size) return;

  const visible = new Set();
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) visible.add(entry.target);
        else visible.delete(entry.target);
      }
      // The topmost visible section wins, so the marker never flickers
      // between two sections that overlap the reading band.
      const current = [...visible].sort((a, b) => a.offsetTop - b.offsetTop)[0];
      for (const [section, link] of byId) {
        if (section === current) link.setAttribute('aria-current', 'true');
        else link.removeAttribute('aria-current');
      }
    },
    { rootMargin: '-45% 0px -50% 0px' }
  );
  for (const section of byId.keys()) observer.observe(section);
}

/** The mobile action bar appears once the hero has scrolled away. */
export function initDock() {
  const dock = $('[data-dock]');
  const hero = $('#hero');
  const booking = $('#rezervace');
  if (!dock || !hero) return;

  let pastHero = false;
  let inBooking = false;

  const apply = () => {
    const show = pastHero && !inBooking;
    dock.classList.toggle('is-visible', show);
    dock.setAttribute('aria-hidden', String(!show));
  };

  new IntersectionObserver(
    ([e]) => { pastHero = !e.isIntersecting; apply(); },
    { rootMargin: '-70% 0px 0px 0px' }
  ).observe(hero);

  // Hiding it over the form keeps the sticky CTA from covering the submit button.
  if (booking) {
    new IntersectionObserver(
      ([e]) => { inBooking = e.isIntersecting; apply(); },
      { threshold: 0.12 }
    ).observe(booking);
  }
}

export function initYear() {
  const node = $('[data-year]');
  if (node) node.textContent = String(new Date().getFullYear());
}
