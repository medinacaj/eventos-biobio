// Formulario "Publica tu evento": todo envío queda Pendiente de revisión.
import { api, state, escapeHTML } from './state.js';

export function renderSubmissions() {
  const root = document.getElementById('view-submit');
  if (root.dataset.ready) return;
  root.dataset.ready = '1';
  const opts = state.communes.map((c) => `<option>${escapeHTML(c.name)}</option>`).join('');
  root.innerHTML = `
    <p class="notice">Todo evento enviado queda en estado <b>Pendiente de revisión</b> y <b>no se publica automáticamente</b>.
      Incluye un enlace a la publicación oficial si existe. Si tu evento está solo en Instagram, adjunta el enlace o envía la captura
      a quien administra el proyecto: no hacemos scraping de Instagram.</p>
    <div id="sub-msg" aria-live="polite"></div>
    <form id="sub-form" class="form" novalidate>
      <label class="full">Título *<input name="title" required minlength="4" maxlength="200"></label>
      <label>Fecha *<input name="date" type="date" required></label>
      <label>Hora<input name="time" type="time"></label>
      <label>Comuna *<select name="commune" required><option value="">Elige…</option>${opts}</select></label>
      <label>Categoría<select name="category"><option value="">Sin especificar</option><option>Cultura</option><option>Comunidad</option><option>Empresarial</option></select></label>
      <label class="full">Lugar<input name="venue" maxlength="300"></label>
      <label>Precio (texto)<input name="price_text" placeholder="Ej: Gratis, $5.000" maxlength="200"></label>
      <label>Enlace oficial<input name="source_url" type="url" placeholder="https://"></label>
      <label class="full">Descripción<textarea name="description" rows="4" maxlength="2000"></textarea></label>
      <label class="full">Contacto (opcional, no se publica)<input name="contact" maxlength="200"></label>
      <div class="full"><button class="btn" type="submit">Enviar para revisión</button></div>
    </form>`;
  const form = root.querySelector('#sub-form');
  const msg = root.querySelector('#sub-msg');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    Object.keys(data).forEach((k) => { if (data[k] === '') delete data[k]; });
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const r = await api('/api/submissions', { method: 'POST', body: JSON.stringify(data) });
      msg.innerHTML = `<p class="notice ok">${escapeHTML(r.message)} (envío #${r.id})</p>`;
      form.reset();
    } catch (err) {
      const errs = (err.data && err.data.errors) || [err.message];
      msg.innerHTML = `<p class="notice err">${errs.map(escapeHTML).join('<br>')}</p>`;
    } finally {
      btn.disabled = false;
    }
  });
}
