// Panel de administración: estado real, cobertura, fuentes, posibles eventos,
// candidatas, envíos y actualización manual.
import { api, escapeHTML, safeURL } from './state.js';
import { renderCoverage } from './coverage.js';

const stat = (n, label) => `<div class="stat"><b>${escapeHTML(n ?? '—')}</b><span>${escapeHTML(label)}</span></div>`;
const link = (u, t) => (safeURL(u) ? `<a href="${escapeHTML(u)}" target="_blank" rel="noopener">${escapeHTML(t || u)}</a>` : escapeHTML(t || u || ''));
let pollTimer = null;

export async function renderAdmin() {
  const root = document.getElementById('view-admin');
  root.classList.add('admin');
  root.innerHTML = `
    <div class="view-toolbar"><button id="refresh-btn" class="btn">Actualizar fuentes ahora</button>
      <span id="refresh-msg" class="muted" aria-live="polite"></span></div>
    <div id="admin-stats" class="stats"></div>
    <h2>Cobertura por comuna</h2><div id="admin-coverage"></div>
    <h2>Fuentes configuradas</h2><div id="admin-sources"></div>
    <h2>Últimas corridas</h2><div id="admin-runs"></div>
    <h2>Posibles eventos (pendientes de revisión)</h2><div id="admin-possible"></div>
    <h2>Fuentes candidatas descubiertas</h2><div id="admin-candidates"></div>
    <h2>Envíos del formulario</h2><div id="admin-subs"></div>`;
  root.querySelector('#refresh-btn').onclick = startRefresh;
  await Promise.all([loadStats(), renderCoverage(root.querySelector('#admin-coverage')), loadSources(), loadTables()]);
}

async function loadStats() {
  const s = await api('/api/status');
  document.getElementById('admin-stats').innerHTML = [
    stat(s.events_total, 'eventos en la base'), stat(s.events_seed, 'eventos semilla'),
    stat(s.events_crawled, 'eventos rastreados'), stat(s.events_current, `eventos vigentes (desde ${s.today})`),
    stat(s.events_past, 'eventos ya pasados'), stat(`${s.communes_with_events}/${s.communes_total}`, 'comunas con eventos'),
    stat(s.sources_configured, 'fuentes configuradas'), stat(s.sources_enabled, 'fuentes habilitadas'),
    stat(s.sources_verified_live, 'fuentes verificadas en vivo'), stat(s.sources_with_successful_run, 'fuentes con corrida exitosa'),
    stat(s.possible_events_pending, 'posibles eventos por revisar'), stat(s.submissions_pending, 'envíos por revisar'),
  ].join('');
  const msg = document.getElementById('refresh-msg');
  const btn = document.getElementById('refresh-btn');
  if (s.refresh.running) {
    msg.textContent = `Actualización en curso desde ${s.refresh.started_at}…`;
    btn.disabled = true;
    clearTimeout(pollTimer); pollTimer = setTimeout(() => renderAdmin(), 3000);
  } else if (s.refresh.summary) {
    const r = s.refresh.summary;
    msg.textContent = `Última actualización (${s.refresh.finished_at}): ${r.sources_ok} de ${r.sources_attempted} fuentes respondieron, ` +
      `${r.events_found} eventos encontrados (${r.events_inserted} nuevos, ${r.events_merged} fusionados), ${r.possible_events} posibles eventos.`;
  } else if (s.last_run) {
    msg.textContent = `Última corrida registrada: ${s.last_run.finished_at}.`;
  } else {
    msg.textContent = 'Aún no se ha ejecutado ninguna actualización en esta base.';
  }
}

async function startRefresh() {
  const msg = document.getElementById('refresh-msg');
  try {
    const r = await api('/api/admin/refresh', { method: 'POST', body: '{}' });
    msg.textContent = r.message;
    setTimeout(() => renderAdmin(), 1500);
  } catch (e) {
    msg.textContent = `No se pudo iniciar: ${e.message}`;
  }
}

async function loadSources() {
  const { sources } = await api('/api/sources');
  const rows = sources.map((s) => `<tr>
    <td>${link(s.url, s.name)}</td><td>${escapeHTML(s.source_type)}</td><td>${escapeHTML(s.commune || 'Regional')}</td>
    <td class="${s.enabled ? 'yes' : 'no'}">${s.enabled ? 'Sí' : 'No'}</td>
    <td class="${s.verified_live ? 'yes' : 'no'}">${s.verified_live ? 'Sí' : 'No'}</td>
    <td>${s.radar_only ? 'Radar' : 'Publica'}</td><td class="notes">${escapeHTML(s.notes)}</td></tr>`).join('');
  document.getElementById('admin-sources').innerHTML = `<div class="table-wrap" style="max-height:420px"><table>
    <thead><tr><th>Fuente</th><th>Tipo</th><th>Comuna</th><th>Habilitada</th><th>Verificada en vivo</th><th>Modo</th><th>Notas</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function table(rows, cols, empty) {
  if (!rows.length) return `<div class="empty">${escapeHTML(empty)}</div>`;
  return `<div class="table-wrap" style="max-height:360px"><table><thead><tr>${cols.map((c) => `<th>${escapeHTML(c[0])}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${c[1](r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

async function loadTables() {
  const [pe, sc, sub, runs] = await Promise.all([api('/api/possible-events'), api('/api/source-candidates'),
    api('/api/submissions'), api('/api/source-runs')]);
  document.getElementById('admin-runs').innerHTML = table(runs.source_runs.slice(0, 80), [
    ['Fuente', (r) => escapeHTML(r.source_name)], ['Fin', (r) => escapeHTML(r.finished_at)],
    ['OK', (r) => (r.ok ? '<span class="yes">Sí</span>' : '<span class="no">No</span>')], ['HTTP', (r) => escapeHTML(r.http_status ?? '—')],
    ['Páginas', (r) => r.pages_fetched], ['Eventos', (r) => r.events_found], ['Posibles', (r) => r.possible_found],
    ['Error', (r) => escapeHTML(r.error || '')]], 'Sin corridas registradas todavía.');
  document.getElementById('admin-possible').innerHTML = table(pe.possible_events, [
    ['Título', (r) => escapeHTML(r.title)], ['Fecha', (r) => escapeHTML(r.date || '¿?')], ['Comuna', (r) => escapeHTML(r.commune || '¿?')],
    ['Fuente', (r) => link(r.source_url, r.source)], ['Motivo', (r) => escapeHTML(r.reason)]], 'No hay posibles eventos pendientes.');
  document.getElementById('admin-candidates').innerHTML = table(sc.source_candidates, [
    ['URL', (r) => link(r.url)], ['Dominio', (r) => escapeHTML(r.domain)], ['Encontrada en', (r) => link(r.found_on)],
    ['Estado', (r) => escapeHTML(r.status)]], 'No hay fuentes candidatas registradas.');
  document.getElementById('admin-subs').innerHTML = table(sub.submissions, [
    ['Título', (r) => escapeHTML(r.title)], ['Fecha', (r) => escapeHTML(r.date)], ['Comuna', (r) => escapeHTML(r.commune)],
    ['Enlace', (r) => link(r.source_url, 'enlace')], ['Estado', (r) => escapeHTML(r.status)], ['Recibido', (r) => escapeHTML(r.created_at)]],
  'No hay envíos.');
}
