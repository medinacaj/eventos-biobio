// Ficha rápida del evento (modal) con fuentes e historial de cambios.
import { api, escapeHTML, fmtDate, fmtPrice, safeURL, isSaved, toggleSaved, emit } from './state.js';
import { downloadICS, shareEvent } from './actions.js';
import { badges } from './views.js';

const FIELD_LABELS = { title: 'Título', date: 'Fecha', end_date: 'Fecha de término', time: 'Horario', venue: 'Lugar',
  price_value: 'Precio', price_status: 'Estado del precio', status: 'Estado' };

export async function openDetails(id) {
  const dlg = document.getElementById('details');
  dlg.innerHTML = '<div class="modal-body">Cargando…</div>';
  if (!dlg.open) dlg.showModal();
  let ev;
  try {
    ev = await api(`/api/events/${id}`);
  } catch (e) {
    dlg.innerHTML = `<div class="modal-body">No se pudo cargar el evento: ${escapeHTML(e.message)} <button class="btn ghost" data-close>Cerrar</button></div>`;
    dlg.querySelector('[data-close]').onclick = () => dlg.close();
    return;
  }
  const img = safeURL(ev.image_url);
  const src = safeURL(ev.source_url);
  const sources = (ev.sources || []).map((s) => {
    const u = safeURL(s.url);
    return `<li>${u ? `<a href="${escapeHTML(u)}" target="_blank" rel="noopener">${escapeHTML(s.name || u)}</a>` : escapeHTML(s.name || '')}</li>`;
  }).join('');
  const history = (ev.changes || []).map((c) => `<li><b>${escapeHTML(FIELD_LABELS[c.field] || c.field)}</b>:
      ${escapeHTML(c.old_value ?? '—')} → ${escapeHTML(c.new_value ?? '—')}
      <div class="muted">${escapeHTML((c.changed_at || '').replace('T', ' '))} · ${escapeHTML(c.source || '')}</div></li>`).join('');
  dlg.innerHTML = `
    <div class="modal-head">
      <div><h2 id="details-title">${escapeHTML(ev.title)}</h2>${badges(ev)}</div>
      <button class="close-x" data-close aria-label="Cerrar">✕</button>
    </div>
    <div class="modal-body">
      ${img ? `<img src="${escapeHTML(img)}" alt="Imagen publicada por la fuente" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      <dl class="facts">
        <dt>Fecha</dt><dd>${escapeHTML(fmtDate(ev.date))}${ev.end_date ? ' al ' + escapeHTML(fmtDate(ev.end_date)) : ''}</dd>
        <dt>Horario</dt><dd>${ev.time ? escapeHTML(ev.time) + (ev.end_time ? ' a ' + escapeHTML(ev.end_time) : '') : 'Por confirmar'}</dd>
        <dt>Lugar</dt><dd>${escapeHTML(ev.venue || 'Por confirmar')}${ev.address ? '<br><span class="muted">' + escapeHTML(ev.address) + '</span>' : ''}</dd>
        <dt>Comuna</dt><dd>${escapeHTML(ev.commune)} <span class="muted">(Provincia de ${escapeHTML(ev.province || '')})</span></dd>
        <dt>Precio</dt><dd>${escapeHTML(fmtPrice(ev))}</dd>
        ${ev.access ? `<dt>Acceso</dt><dd>${escapeHTML(ev.access)}</dd>` : ''}
        ${ev.audience ? `<dt>Público</dt><dd>${escapeHTML(ev.audience)}</dd>` : ''}
        <dt>Estado</dt><dd>${escapeHTML(ev.status)}</dd>
        <dt>Origen</dt><dd>${ev.origin === 'seed' ? 'Semilla verificada manualmente (búsqueda web)' : ev.origin === 'crawl' ? 'Rastreo automático' : escapeHTML(ev.origin || '')}</dd>
      </dl>
      ${ev.description ? `<p>${escapeHTML(ev.description)}</p>` : ''}
      <h3>Fuentes</h3>
      <ul>${sources || '<li class="muted">Sin fuentes registradas</li>'}</ul>
      <h3>Historial de cambios</h3>
      ${history ? `<ul class="history">${history}</ul>` : '<p class="muted">Sin cambios registrados desde que se descubrió.</p>'}
      <div class="modal-actions">
        <button class="btn" data-save>${isSaved(ev.id) ? '★ Guardado' : '☆ Guardar'}</button>
        <button class="btn ghost" data-ics>Añadir a mi calendario (.ics)</button>
        <button class="btn ghost" data-share>Compartir</button>
        ${src ? `<a class="btn ghost" href="${escapeHTML(src)}" target="_blank" rel="noopener">Ver en la fuente</a>` : ''}
      </div>
      <p class="muted" id="details-msg" aria-live="polite"></p>
    </div>`;
  dlg.querySelectorAll('[data-close]').forEach((b) => { b.onclick = () => dlg.close(); });
  dlg.querySelector('[data-save]').onclick = (e) => {
    const on = toggleSaved(ev);
    e.target.textContent = on ? '★ Guardado' : '☆ Guardar';
    emit('saved');
  };
  dlg.querySelector('[data-ics]').onclick = () => downloadICS(ev);
  dlg.querySelector('[data-share]').onclick = async () => {
    dlg.querySelector('#details-msg').textContent = await shareEvent(ev);
  };
}

export function initDetails() {
  const dlg = document.getElementById('details');
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
}
