// Barra de filtros: búsqueda, comuna, categoría, precio y rango de fechas.
import { state, escapeHTML, emit, todayISO } from './state.js';

let timer = null;

export function renderFilters(root) {
  const byProv = {};
  state.communes.forEach((c) => { (byProv[c.province] ||= []).push(c.name); });
  const communeOpts = Object.entries(byProv).map(([p, names]) =>
    `<optgroup label="Provincia de ${escapeHTML(p)}">${names.map((n) => `<option>${escapeHTML(n)}</option>`).join('')}</optgroup>`).join('');
  root.innerHTML = `
    <label class="f-q">Buscar<input id="f-q" type="search" placeholder="Título, lugar, comuna…" autocomplete="off"></label>
    <label>Comuna<select id="f-commune"><option value="">Todas (33)</option>${communeOpts}</select></label>
    <label>Categoría<select id="f-category"><option value="">Todas</option><option>Cultura</option><option>Comunidad</option><option>Empresarial</option></select></label>
    <label>Precio<select id="f-price"><option value="">Todos</option><option value="free">Gratis</option><option value="paid">Pagado</option><option value="pending">Por confirmar</option></select></label>
    <label>Desde<input id="f-from" type="date"></label>
    <label>Hasta<input id="f-to" type="date"></label>
    <button id="f-reset" class="btn ghost" type="button">Limpiar</button>`;
  syncInputs();
  const bind = (id, key, ev = 'change') => root.querySelector(id).addEventListener(ev, (e) => {
    state.filters[key] = e.target.value;
    if (ev === 'input') { clearTimeout(timer); timer = setTimeout(() => emit('filters'), 250); } else emit('filters');
  });
  bind('#f-q', 'q', 'input');
  bind('#f-commune', 'commune');
  bind('#f-category', 'category');
  bind('#f-price', 'price_status');
  bind('#f-from', 'date_from');
  bind('#f-to', 'date_to');
  root.querySelector('#f-reset').addEventListener('click', () => {
    state.filters = { q: '', commune: '', category: '', price_status: '', date_from: todayISO(), date_to: '' };
    syncInputs();
    emit('filters');
  });
}

export function syncInputs() {
  const f = state.filters;
  const set = (id, v) => { const el = document.querySelector(id); if (el) el.value = v || ''; };
  set('#f-q', f.q); set('#f-commune', f.commune); set('#f-category', f.category);
  set('#f-price', f.price_status); set('#f-from', f.date_from); set('#f-to', f.date_to);
}

export function setFilter(key, value) {
  state.filters[key] = value;
  syncInputs();
  emit('filters');
}

export function queryString(overrides = {}) {
  const f = { ...state.filters, ...overrides };
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => { if (v) p.set(k, v); });
  return p.toString();
}
