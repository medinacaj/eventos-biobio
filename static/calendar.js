// Calendario mensual con conteo de eventos por día.
import { api, state, escapeHTML, todayISO } from './state.js';
import { queryString } from './filters.js';
import { renderEventList } from './views.js';

const MONTH_FMT = new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' });
const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
let monthEvents = [];

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export function initCalendar() {
  const t = new Date();
  state.calMonth = new Date(t.getFullYear(), t.getMonth(), 1);
  document.getElementById('cal-prev').onclick = () => shift(-1);
  document.getElementById('cal-next').onclick = () => shift(1);
  document.getElementById('cal-today').onclick = () => {
    const n = new Date(); state.calMonth = new Date(n.getFullYear(), n.getMonth(), 1); state.calSelected = todayISO(); renderCalendar();
  };
}

function shift(n) {
  const m = state.calMonth;
  state.calMonth = new Date(m.getFullYear(), m.getMonth() + n, 1);
  state.calSelected = null;
  renderCalendar();
}

export async function renderCalendar() {
  const m = state.calMonth;
  const first = new Date(m.getFullYear(), m.getMonth(), 1);
  const last = new Date(m.getFullYear(), m.getMonth() + 1, 0);
  document.getElementById('cal-title').textContent = MONTH_FMT.format(first);
  // Rango del mes; respeta el resto de los filtros (comuna, categoría, precio, texto).
  const qs = queryString({ date_from: iso(first), date_to: iso(last) });
  try {
    monthEvents = (await api(`/api/events?${qs}`)).events;
  } catch (e) {
    document.getElementById('calendar').innerHTML = `<div class="empty">Error: ${escapeHTML(e.message)}</div>`;
    return;
  }
  const counts = {};
  monthEvents.forEach((ev) => {
    // Un evento de varios días cuenta en cada día dentro del mes.
    const s = ev.date < iso(first) ? new Date(first) : new Date(...ev.date.split('-').map((x, i) => Number(x) - (i === 1 ? 1 : 0)));
    const endIso = ev.end_date && ev.end_date > ev.date ? ev.end_date : ev.date;
    for (let d = s; iso(d) <= endIso && d <= last; d.setDate(d.getDate() + 1)) counts[iso(d)] = (counts[iso(d)] || 0) + 1;
  });
  const startOffset = (first.getDay() + 6) % 7;
  const cells = WEEKDAYS.map((w) => `<div class="cal-head">${w}</div>`);
  const gridStart = new Date(first); gridStart.setDate(1 - startOffset);
  const total = Math.ceil((startOffset + last.getDate()) / 7) * 7;
  const today = todayISO();
  for (let i = 0; i < total; i++) {
    const d = new Date(gridStart); d.setDate(gridStart.getDate() + i);
    const k = iso(d);
    const other = d.getMonth() !== m.getMonth();
    const n = other ? 0 : counts[k] || 0;
    cells.push(`<button class="cal-day ${other ? 'other' : ''} ${k === today ? 'today' : ''} ${k === state.calSelected ? 'selected' : ''}" data-day="${k}" ${other ? 'tabindex="-1"' : ''}
      aria-label="${k}: ${n} evento${n === 1 ? '' : 's'}"><span class="cal-num">${d.getDate()}</span>${n ? `<span class="cal-count">${n}</span>` : ''}</button>`);
  }
  const cal = document.getElementById('calendar');
  cal.innerHTML = cells.join('');
  cal.querySelectorAll('.cal-day:not(.other)').forEach((b) => b.addEventListener('click', () => {
    state.calSelected = b.dataset.day; renderCalendar();
  }));
  renderDay();
}

function renderDay() {
  const root = document.getElementById('calendar-day');
  const d = state.calSelected;
  if (!d) { root.innerHTML = '<p class="muted">Selecciona un día para ver sus eventos.</p>'; return; }
  const evs = monthEvents.filter((e) => e.date <= d && (e.end_date || e.date) >= d);
  renderEventList(root, evs, 'list', 'No hay eventos cargados para este día.');
}
