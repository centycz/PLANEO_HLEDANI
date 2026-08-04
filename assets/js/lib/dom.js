/** Small DOM helpers shared by the feature modules. */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Creates an element from a tag, props and children in one call. */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(node.style, v);
    else if (k.startsWith('on')) node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k in node && k !== 'list') node[k] = v;
    else node.setAttribute(k, v === true ? '' : v);
  }
  node.append(...children.flat().filter((c) => c != null && c !== false));
  return node;
}

/** `<svg class="icon"><use href="#id"></svg>` without the boilerplate. */
export function icon(id, cls = 'icon') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', cls);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#${id}`);
  svg.append(use);
  return svg;
}

export const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Trailing-edge throttle pinned to the frame clock — for pointer and scroll. */
export function raf(fn) {
  let ticking = false;
  let lastArgs;
  return (...args) => {
    lastArgs = args;
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      fn(...lastArgs);
    });
  };
}

export function debounce(fn, ms = 200) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

/** Keeps Tab focus inside `container` while it is open. */
export function trapFocus(container) {
  const SELECTOR =
    'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';
  const onKey = (e) => {
    if (e.key !== 'Tab') return;
    const items = $$(SELECTOR, container).filter((n) => n.offsetParent !== null);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };
  container.addEventListener('keydown', onKey);
  return () => container.removeEventListener('keydown', onKey);
}

/** Transient status message, bottom-centre. */
export function toast(message, tone = 'ok') {
  const host = $('[data-toasts]');
  if (!host) return;
  const node = el(
    'div',
    { class: `toast toast--${tone}`, role: 'status' },
    icon(tone === 'ok' ? 'i-check' : 'i-info'),
    el('span', { text: message })
  );
  host.append(node);
  setTimeout(() => {
    node.classList.add('is-leaving');
    node.addEventListener('animationend', () => node.remove(), { once: true });
  }, 4200);
}
