// GeoMapa: intenta Leaflet + OpenStreetMap desde cdnjs; si no carga, usa un
// mapa SVG interno con las 33 comunas (no depende de la red).
import { state, escapeHTML } from './state.js';
import { setFilter } from './filters.js';

const LEAFLET_JS = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
const LEAFLET_CSS = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';
const COLORS = { Cultura: '#e0633f', Comunidad: '#a86a1c', Empresarial: '#3f3d56' };
let leafletPromise = null;
let lmap = null;
let layer = null;
let mode = null;

function loadLeaflet(timeoutMs = 5000) {
  if (window.L) return Promise.resolve(window.L);
  if (leafletPromise) return leafletPromise;
  leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet'; css.href = LEAFLET_CSS;
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = LEAFLET_JS; s.async = true;
    const timer = setTimeout(() => reject(new Error('timeout')), timeoutMs);
    s.onload = () => { clearTimeout(timer); window.L ? resolve(window.L) : reject(new Error('sin L')); };
    s.onerror = () => { clearTimeout(timer); reject(new Error('CDN no disponible')); };
    document.head.appendChild(s);
  });
  return leafletPromise;
}

function communeStats() {
  // Conteo por comuna con los eventos filtrados actualmente.
  const stats = {};
  state.communes.forEach((c) => { stats[c.name] = { ...c, total: 0, byCat: {} }; });
  state.events.forEach((e) => {
    const s = stats[e.commune]; if (!s) return;
    s.total += 1; s.byCat[e.category] = (s.byCat[e.category] || 0) + 1;
  });
  Object.values(stats).forEach((s) => {
    const cats = Object.entries(s.byCat).sort((a, b) => b[1] - a[1]);
    s.dominant = cats.length ? cats[0][0] : null;
  });
  return Object.values(stats);
}

function popupHTML(s) {
  const cats = Object.entries(s.byCat).map(([k, v]) => `${escapeHTML(k)}: ${v}`).join(' · ');
  return `<b>${escapeHTML(s.name)}</b><br>Provincia de ${escapeHTML(s.province)}<br>${s.total} evento${s.total === 1 ? '' : 's'}${cats ? '<br>' + cats : ''}`;
}

export async function renderMap() {
  const el = document.getElementById('map');
  const label = document.getElementById('map-mode');
  if (mode === null) {
    try {
      await loadLeaflet();
      mode = 'leaflet';
    } catch (_) {
      mode = 'svg';
    }
  }
  const stats = communeStats();
  if (mode === 'leaflet') {
    label.textContent = 'Mapa Leaflet + OpenStreetMap. Cada punto es una comuna (ubicación aproximada de su cabecera), coloreado por su categoría dominante.';
    const L = window.L;
    if (!lmap) {
      el.innerHTML = '';
      lmap = L.map(el, { scrollWheelZoom: false }).setView([-37.35, -72.75], 8);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18, attribution: '&copy; colaboradores de OpenStreetMap',
      }).addTo(lmap);
    }
    if (layer) layer.remove();
    layer = L.layerGroup().addTo(lmap);
    stats.forEach((s) => {
      const m = L.circleMarker([s.lat, s.lon], {
        radius: s.total ? Math.min(7 + s.total * 2, 22) : 6,
        color: s.dominant ? COLORS[s.dominant] : '#b9b9c3', weight: 2,
        fillColor: s.dominant ? COLORS[s.dominant] : '#ffffff', fillOpacity: s.total ? 0.8 : 1,
      }).bindPopup(popupHTML(s) + `<br><a href="#" data-commune="${escapeHTML(s.name)}">Ver en la agenda</a>`);
      m.on('popupopen', (e) => {
        const a = e.popup.getElement().querySelector('[data-commune]');
        if (a) a.onclick = (ev) => { ev.preventDefault(); goToCommune(s.name); };
      });
      m.addTo(layer);
    });
    setTimeout(() => lmap.invalidateSize(), 50);
    return;
  }
  label.textContent = 'Mapa interno (sin conexión al CDN de mapas). Cada punto es una comuna, coloreado por su categoría dominante.';
  el.innerHTML = svgMap(stats);
  el.querySelectorAll('[data-commune]').forEach((g) => {
    g.addEventListener('click', () => goToCommune(g.dataset.commune));
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter') goToCommune(g.dataset.commune); });
  });
}

function goToCommune(name) {
  setFilter('commune', name);
  document.querySelector('[data-view="agenda"]').click();
}

function svgMap(stats) {
  const W = 900; const H = 640; const pad = 60;
  const lats = stats.map((s) => s.lat); const lons = stats.map((s) => s.lon);
  const minLat = Math.min(...lats); const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons); const maxLon = Math.max(...lons);
  // Proyección equirectangular con corrección por coseno de la latitud.
  const k = Math.cos((minLat + maxLat) / 2 * Math.PI / 180);
  const sx = (W - 2 * pad) / ((maxLon - minLon) * k); const sy = (H - 2 * pad) / (maxLat - minLat);
  const s = Math.min(sx, sy);
  const x = (lon) => pad + (lon - minLon) * k * s;
  const y = (lat) => pad + (maxLat - lat) * s;
  // Etiquetas con anticolisión simple: prueba 6 posiciones y elige la primera libre.
  const boxes = [];
  const overlaps = (b) => boxes.some((o) => b.x < o.x + o.w && b.x + b.w > o.x && b.y < o.y + o.h && b.y + b.h > o.y);
  const order = [...stats].sort((a, b) => b.total - a.total || a.lon - b.lon);
  stats.forEach((c) => { const r = c.total ? Math.min(7 + c.total * 2, 20) : 6; boxes.push({ x: x(c.lon) - r, y: y(c.lat) - r, w: 2 * r, h: 2 * r }); });
  const labels = new Map();
  order.forEach((c) => {
    const r = c.total ? Math.min(7 + c.total * 2, 20) : 6;
    const text = c.name + (c.total ? ` (${c.total})` : '');
    const w = text.length * 6.2; const h = 13; const cx = x(c.lon); const cy = y(c.lat);
    const cands = [[cx + r + 3, cy - h / 2], [cx - r - 3 - w, cy - h / 2], [cx + r, cy - r - h], [cx + r, cy + r],
      [cx - w - r, cy - r - h], [cx - w - r, cy + r], [cx + r + 3, cy - h * 1.6], [cx + r + 3, cy + h * 0.6]];
    let pos = cands.find(([lx, ly]) => !overlaps({ x: lx, y: ly, w, h })) || cands[0];
    boxes.push({ x: pos[0], y: pos[1], w, h });
    labels.set(c.name, { x: pos[0], y: pos[1] + 10, text });
  });
  const pts = stats.map((c) => {
    const r = c.total ? Math.min(7 + c.total * 2, 20) : 6;
    const fill = c.dominant ? COLORS[c.dominant] : '#ffffff';
    const stroke = c.dominant ? COLORS[c.dominant] : '#b9b9c3';
    const lb = labels.get(c.name);
    return `<g class="commune" data-commune="${escapeHTML(c.name)}" tabindex="0" role="button" aria-label="${escapeHTML(c.name)}: ${c.total} eventos">
      <title>${escapeHTML(c.name)} — ${c.total} evento${c.total === 1 ? '' : 's'}</title>
      <circle cx="${x(c.lon).toFixed(1)}" cy="${y(c.lat).toFixed(1)}" r="${r}" fill="${fill}" fill-opacity="${c.total ? 0.85 : 1}" stroke="${stroke}" stroke-width="2"/>
      <text x="${lb.x.toFixed(1)}" y="${lb.y.toFixed(1)}">${escapeHTML(lb.text)}</text></g>`;
  }).join('');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mapa esquemático de las 33 comunas del Biobío">
    <rect width="${W}" height="${H}" fill="#f7f7f8"/>
    <text x="${pad}" y="22" fill="#5f6270">Océano Pacífico ←</text>
    <text x="${W - pad - 160}" y="22" fill="#5f6270">→ Cordillera de los Andes</text>
    ${pts}</svg>`;
}
