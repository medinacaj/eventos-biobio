// Estado global, API y favoritos (localStorage protegido con try/catch).
export const state = {
  view: 'agenda',
  agendaMode: 'list',
  filters: { q: '', commune: '', category: '', price_status: '', date_from: todayISO(), date_to: '' },
  events: [],
  communes: [],
  status: null,
  coverage: null,
  calMonth: null,
  calSelected: null,
};

export function todayISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* sin cuerpo */ }
  if (!res.ok) {
    const err = new Error((data && (data.error || (data.errors || []).join(' '))) || `HTTP ${res.status}`);
    err.data = data;
    err.status = res.status;
    throw err;
  }
  return data;
}

const FAV_KEY = 'eventos-biobio:guardados';
let favCache = null;

function readFavs() {
  if (favCache) return favCache;
  try {
    favCache = JSON.parse(localStorage.getItem(FAV_KEY) || '{}') || {};
  } catch (_) {
    favCache = {};
  }
  return favCache;
}

function writeFavs() {
  try { localStorage.setItem(FAV_KEY, JSON.stringify(favCache)); } catch (_) { /* modo privado */ }
}

export function isSaved(id) { return Boolean(readFavs()[id]); }

export function toggleSaved(ev) {
  const favs = readFavs();
  if (favs[ev.id]) delete favs[ev.id];
  else favs[ev.id] = { id: ev.id, title: ev.title, date: ev.date, saved_at: new Date().toISOString() };
  writeFavs();
  return Boolean(favs[ev.id]);
}

export function savedList() { return Object.values(readFavs()); }

const listeners = new Set();
export function onChange(fn) { listeners.add(fn); }
export function emit(what) { listeners.forEach((fn) => fn(what)); }

export function escapeHTML(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function safeURL(u) {
  return /^https?:\/\//i.test(u || '') ? u : null;
}

const DATE_FMT = new Intl.DateTimeFormat('es-CL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const SHORT_FMT = new Intl.DateTimeFormat('es-CL', { weekday: 'short', day: 'numeric', month: 'short' });

export function parseISO(d) {
  const [y, m, day] = d.split('-').map(Number);
  return new Date(y, m - 1, day);
}
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
export function fmtDate(d) { return cap(DATE_FMT.format(parseISO(d))); }
export function fmtShort(d) { return cap(SHORT_FMT.format(parseISO(d))); }

export function fmtPrice(ev) {
  if (ev.price_status === 'free') return 'Gratis';
  if (ev.price_status === 'paid') return ev.price_value != null ? `Desde $${Number(ev.price_value).toLocaleString('es-CL')}` : 'Pagado (monto por confirmar)';
  return 'Precio por confirmar';
}
