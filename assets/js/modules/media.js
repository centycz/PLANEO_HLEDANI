/** Gallery lightbox. */
import { $, $$, trapFocus } from '../lib/dom.js';

export function initLightbox() {
  const dialog = $('[data-lightbox-dialog]');
  const items = $$('[data-lightbox]');
  if (!dialog || !items.length) return;

  const img = $('[data-lightbox-img]', dialog);
  const caption = $('[data-lightbox-caption]', dialog);
  const btnPrev = $('[data-lightbox-prev]', dialog);
  const btnNext = $('[data-lightbox-next]', dialog);
  const btnClose = $('[data-lightbox-close]', dialog);

  // Prefer the largest source the thumbnail knows about.
  const slides = items.map((btn) => {
    const thumb = btn.querySelector('img');
    const largest = (thumb.getAttribute('srcset') || '')
      .split(',')
      .map((s) => s.trim().split(/\s+/)[0])
      .filter(Boolean)
      .pop();
    return { src: largest || thumb.currentSrc || thumb.src, alt: thumb.alt };
  });

  let index = 0;
  let release = null;

  const show = (i) => {
    index = (i + slides.length) % slides.length;
    const slide = slides[index];
    img.src = slide.src;
    img.alt = slide.alt;
    caption.textContent = `${slide.alt} · ${index + 1} / ${slides.length}`;
  };

  const open = (i) => {
    show(i);
    dialog.showModal();
    document.body.classList.add('no-scroll');
    release = trapFocus(dialog);
    btnClose.focus();
  };

  const close = () => {
    dialog.close();
  };

  items.forEach((btn, i) => btn.addEventListener('click', () => open(i)));
  btnPrev.addEventListener('click', () => show(index - 1));
  btnNext.addEventListener('click', () => show(index + 1));
  btnClose.addEventListener('click', close);

  dialog.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); show(index + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); show(index - 1); }
  });

  // Clicking the backdrop — anywhere that is not the figure — closes.
  dialog.addEventListener('click', (e) => {
    if (!e.target.closest('.lightbox__figure') && !e.target.closest('button')) close();
  });

  dialog.addEventListener('close', () => {
    document.body.classList.remove('no-scroll');
    release?.();
    release = null;
    img.removeAttribute('src');
    items[index]?.focus();
  });
}
