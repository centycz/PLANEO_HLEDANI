/**
 * Motion: scroll reveals, pointer parallax, card spotlight and counting stats.
 *
 * Every effect here is additive. With JavaScript disabled, reduced motion
 * requested, or an observer that never fires, the page still shows its final
 * state — nothing is hidden behind an animation that might not run.
 */
import { $$, raf, prefersReducedMotion } from '../lib/dom.js';

/* ------------------------------------------------------------------ reveal */
export function initReveal() {
  const targets = $$('[data-reveal]');
  if (!targets.length) return;

  if (!('IntersectionObserver' in window) || prefersReducedMotion()) {
    targets.forEach((n) => n.classList.add('is-revealed'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries, obs) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add('is-revealed');
        obs.unobserve(entry.target);
      }
    },
    { rootMargin: '0px 0px -12% 0px', threshold: 0.06 }
  );
  targets.forEach((n) => observer.observe(n));
}

/* ---------------------------------------------------------------- parallax */
/**
 * Mouse parallax. Layers declare `data-depth`; the pointer offset is scaled by
 * depth and written to custom properties, letting CSS own the easing.
 */
export function initParallax() {
  const roots = $$('[data-parallax-root]');
  if (!roots.length || prefersReducedMotion()) return;
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

  for (const root of roots) {
    const layers = $$('[data-parallax]', root);
    if (!layers.length) continue;

    const move = raf((clientX, clientY) => {
      const r = root.getBoundingClientRect();
      const nx = (clientX - r.left) / r.width - 0.5;   // −0.5 … 0.5
      const ny = (clientY - r.top) / r.height - 0.5;
      for (const layer of layers) {
        const depth = Number(layer.dataset.depth || 10);
        layer.style.setProperty('--px', `${(-nx * depth).toFixed(2)}px`);
        layer.style.setProperty('--py', `${(-ny * depth).toFixed(2)}px`);
      }
    });

    root.addEventListener('pointermove', (e) => move(e.clientX, e.clientY), { passive: true });
    root.addEventListener('pointerleave', () => {
      for (const layer of layers) {
        layer.style.setProperty('--px', '0px');
        layer.style.setProperty('--py', '0px');
      }
    });
  }
}

/* --------------------------------------------------------------- spotlight */
/** Pointer-tracked highlight on cards that opt in with `data-spotlight`. */
export function initSpotlight() {
  const cards = $$('[data-spotlight]');
  if (!cards.length || prefersReducedMotion()) return;
  if (!window.matchMedia('(hover: hover)').matches) return;

  for (const card of cards) {
    const move = raf((clientX, clientY) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${((clientX - r.left) / r.width) * 100}%`);
      card.style.setProperty('--my', `${((clientY - r.top) / r.height) * 100}%`);
    });
    card.addEventListener('pointermove', (e) => move(e.clientX, e.clientY), { passive: true });
  }
}

/* ---------------------------------------------------------------- counters */
/** Counts a stat up to its target the first time it scrolls into view. */
export function initCounters() {
  const nodes = $$('[data-count]');
  if (!nodes.length || !('IntersectionObserver' in window)) return;

  const nf = new Intl.NumberFormat('cs-CZ');

  const run = (node) => {
    const target = Number(node.dataset.count);
    const decimals = Number(node.dataset.decimal || 0);
    const suffix = node.dataset.suffix || '';
    if (!Number.isFinite(target)) return;

    if (prefersReducedMotion()) return;         // the markup already reads correctly

    const duration = 1100;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const value = target * eased;
      node.textContent = decimals
        ? (value / 10 ** decimals).toFixed(decimals).replace('.', ',') + suffix
        : nf.format(Math.round(value)) + suffix;
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  const observer = new IntersectionObserver(
    (entries, obs) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        run(entry.target);
        obs.unobserve(entry.target);
      }
    },
    { threshold: 0.6 }
  );
  nodes.forEach((n) => observer.observe(n));
}
