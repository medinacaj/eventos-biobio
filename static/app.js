// Punto de entrada: navegación entre vistas y carga de datos.
import { api, state, onChange, savedList, escapeHTML } from './state.js';
import { renderFilters, queryString } from './filters.js';
import { renderAgenda, renderEventList } from './views.js';
import { initCalendar, renderCalendar } from './calendar.js';
import { renderMap } from './map.js';
import { initDetails } from './details.js';
import { renderSubmissions } from './submissions.js';
import { renderAdmin } from './admin.js';

const FILTER_VIEWS = new Set(['agenda', 'calendar', 'map']);

async function loadEvents() {
  try {
    state.events = (await api(`/api/events?${queryString()}`)).events;
  } catch (e) {
    state.events = [];
    document.getElementById('agenda').innerHTML = `<div class="empty">No se pudo cargar la agenda: ${escapeHTML(e.message)}</div>`;
    return;
  }
  renderCurrent();
}

async function renderSaved() {
  const saved = savedList();
  const root = document.getElementById('saved');
  if (!saved.length) { root.innerHTML = '<div class="empty">Aún no guardas eventos. Usa ☆ en cualquier evento.</div>'; return; }
  // Trae todos los eventos (sin filtros de fecha) y cruza con los guardados.
  const all = (await api('/api/events')).events;
  const ids = new Set(saved.map((s) => s.id));
  const evs = all.filter((e) => ids.has(e.id));
  const missing = saved.filter((s) => !evs.some((e) => e.id === s.id));
  renderEventList(root, evs, 'list', 'Los eventos guardados ya no están en la base.');
  if (missing.length) root.insertAdjacentHTML('beforeend', `<p class="muted">${missing.length} evento(s) guardado(s) ya no existen en la base local.</p>`);
}

function updateSavedCount() { document.getElementById('saved-count').textContent = savedList().length; }

function renderCurrent() {
  const v = state.view;
  if (v === 'agenda') renderAgenda();
  else if (v === 'calendar') renderCalendar();
  else if (v === 'map') renderMap();
  else if (v === 'saved') renderSaved();
  else if (v === 'submit') renderSubmissions();
  else if (v === 'admin') renderAdmin();
}

function switchView(v) {
  state.view = v;
  document.querySelectorAll('.tab').forEach((t) => {
    const on = t.dataset.view === v;
    t.classList.toggle('active', on); t.setAttribute('aria-selected', on);
  });
  document.querySelectorAll('.view').forEach((s) => s.classList.toggle('active', s.id === `view-${v}`));
  document.getElementById('filters').classList.toggle('hidden', !FILTER_VIEWS.has(v));
  renderCurrent();
}

async function loadHonestyLine() {
  try {
    const s = await api('/api/status');
    document.getElementById('honesty-line').textContent =
      `${s.events_current} eventos vigentes (${s.events_seed} semilla, ${s.events_crawled} rastreados) · ` +
      `${s.communes_with_current_events}/${s.communes_total} comunas con eventos vigentes · ` +
      `${s.sources_verified_live} de ${s.sources_configured} fuentes verificadas en vivo.`;
  } catch (_) {
    document.getElementById('honesty-line').textContent = 'No se pudo leer el estado del servidor.';
  }
}

async function init() {
  initDetails();
  initCalendar();
  const { communes } = await api('/api/communes');
  state.communes = communes;
  renderFilters(document.getElementById('filters'));
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => switchView(t.dataset.view)));
  document.querySelectorAll('.seg').forEach((b) => b.addEventListener('click', () => {
    state.agendaMode = b.dataset.mode;
    document.querySelectorAll('.seg').forEach((x) => x.classList.toggle('active', x === b));
    renderAgenda();
  }));
  onChange((what) => {
    if (what === 'filters') loadEvents();
    if (what === 'saved') { updateSavedCount(); if (state.view === 'saved') renderSaved(); }
  });
  updateSavedCount();
  loadHonestyLine();
  await loadEvents();
}

init().catch((e) => {
  document.querySelector('main').insertAdjacentHTML('afterbegin', `<div class="notice err">Error al iniciar: ${escapeHTML(e.message)}</div>`);
});
