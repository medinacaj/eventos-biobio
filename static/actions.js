// Acciones sobre eventos: guardar, compartir y exportar a calendario (.ics).
import { toggleSaved, isSaved, emit } from './state.js';

export function saveButton(ev) {
  const on = isSaved(ev.id);
  return `<button class="save-btn" data-save="${ev.id}" aria-pressed="${on}" title="${on ? 'Quitar de guardados' : 'Guardar'}" aria-label="${on ? 'Quitar de guardados' : 'Guardar evento'}">${on ? '★' : '☆'}</button>`;
}

export function bindSaveButtons(root, eventsById) {
  root.querySelectorAll('[data-save]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const ev = eventsById.get(Number(btn.dataset.save));
      if (!ev) return;
      const on = toggleSaved(ev);
      btn.setAttribute('aria-pressed', on);
      btn.textContent = on ? '★' : '☆';
      emit('saved');
    });
  });
}

function icsEscape(s) { return String(s || '').replace(/[\;,]/g, (c) => '\\' + c).replace(/\n/g, '\\n'); }

export function downloadICS(ev) {
  const d = ev.date.replace(/-/g, '');
  let dtStart; let dtEnd;
  if (ev.time) {
    const t = ev.time.replace(':', '') + '00';
    dtStart = `DTSTART:${d}T${t}`;
    const endT = (ev.end_time || ev.time).replace(':', '') + '00';
    dtEnd = ev.end_time ? `DTEND:${d}T${endT}` : '';
  } else {
    dtStart = `DTSTART;VALUE=DATE:${d}`;
    const end = new Date(ev.end_date || ev.date); end.setDate(end.getDate() + 1);
    dtEnd = `DTEND;VALUE=DATE:${end.toISOString().slice(0, 10).replace(/-/g, '')}`;
  }
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Eventos Biobio//ES', 'BEGIN:VEVENT',
    `UID:evento-${ev.id}@eventos-biobio.local`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}Z`,
    dtStart, dtEnd, `SUMMARY:${icsEscape(ev.title)}`,
    `LOCATION:${icsEscape([ev.venue, ev.commune].filter(Boolean).join(', '))}`,
    `DESCRIPTION:${icsEscape((ev.description || '') + (ev.source_url ? '\nFuente: ' + ev.source_url : ''))}`,
    'END:VEVENT', 'END:VCALENDAR'].filter(Boolean);
  const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `evento-${ev.id}.ics`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export async function shareEvent(ev) {
  const text = `${ev.title} — ${ev.date}${ev.time ? ' ' + ev.time : ''}, ${ev.commune}`;
  const url = ev.source_url || location.href;
  try {
    if (navigator.share) { await navigator.share({ title: ev.title, text, url }); return 'Compartido'; }
    await navigator.clipboard.writeText(`${text}\n${url}`);
    return 'Copiado al portapapeles';
  } catch (_) {
    return 'No se pudo compartir';
  }
}
