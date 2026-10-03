# Eventos Región del Biobío

App **local** (no hosteada) para descubrir eventos públicos presenciales en las **33 comunas de la Región del Biobío**, Chile: cultura, música, teatro, deporte, ferias, actividades familiares, empresariales y comunitarias.

- Backend: solo librería estándar de Python (`sqlite3`, `http.server`, `urllib`, `concurrent.futures`, `html.parser`). Sin pip, sin frameworks.
- Frontend: HTML + CSS + módulos JavaScript vanilla, sin build step.

## Cómo iniciar

| Sistema | Acción |
|---|---|
| Windows | Doble clic en `iniciar_windows.bat` (usa `launcher.py`) |
| Mac / Linux | `./iniciar_mac_linux.sh` |
| Manual | `python3 launcher.py` (busca puerto libre y abre el navegador) o `python3 app.py --port 8765` |

Requiere Python 3.9+. Al arrancar se crea `data/eventos.db` y se cargan los eventos semilla (`data/seed_events.json`), sin duplicar si ya estaban.

Opcional: copia `.env.example` a `.env` (puerto, ruta de la BD, `ADMIN_TOKEN`).

## Estado real del proyecto (2026-10-03)

> Las cifras de esta sección vienen de ejecutar el código, no de estimaciones.

| Concepto | Valor | Cómo se obtuvo |
|---|---|---|
| Fuentes configuradas | **60** | `config/sources.json` |
| Fuentes habilitadas | **45** | 15 deshabilitadas: dominio sin confirmar, Instagram, gremios sin URL de agenda |
| Fuentes **verificadas en vivo** | **0** | El entorno de construcción bloquea la salida HTTP a esos dominios (proxy 403, también desde la herramienta de lectura web). |
| Actualización real ejecutada | 45 intentadas, **0 OK**, 45 fallidas | `scrapers.runner.refresh()` ejecutado el 2026-10-03: 44 × «Tunnel connection failed: 403», 1 × «HTTP 403». |
| Eventos rastreados | **0** | Consecuencia de lo anterior |
| Eventos semilla | **5** | Verificados por búsqueda web (ver abajo) |
| Eventos vigentes (≥ 2026-10-03) | **4** | `/api/status` |
| Comunas con eventos cargados | **2 de 33** (Concepción, Tomé) | `/api/coverage` |

**Los scrapers están escritos y probados con HTML de ejemplo (tests offline), pero NUNCA se ejecutaron con éxito contra ningún sitio real.** Pueden fallar ante la estructura real de cada sitio. En particular, si un sitio carga su cartelera con JavaScript, el scraper no verá eventos y lo reportará como 0, sin inventar nada.

### Cómo se investigaron las fuentes

Las URLs de `config/sources.json` se obtuvieron con búsquedas web el 2026-10-03. Cada fuente tiene:

- `verified_live`: `true` solo si este proyecto hizo una petición HTTP real y respondió. Hoy es `false` en todas.
- `url_evidence`: `observado_en_busqueda` (el dominio apareció en resultados reales), `resumen_de_busqueda` (solo en un resumen; baja confianza, p. ej. Hualpén), `conocimiento_previo` o `no_confirmado` (estas últimas suelen estar deshabilitadas).
- `notes`: explicación del estado real.

Municipalidades **sin dominio confirmado** (deshabilitadas hasta que alguien verifique la URL a mano): San Pedro de la Paz, Hualqui, Santa Juana, Curanilahue, Tirúa, Antuco, Laja, Quilaco, San Rosendo, Tucapel.

### Eventos semilla

`data/seed_events.json` contiene solo 5 eventos con fuente citable. Como no se pudo abrir ninguna página, cada dato se tomó de lo que el buscador mostraba de esa página; el campo `verification` explica cómo se comprobó cada uno:

1. Inarbolece — 17-10-2026, 19:30, Teatro Biobío, Sala de Cámara ($7.000 / $5.000).
2. Festival Internacional de Arpas — 17-10-2026, 19:00, Teatro Biobío, Sala Principal (gratis con inscripción).
3. Día de la Música Chilena, homenaje a Cecilia — 04-10-2026, 15:00–21:00, Gimnasio Municipal de Tomé (entrada liberada).
4. Mes de la Música, intervención en Plaza de la Independencia — 21-10-2026, **hora y precio por confirmar**, estado «Por confirmar» (el fragmento no mostraba el año explícito).
5. VI Festival Fío-Fío — 23 al 30-09-2026 (**ya pasado**; se deja como ejemplo de evento no vigente).

Verifícalos con el organizador antes de difundirlos.

### Instagram

No se hace scraping de Instagram (requiere login; no se evade login, CAPTCHA ni se usan cookies). Si hace falta contenido de Instagram, quien administre el proyecto debe aportar capturas de pantalla y cargarlas manualmente, por ejemplo con el formulario «Publica tu evento».

## Arquitectura

```
app.py            ThreadingHTTPServer + API JSON sobre SQLite
launcher.py       puerto libre + abre navegador
db.py             esquema SQLite, dedupe, consultas, cifras de estado/cobertura
metadata.py       parsing de fecha/hora/precio en español, comuna, categoría
images.py         imagen oficial (og:image, twitter:image, JSON-LD); nunca se generan
discovery.py      carga/validación de fuentes y registro de fuentes candidatas
config/sources.json, config/communes.json (33 comunas, coords aprox. de la cabecera)
data/seed_events.json
scrapers/         common, generic_events, deep_crawler, sitemap, rss, ticketing, runner
static/           index.html, styles.css, state.js, filters.js, views.js, calendar.js,
                  map.js, actions.js, details.js, submissions.js, admin.js, coverage.js, app.js
tests/            unittest (sin red)
```

### Política de publicación del rastreo

- Solo los datos **estructurados** (JSON-LD `schema.org/Event`) con título, fecha y comuna identificables se publican como eventos.
- El texto con fechas, las notas de prensa y las fuentes `radar_only` (medios, ticketing nacional sin filtro regional) generan **posibles eventos** pendientes de revisión.
- Los enlaces externos que parecen agendas se guardan como **fuentes candidatas**.
- Se respeta `robots.txt`, con un User-Agent identificable y límites de páginas y profundidad por fuente.
- Los envíos del formulario quedan siempre como «Pendiente de revisión»; nunca se publican solos.

### Deduplicación (`db.find_duplicate`)

Fusiona por fecha + comuna + similitud de título (`difflib`, umbral 0,85), **excepto** cuando:

1. ambos horarios existen y difieren en **más de 60 minutos** (dos funciones distintas el mismo día);
2. el contenido **entre paréntesis** difiere (`"Obra X"` vs `"Obra X (2ª función)"`).

Al fusionar se conservan todas las fuentes en `sources_json`. Los cambios de título, fecha, horario, lugar, precio o estado se registran en `event_changes` (valor anterior, valor nuevo, fuente y fecha). Si una página de un solo evento cambia su fecha, el evento pasa a «Reprogramado». Una fuente de menor prioridad no sobrescribe datos de una fuente oficial.

## API

| Método | Ruta | Notas |
|---|---|---|
| GET | `/health` | |
| GET | `/api/events` | filtros `date_from`, `date_to`, `commune`, `category`, `price_status`, `q` |
| GET | `/api/events/<id>` | incluye historial de cambios |
| GET | `/api/status` | cifras calculadas en la petición (semilla / rastreados / vigentes, fuentes configuradas / verificadas) |
| GET | `/api/coverage` | matriz por comuna, calculada en la petición |
| GET | `/api/communes`, `/api/sources`, `/api/possible-events`, `/api/source-candidates`, `/api/submissions`, `/api/source-runs` | |
| POST | `/api/submissions` | valida y deja «Pendiente de revisión» |
| POST | `/api/admin/refresh` | lanza el rastreo en segundo plano; con `ADMIN_TOKEN` exige `X-Admin-Token` |

El servidor escucha solo en `127.0.0.1` por defecto.

## Frontend

Agenda (lista agrupada por fecha o tarjetas), calendario mensual con conteo por día, GeoMapa, guardados (localStorage, sin login), ficha con historial de cambios y exportación `.ics`, formulario «Publica tu evento» y panel de Administración con la matriz de cobertura real.

**GeoMapa:** intenta cargar Leaflet 1.9.4 desde cdnjs.cloudflare.com con teselas de OpenStreetMap. Si el CDN no responde en 5 s, dibuja un mapa SVG interno con las 33 comunas coloreadas por su categoría dominante, sin depender de la red. En el entorno de construcción el CDN estaba bloqueado y **se comprobó el modo SVG** en Chromium; el modo Leaflet no se pudo probar.

## Tests

```
python3 -m unittest discover -s tests -t .
node --check static/*.js   # opcional, solo desarrollo
```

Cubren el esquema e inserción, la deduplicación (incluidos los dos casos límite), el parsing de fecha, hora y precio, la extracción de imagen, los scrapers con HTML/XML de ejemplo y un fetcher falso, la configuración, y un smoke test end-to-end que levanta el servidor real en un puerto local y prueba la API con `urllib`. Ninguno usa la red externa.

Resultado de la última ejecución (2026-10-03): **61 tests, 61 OK, 0 fallos**.

## Limitaciones conocidas

- 0 fuentes verificadas en vivo; los scrapers no se han probado contra sitios reales.
- Muchos sitios municipales publican eventos como noticias sin datos estructurados: solo producirán «posibles eventos» para revisión manual.
- No existe todavía una pantalla para aprobar posibles eventos o envíos; hoy la revisión es de solo lectura en Administración.
- Las coordenadas son de la cabecera comunal (precisión ~1–3 km), no del recinto.
- La inferencia del año en fechas sin año asume el año actual, o el siguiente si la fecha quedó más de 60 días atrás.
- La categoría se infiere por palabras clave y puede equivocarse.
- Ticketing nacional (PuntoTicket, Passline, TuAcceso, PrimeTicket): sin filtro regional confirmado; se filtra por comuna detectada en el recinto o la dirección.
