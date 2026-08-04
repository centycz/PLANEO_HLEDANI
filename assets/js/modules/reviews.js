/**
 * Review carousel.
 *
 * The track is a plain scroll-snap container, so it already works by swipe and
 * by keyboard before this module loads. This adds arrows, page dots and a
 * gentle auto-advance that stops the moment anyone interacts.
 */
import { $, $$, el, debounce, prefersReducedMotion } from '../lib/dom.js';

export function initReviews() {
  const root = $('[data-reviews]');
  if (!root) return;

  const track = $('[data-reviews-track]', root);
  const slides = $$('[data-review]', track);
  const dotsHost = $('[data-reviews-dots]', root);
  const prev = $('[data-reviews-prev]', root);
  const next = $('[data-reviews-next]', root);
  if (!track || slides.length < 2) return;

  /** How many cards fit at once — drives the number of pages. */
  const perPage = () => {
    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    const slideWidth = slides[0].getBoundingClientRect().width + gap;
    return Math.max(1, Math.round(track.clientWidth / slideWidth));
  };

  let pages = 1;
  let page = 0;
  let auto = null;

  const buildDots = () => {
    pages = Math.max(1, Math.ceil(slides.length / perPage()));
    dotsHost.replaceChildren(
      ...Array.from({ length: pages }, (_, i) =>
        el('button', {
          type: 'button',
          role: 'tab',
          'aria-selected': String(i === page),
          'aria-label': `Stránka ${i + 1} z ${pages}`,
          onClick: () => { stop(); go(i); },
        })
      )
    );
  };

  const syncDots = () => {
    $$('button', dotsHost).forEach((d, i) => d.setAttribute('aria-selected', String(i === page)));
    prev.disabled = page === 0;
    next.disabled = page === pages - 1;
  };

  const go = (target) => {
    page = Math.max(0, Math.min(pages - 1, target));
    const first = slides[page * perPage()];
    if (first) track.scrollTo({ left: first.offsetLeft - track.offsetLeft, behavior: 'smooth' });
    syncDots();
  };

  // Scrolling by hand — swipe, trackpad, keyboard — updates the dots.
  track.addEventListener('scroll', debounce(() => {
    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    const slideWidth = slides[0].getBoundingClientRect().width + gap;
    page = Math.round(track.scrollLeft / (slideWidth * perPage()));
    page = Math.max(0, Math.min(pages - 1, page));
    syncDots();
  }, 90), { passive: true });

  prev.addEventListener('click', () => { stop(); go(page - 1); });
  next.addEventListener('click', () => { stop(); go(page + 1); });

  const stop = () => { clearInterval(auto); auto = null; };
  const start = () => {
    if (auto || prefersReducedMotion() || pages < 2) return;
    auto = setInterval(() => go(page >= pages - 1 ? 0 : page + 1), 6500);
  };

  for (const event of ['pointerdown', 'focusin', 'pointerenter']) {
    root.addEventListener(event, stop, { passive: true });
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop();
  });

  window.addEventListener('resize', debounce(() => { buildDots(); syncDots(); }, 180));

  buildDots();
  syncDots();

  // Only auto-advance while the carousel is actually on screen.
  new IntersectionObserver(([e]) => (e.isIntersecting ? start() : stop()), { threshold: 0.35 })
    .observe(root);
}
