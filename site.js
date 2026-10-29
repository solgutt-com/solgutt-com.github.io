// Shared helpers for the site's pages. Reads `collections` from data.js.

const ROOT = '';

function byId(id) {
  return collections.find(c => c.id === id);
}

function childrenOf(id) {
  return collections
    .filter(c => c.parent === id)
    .sort((a, b) => (a.order || 999) - (b.order || 999));
}

// All photos inside a collection, walking down through sub-collections in order.
function photosUnder(id) {
  const c = byId(id);
  if (!c) return [];
  if (c.photos) return c.photos;
  return childrenOf(id).flatMap(child => photosUnder(child.id));
}

function photoSrc(p) {
  return ROOT + p.src.split('/').map(encodeURIComponent).join('/');
}

// Small preview made by make_thumbs.py; mirrors the photo's path under thumbs/.
function thumbSrc(p) {
  return 'thumbs/' + p.src.replace(/\.[^.]+$/, '.jpg').split('/').map(encodeURIComponent).join('/');
}

// <img> that shows the thumbnail, falling back to the full photo if it hasn't been made yet.
function thumbImg(p, attrs) {
  const img = h('img', { src: thumbSrc(p), alt: '', loading: 'lazy', decoding: 'async', ...attrs });
  img.addEventListener('error', () => { img.src = photoSrc(p); }, { once: true });
  return img;
}

// Up to `n` representative photos: the cover first, then one from each child,
// then spread evenly across everything else.
function previewPhotos(id, n) {
  const c = byId(id);
  const all = photosUnder(id);
  const picks = [];
  const add = p => { if (p && picks.length < n && !picks.includes(p)) picks.push(p); };
  if (c.cover) add(all.find(p => p.src.endsWith('/' + c.cover)));
  childrenOf(id).forEach(k => add(photosUnder(k.id)[0]));
  const step = Math.max(1, Math.floor(all.length / n));
  for (let i = 0; i < all.length && picks.length < n; i += step) add(all[i]);
  return picks;
}

function countLabel(c) {
  if (c.type === 'parent') {
    const k = childrenOf(c.id).filter(x => x.type !== 'coming-soon').length;
    return k + (k === 1 ? ' gallery' : ' galleries');
  }
  const n = (c.photos || []).length;
  if (n === 0) return 'No photographs yet';
  return n + (n === 1 ? ' photograph' : ' photographs');
}

function hrefFor(c) {
  return c.type === 'parent'
    ? 'sub-collection.html?id=' + encodeURIComponent(c.id)
    : 'gallery.html?code=' + encodeURIComponent(c.id);
}

// Ancestors from the top level down to (and including) the collection.
function trail(id) {
  const out = [];
  for (let c = byId(id); c; c = c.parent ? byId(c.parent) : null) out.unshift(c);
  return out;
}

function renderTrail(el, id) {
  el.append(h('a', { href: 'photography.html' }, 'Fotos'));
  const steps = trail(id);
  steps.forEach((c, i) => {
    el.append(h('span', { class: 'trail-sep', 'aria-hidden': 'true' }, '/'));
    el.append(i === steps.length - 1
      ? h('span', { 'aria-current': 'page' }, c.title)
      : h('a', { href: hrefFor(c) }, c.title));
  });
}

// Tiny element builder; strings become text nodes so data is never parsed as HTML.
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    el.setAttribute(k, v === true ? '' : v);
  }
  for (const child of children.flat()) {
    if (child == null || child === '') continue;
    el.append(child);
  }
  return el;
}
