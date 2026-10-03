// Matriz de cobertura real por comuna (cifras calculadas por /api/coverage).
import { api, escapeHTML } from './state.js';

const num = (n) => `<td class="num ${n ? '' : 'zero'}">${n}</td>`;

export async function renderCoverage(root) {
  root.innerHTML = '<p class="muted">Calculando cobertura…</p>';
  let cov;
  try { cov = await api('/api/coverage'); } catch (e) {
    root.innerHTML = `<div class="empty">Error: ${escapeHTML(e.message)}</div>`; return;
  }
  let prov = null;
  const rows = [];
  cov.communes.forEach((c) => {
    if (c.province !== prov) {
      prov = c.province;
      rows.push(`<tr class="prov"><td colspan="10">Provincia de ${escapeHTML(prov)}</td></tr>`);
    }
    rows.push(`<tr><td>${escapeHTML(c.commune)}</td>${num(c.events_total)}${num(c.events_current)}
      ${num(c.by_category.Cultura)}${num(c.by_category.Comunidad)}${num(c.by_category.Empresarial)}
      ${num(c.sources_configured)}${num(c.sources_enabled)}${num(c.sources_verified_live)}${num(c.sources_ran_ok)}</tr>`);
  });
  const withEv = cov.communes.filter((c) => c.events_total).length;
  root.innerHTML = `
    <p class="muted">Calculado en vivo desde la base de datos (${escapeHTML(cov.generated_at.replace('T', ' '))}).
      ${withEv} de ${cov.communes.length} comunas tienen al menos un evento cargado.
      Además hay ${cov.regional_sources} fuentes regionales/nacionales sin comuna fija (${cov.regional_sources_enabled} habilitadas).</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Comuna</th><th class="num">Eventos</th><th class="num">Vigentes</th><th class="num">Cultura</th><th class="num">Comunidad</th>
      <th class="num">Empresarial</th><th class="num">Fuentes config.</th><th class="num">Habilitadas</th><th class="num">Verif. en vivo</th><th class="num">Última corrida OK</th></tr></thead>
      <tbody>${rows.join('')}</tbody></table></div>`;
}
