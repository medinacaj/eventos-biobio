// Render de la agenda: lista agrupada por fecha y tarjetas.
import { escapeHTML, fmtDate, fmtShort, fmtPrice, safeURL, state } from './state.js';
import { saveButton, bindSaveButtons } from './actions.js';
import { openDetails } from './details.js';

const RECENT_CHANGE_DAYS = 7;

export function badges(ev) {
  const b = [`<span class="badge cat-${escapeHTML(ev.category)}">${escapeHTML(ev.category)}</span>`];
  if (ev.official) b.push('<span class="badge oficial" title="Publicado por el organizador o institución oficial">Oficial</span>');
  if (ev.price_status === 'free') b.push('<span class="badge gratis">Gratis</span>');
  else if (ev.price_status === 'paid') b.push(`<span class="badge pago">${escapeHTML(fmtPrice(ev))}</span>`);
  else b.push('<span class="badge pendiente">Precio por confirmar</span>');
  if (ev.status === 'Cancelado') b.push('<span class="badge cancelado">Cancelado</span>');
  else if (ev.status !== 'Confirmado') b.push(`<span class="badge estado">${escapeHTML(ev.status)}</span>`);
  if (ev.is_new) b.push('<span class="badge nuevo">Nuevo</span>');
  if (ev.changed_at && (Date.now() - new Date(ev.changed_at)) / 864e5 < RECENT_CHANGE_DAYS) b.push('<span class="badge actualizado">Actualizado</span>');
  if (ev.origin === 'seed') b.push('<span class="badge semilla" title="Evento semilla verificado manualmente por búsqueda web, no rastreado automáticamente">Semilla</span>');
  return `<div class="badges">${b.join('')}</div>`;
}

function place(ev) {
  return [ev.venue, ev.commune].filter(Boolean).map(escapeHTML).join(' · ');
}

function timeLabel(ev) {
  if (!ev.time) return '<span class="ev-time">—<small>Hora por confirmar</small></span>';
  return `<span class="ev-time">${escapeHTML(ev.time)}${ev.end_time ? `<small>a ${escapeHTML(ev.end_time)}</small>` : ''}</span>`;
}

function row(ev) {
  return `<article class="ev-row ${ev.status === 'Cancelado' ? 'cancelled' : ''}" data-id="${ev.id}" tabindex="0">
    ${timeLabel(ev)}
    <div>
      <h3 class="ev-title">${escapeHTML(ev.title)}</h3>
      <div class="ev-meta">${place(ev)}${ev.end_date ? ` · hasta ${escapeHTML(fmtShort(ev.end_date))}` : ''}</div>
      ${badges(ev)}
    </div>
    ${saveButton(ev)}
  </article>`;
}

function card(ev) {
  const img = safeURL(ev.image_url);
  return `<article class="card ${ev.status === 'Cancelado' ? 'cancelled' : ''}" data-id="${ev.id}" tabindex="0">
    <div class="stripe ${escapeHTML(ev.category)}"></div>
    ${img ? `<img src="${escapeHTML(img)}" alt="Imagen publicada por la fuente" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
    <div class="card-body">
      <span class="card-date">${escapeHTML(fmtShort(ev.date))}${ev.time ? ' · ' + escapeHTML(ev.time) : ' · hora por confirmar'}</span>
      <h3 class="ev-title">${escapeHTML(ev.title)}</h3>
      <div class="ev-meta">${place(ev)}</div>
      ${badges(ev)}
      <div class="card-foot"><span class="muted" style="font-size:.8rem">${escapeHTML(ev.source || '')}</span>${saveButton(ev)}</div>
    </div>
  </article>`;
}

export function groupByDate(events) {
  const groups = new Map();
  events.forEach((ev) => {
    if (!groups.has(ev.date)) groups.set(ev.date, []);
    groups.get(ev.date).push(ev);
  });
  return groups;
}

export function renderEventList(root, events, mode = 'list', emptyMsg = 'No hay eventos con estos filtros.') {
  if (!events.length) {
    root.innerHTML = `<div class="empty">${escapeHTML(emptyMsg)}</div>`;
    return;
  }
  if (mode === 'cards') {
    root.innerHTML = `<div class="cards">${events.map(card).join('')}</div>`;
  } else {
    // Barras de fecha: todas abiertas por defecto, mismo tono fijo.
    root.innerHTML = [...groupByDate(events)].map(([d, evs]) => `
      <details class="date-group" open>
        <summary><span>${escapeHTML(fmtDate(d))}</span><span class="count">${evs.length} evento${evs.length === 1 ? '' : 's'}</span></summary>
        ${evs.map(row).join('')}
      </details>`).join('');
  }
  const byId = new Map(events.map((e) => [e.id, e]));
  bindSaveButtons(root, byId);
  root.querySelectorAll('[data-id]').forEach((el) => {
    const open = () => openDetails(Number(el.dataset.id));
    el.addEventListener('click', open);
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
  });
}

export function renderAgenda() {
  const root = document.getElementById('agenda');
  const n = state.events.length;
  document.getElementById('result-count').textContent = `${n} evento${n === 1 ? '' : 's'} con los filtros actuales`;
  renderEventList(root, state.events, state.agendaMode,
    'No hay eventos cargados con estos filtros. Prueba ampliar el rango de fechas o quitar filtros.');
}
