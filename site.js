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

// Preview made by make_thumbs.py; mirrors the photo's path under thumbs/, or under
// thumbs-large/ for the sharper copies of photos shown large (Fotos squares, collection cards).
function thumbSrc(p, large) {
  return (large ? 'thumbs-large/' : 'thumbs/') + p.src.replace(/\.[^.]+$/, '.jpg').split('/').map(encodeURIComponent).join('/');
}

// <img> that shows the preview, stepping back to the small thumbnail and then the photo
// itself if one hasn't been made yet.
function thumbImg(p, attrs, large) {
  const img = h('img', { src: thumbSrc(p, large), alt: '', loading: 'lazy', decoding: 'async', ...attrs });
  const fallbacks = [...(large ? [thumbSrc(p)] : []), photoSrc(p)];
  img.addEventListener('error', () => { if (fallbacks.length) img.src = fallbacks.shift(); });
  return img;
}

// The photo that stands for a collection: its starred cover, otherwise the cover
// of its first sub-collection that has one, otherwise its first photo.
function coverPhoto(id) {
  const c = byId(id);
  if (c.cover) {
    const starred = photosUnder(id).find(p => p.src.endsWith('/' + c.cover));
    if (starred) return starred;
  }
  if (c.photos) return c.photos[0] || null;
  for (const k of childrenOf(id)) {
    const p = coverPhoto(k.id);
    if (p) return p;
  }
  return null;
}

// Up to `n` representative photos: any chosen in the editor first, then the collection's
// own cover, then the cover of each sub-collection in order, then spread evenly across the rest.
function previewPhotos(id, n) {
  const c = byId(id);
  const all = photosUnder(id);
  const picks = [];
  const add = p => { if (p && picks.length < n && !picks.includes(p)) picks.push(p); };
  (c.preview || []).forEach(src => add(all.find(p => p.src === src)));
  if (c.cover) add(coverPhoto(id));
  childrenOf(id).forEach(k => add(coverPhoto(k.id)));
  const step = Math.max(1, Math.floor(all.length / n));
  for (let i = 0; i < all.length && picks.length < n; i += step) add(all[i]);
  return picks;
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
