"""Esquema SQLite, deduplicación y consultas.

Todas las cifras que muestra la app (estado, cobertura) se calculan aquí,
consultando la base en el momento de la petición.
"""
import json
import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

import metadata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "eventos.db")

CATEGORIES = ("Cultura", "Comunidad", "Empresarial")
STATUSES = ("Confirmado", "Por confirmar", "Reprogramado", "Cancelado", "Agotado")
PRICE_STATUSES = ("free", "paid", "pending")
TRACKED_FIELDS = ("title", "date", "end_date", "time", "venue", "price_value",
                  "price_status", "status")
TITLE_SIMILARITY = 0.85
MAX_TIME_GAP_MIN = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    date TEXT NOT NULL,
    end_date TEXT,
    time TEXT,
    end_time TEXT,
    venue TEXT,
    address TEXT,
    commune TEXT NOT NULL,
    province TEXT,
    category TEXT NOT NULL DEFAULT 'Cultura',
    tags TEXT DEFAULT '[]',
    audience TEXT,
    access TEXT,
    price_value INTEGER,
    price_status TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'Por confirmar',
    source TEXT,
    source_url TEXT,
    source_type TEXT,
    source_priority INTEGER DEFAULT 3,
    official INTEGER DEFAULT 0,
    sources_json TEXT DEFAULT '[]',
    image_url TEXT,
    image_official INTEGER DEFAULT 0,
    latitude REAL,
    longitude REAL,
    location_accuracy TEXT,
    discovered_at TEXT,
    updated_at TEXT,
    changed_at TEXT,
    created_at TEXT,
    dedupe_key TEXT,
    origin TEXT DEFAULT 'crawl'
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_commune ON events(commune);
CREATE INDEX IF NOT EXISTS idx_events_dedupe ON events(dedupe_key);

CREATE TABLE IF NOT EXISTS event_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source TEXT,
    source_url TEXT,
    changed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_event ON event_changes(event_id);

CREATE TABLE IF NOT EXISTS source_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    domain TEXT,
    found_on TEXT,
    reason TEXT,
    status TEXT DEFAULT 'Pendiente de revisión',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS possible_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    raw_text TEXT,
    date TEXT,
    commune TEXT,
    source TEXT,
    source_url TEXT,
    reason TEXT,
    status TEXT DEFAULT 'Pendiente de revisión',
    created_at TEXT,
    UNIQUE(title, source_url)
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    date TEXT NOT NULL,
    time TEXT,
    venue TEXT,
    commune TEXT NOT NULL,
    category TEXT,
    price_text TEXT,
    contact TEXT,
    source_url TEXT,
    status TEXT NOT NULL DEFAULT 'Pendiente de revisión',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_url TEXT,
    started_at TEXT,
    finished_at TEXT,
    ok INTEGER DEFAULT 0,
    http_status INTEGER,
    pages_fetched INTEGER DEFAULT 0,
    events_found INTEGER DEFAULT 0,
    events_inserted INTEGER DEFAULT 0,
    events_merged INTEGER DEFAULT 0,
    possible_found INTEGER DEFAULT 0,
    error TEXT
);
"""

_write_lock = threading.Lock()


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso():
    return date.today().isoformat()


def connect(path=None):
    path = path or os.environ.get("EVENTOS_DB") or DEFAULT_DB
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------- dedupe

def _paren_parts(title):
    import re
    return sorted(metadata.normalize(p) for p in re.findall(r"\(([^)]*)\)", title or "") if p.strip())


def _title_core(title):
    import re
    return metadata.normalize(re.sub(r"\([^)]*\)", " ", title or ""))


def _minutes(t):
    if not t or ":" not in t:
        return None
    h, m = t.split(":")[:2]
    try:
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def times_compatible(t1, t2):
    """False si ambos horarios existen y difieren en más de 60 minutos."""
    a, b = _minutes(t1), _minutes(t2)
    if a is None or b is None:
        return True
    return abs(a - b) <= MAX_TIME_GAP_MIN


def titles_match(a, b):
    """True si los títulos describen el mismo evento.

    Salvaguarda: si uno tiene contenido entre paréntesis que el otro no tiene
    (o tienen paréntesis distintos), NO es el mismo evento:
    'Obra X' vs 'Obra X (2ª función)'.
    """
    if _paren_parts(a) != _paren_parts(b):
        return False
    ca, cb = _title_core(a), _title_core(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    return SequenceMatcher(None, ca, cb).ratio() >= TITLE_SIMILARITY


def make_dedupe_key(ev):
    return "|".join([metadata.slug(ev.get("title")), ev.get("date") or "",
                     metadata.slug(ev.get("commune")), ev.get("time") or ""])


def find_duplicate(conn, ev):
    """Busca un evento existente que sea el mismo que `ev`.

    1) Mismo source_url + título equivalente (permite detectar cambios de fecha).
    2) Misma fecha + misma comuna + título similar (difflib) + horarios compatibles.
    """
    title, commune, d = ev.get("title"), ev.get("commune"), ev.get("date")
    if ev.get("source_url"):
        rows = conn.execute(
            "SELECT * FROM events WHERE source_url = ? OR sources_json LIKE ?",
            (ev["source_url"], '%' + json.dumps(ev["source_url"])[1:-1] + '%')).fetchall()
        for r in rows:
            if titles_match(r["title"], title) and times_compatible(r["time"], ev.get("time")) \
                    and r["commune"] == commune:
                # Fecha distinta desde la MISMA página de un solo evento => posible
                # reprogramación. Si la página lista varias fechas (temporada),
                # cada fecha es un evento distinto y no se fusiona.
                if r["date"] == d or (ev.get("single_event_page")
                                      and not _has_other_events_from_url(conn, r)):
                    return r
    rows = conn.execute("SELECT * FROM events WHERE date = ? AND commune = ?", (d, commune)).fetchall()
    for r in rows:
        if not times_compatible(r["time"], ev.get("time")):
            continue
        if titles_match(r["title"], title):
            return r
    return None


def _has_other_events_from_url(conn, row):
    n = conn.execute("SELECT COUNT(*) FROM events WHERE source_url = ? AND id != ?",
                     (row["source_url"], row["id"])).fetchone()[0]
    return n > 0


# ---------------------------------------------------------------- upsert

def _commune_info(commune, communes):
    for c in communes or []:
        if c["name"] == commune:
            return c
    return None


def _clean_event(ev, communes=None):
    e = dict(ev)
    e["title"] = " ".join((e.get("title") or "").split())
    e.setdefault("category", "Cultura")
    if e["category"] not in CATEGORIES:
        e["category"] = metadata.guess_category(e["title"] + " " + (e.get("description") or ""))
    if e.get("price_status") not in PRICE_STATUSES:
        e["price_status"] = "pending"
    if e.get("status") not in STATUSES:
        e["status"] = "Confirmado" if e.get("official") and e.get("time") else "Por confirmar"
    tags = e.get("tags") or []
    e["tags"] = json.dumps(tags if isinstance(tags, list) else [tags], ensure_ascii=False)
    info = _commune_info(e.get("commune"), communes)
    if info:
        e.setdefault("province", info["province"])
        if e.get("latitude") is None:
            e["latitude"], e["longitude"] = info["lat"], info["lon"]
            e["location_accuracy"] = "comuna"
    e["official"] = 1 if e.get("official") else 0
    e["image_official"] = 1 if e.get("image_url") else 0
    return e


def _source_entry(ev):
    return {"name": ev.get("source"), "url": ev.get("source_url"),
            "type": ev.get("source_type"), "priority": ev.get("source_priority", 3),
            "official": bool(ev.get("official")), "seen_at": now_iso()}


EVENT_COLUMNS = ("title", "description", "date", "end_date", "time", "end_time", "venue",
                 "address", "commune", "province", "category", "tags", "audience", "access",
                 "price_value", "price_status", "status", "source", "source_url",
                 "source_type", "source_priority", "official", "image_url", "image_official",
                 "latitude", "longitude", "location_accuracy", "origin")


def upsert_event(conn, ev, communes=None):
    """Inserta o fusiona un evento. Devuelve (id, 'inserted'|'merged'|'unchanged').

    Requiere title, date (YYYY-MM-DD) y commune; si faltan, ValueError.
    """
    if not ev.get("title") or not ev.get("date") or not ev.get("commune"):
        raise ValueError("Evento incompleto: se requieren title, date y commune")
    e = _clean_event(ev, communes)
    with _write_lock:
        dup = find_duplicate(conn, e)
        ts = now_iso()
        if dup is None:
            sources = [_source_entry(e)] + [
                {"name": s.get("name"), "url": s.get("url"), "seen_at": ts}
                for s in (ev.get("extra_sources") or [])]
            cols = list(EVENT_COLUMNS) + ["sources_json", "discovered_at", "updated_at",
                                          "created_at", "dedupe_key"]
            vals = [e.get(c) for c in EVENT_COLUMNS] + [
                json.dumps(sources, ensure_ascii=False), ts, ts, ts, make_dedupe_key(e)]
            vals[cols.index("origin")] = e.get("origin") or "crawl"
            cur = conn.execute("INSERT INTO events (%s) VALUES (%s)" % (
                ",".join(cols), ",".join("?" * len(cols))), vals)
            conn.commit()
            return cur.lastrowid, "inserted"
        return _merge(conn, dup, e, ts)


def _merge(conn, row, e, ts):
    changed = False
    sources = json.loads(row["sources_json"] or "[]")
    urls = {s.get("url") for s in sources}
    if e.get("source_url") not in urls:
        sources.append(_source_entry(e))
        changed = True
    incoming_prio = e.get("source_priority") or 3
    existing_prio = row["source_priority"] or 3
    authoritative = incoming_prio <= existing_prio
    updates = {}
    for f in TRACKED_FIELDS:
        new, old = e.get(f), row[f]
        if new in (None, ""):
            continue
        if f == "price_status" and new == "pending":
            continue
        if f == "status" and new == "Por confirmar" and old:
            continue
        if old in (None, "") or (authoritative and str(new) != str(old)):
            if str(new) != str(old):
                updates[f] = new
    if "date" in updates and row["date"] and "status" not in updates \
            and row["status"] not in ("Cancelado",):
        updates["status"] = "Reprogramado"
    for f in ("description", "address", "image_url", "audience", "access", "end_time"):
        if e.get(f) and not row[f]:
            updates[f] = e[f]
            if f == "image_url":
                updates["image_official"] = 1
    if authoritative and e.get("official") and not row["official"]:
        updates["official"] = 1
        updates["source"], updates["source_url"] = e.get("source"), e.get("source_url")
        updates["source_type"], updates["source_priority"] = e.get("source_type"), incoming_prio
    for f, new in updates.items():
        if f in TRACKED_FIELDS:
            conn.execute(
                "INSERT INTO event_changes (event_id, field, old_value, new_value, source, source_url, changed_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (row["id"], f, None if row[f] is None else str(row[f]), str(new),
                 e.get("source"), e.get("source_url"), ts))
    if updates or changed:
        updates["sources_json"] = json.dumps(sources, ensure_ascii=False)
        updates["updated_at"] = ts
        if any(f in TRACKED_FIELDS for f in updates):
            updates["changed_at"] = ts
        merged = dict(row)
        merged.update(updates)
        updates["dedupe_key"] = make_dedupe_key(merged)
        conn.execute("UPDATE events SET %s WHERE id = ?" % ",".join("%s = ?" % k for k in updates),
                     list(updates.values()) + [row["id"]])
        conn.commit()
        return row["id"], "merged"
    return row["id"], "unchanged"


# ---------------------------------------------------------------- reads

def event_to_dict(row):
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["sources"] = json.loads(d.pop("sources_json", None) or "[]")
    d["official"] = bool(d["official"])
    d["image_official"] = bool(d["image_official"])
    return d


def query_events(conn, date_from=None, date_to=None, commune=None, category=None,
                 price_status=None, q=None, limit=1000):
    sql, args = ["SELECT * FROM events WHERE 1=1"], []
    if date_from:
        sql.append("AND COALESCE(end_date, date) >= ?")
        args.append(date_from)
    if date_to:
        sql.append("AND date <= ?")
        args.append(date_to)
    if commune:
        sql.append("AND commune = ?")
        args.append(commune)
    if category:
        sql.append("AND category = ?")
        args.append(category)
    if price_status:
        sql.append("AND price_status = ?")
        args.append(price_status)
    rows = conn.execute(" ".join(sql) + " ORDER BY date, COALESCE(time, '99:99'), title LIMIT ?",
                        args + [int(limit)]).fetchall()
    out = [event_to_dict(r) for r in rows]
    if q:
        nq = metadata.normalize(q)
        out = [e for e in out if nq in metadata.normalize(" ".join(
            str(e.get(k) or "") for k in ("title", "description", "venue", "commune", "source")
        ) + " " + " ".join(e["tags"]))]
    return out


def get_event(conn, event_id):
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        return None
    ev = event_to_dict(row)
    ev["changes"] = [dict(r) for r in conn.execute(
        "SELECT field, old_value, new_value, source, source_url, changed_at FROM event_changes"
        " WHERE event_id = ? ORDER BY changed_at DESC, id DESC", (event_id,))]
    return ev


def _vigente_clause():
    return "COALESCE(end_date, date) >= ? AND status != 'Cancelado'"


def compute_status(conn, sources, communes):
    t = today_iso()
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    last = conn.execute("SELECT * FROM source_runs ORDER BY id DESC LIMIT 1").fetchone()
    runs_ok = one("SELECT COUNT(DISTINCT source_name) FROM source_runs WHERE ok = 1")
    return {
        "generated_at": now_iso(),
        "today": t,
        "events_total": one("SELECT COUNT(*) FROM events"),
        "events_seed": one("SELECT COUNT(*) FROM events WHERE origin = 'seed'"),
        "events_crawled": one("SELECT COUNT(*) FROM events WHERE origin = 'crawl'"),
        "events_submitted": one("SELECT COUNT(*) FROM events WHERE origin = 'submission'"),
        "events_current": one("SELECT COUNT(*) FROM events WHERE " + _vigente_clause(), t),
        "events_past": one("SELECT COUNT(*) FROM events WHERE COALESCE(end_date, date) < ?", t),
        "events_cancelled": one("SELECT COUNT(*) FROM events WHERE status = 'Cancelado'"),
        "communes_total": len(communes),
        "communes_with_events": one("SELECT COUNT(DISTINCT commune) FROM events"),
        "communes_with_current_events": one(
            "SELECT COUNT(DISTINCT commune) FROM events WHERE " + _vigente_clause(), t),
        "sources_configured": len(sources),
        "sources_enabled": sum(1 for s in sources if s.get("enabled")),
        "sources_verified_live": sum(1 for s in sources if s.get("verified_live")),
        "sources_with_successful_run": runs_ok,
        "source_runs_total": one("SELECT COUNT(*) FROM source_runs"),
        "last_run": dict(last) if last else None,
        "possible_events_pending": one(
            "SELECT COUNT(*) FROM possible_events WHERE status = 'Pendiente de revisión'"),
        "source_candidates_pending": one(
            "SELECT COUNT(*) FROM source_candidates WHERE status = 'Pendiente de revisión'"),
        "submissions_pending": one(
            "SELECT COUNT(*) FROM submissions WHERE status = 'Pendiente de revisión'"),
    }


def compute_coverage(conn, sources, communes):
    t = today_iso()
    rows = conn.execute(
        "SELECT commune, category, COUNT(*) n, SUM(CASE WHEN " + _vigente_clause() +
        " THEN 1 ELSE 0 END) cur FROM events GROUP BY commune, category", (t,)).fetchall()
    stats = {}
    for r in rows:
        s = stats.setdefault(r["commune"], {"total": 0, "current": 0, "by_category": {}})
        s["total"] += r["n"]
        s["current"] += r["cur"] or 0
        s["by_category"][r["category"]] = r["n"]
    last_runs = {r["source_name"]: dict(r) for r in conn.execute(
        "SELECT * FROM source_runs WHERE id IN (SELECT MAX(id) FROM source_runs GROUP BY source_name)")}
    out = []
    for c in communes:
        own = [s for s in sources if s.get("commune") == c["name"]]
        st = stats.get(c["name"], {"total": 0, "current": 0, "by_category": {}})
        bc = st["by_category"]
        out.append({
            "commune": c["name"], "province": c["province"], "lat": c["lat"], "lon": c["lon"],
            "events_total": st["total"], "events_current": st["current"],
            "by_category": {k: bc.get(k, 0) for k in CATEGORIES},
            "dominant_category": max(bc, key=bc.get) if bc else None,
            "sources_configured": len(own),
            "sources_enabled": sum(1 for s in own if s.get("enabled")),
            "sources_verified_live": sum(1 for s in own if s.get("verified_live")),
            "sources_ran_ok": sum(1 for s in own if last_runs.get(s["name"], {}).get("ok")),
        })
    regional = [s for s in sources if not s.get("commune")]
    return {"generated_at": now_iso(), "communes": out,
            "regional_sources": len(regional),
            "regional_sources_enabled": sum(1 for s in regional if s.get("enabled"))}


# ---------------------------------------------------------------- otros

def add_submission(conn, sub):
    ts = now_iso()
    with _write_lock:
        cur = conn.execute(
            "INSERT INTO submissions (title, description, date, time, venue, commune, category,"
            " price_text, contact, source_url, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (sub["title"], sub.get("description"), sub["date"], sub.get("time"), sub.get("venue"),
             sub["commune"], sub.get("category"), sub.get("price_text"), sub.get("contact"),
             sub.get("source_url"), "Pendiente de revisión", ts))
        conn.commit()
    return cur.lastrowid


def add_possible_event(conn, pe):
    with _write_lock:
        cur = conn.execute(
            "INSERT OR IGNORE INTO possible_events (title, raw_text, date, commune, source,"
            " source_url, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (pe["title"][:300], (pe.get("raw_text") or "")[:2000], pe.get("date"), pe.get("commune"),
             pe.get("source"), pe.get("source_url"), pe.get("reason"), now_iso()))
        conn.commit()
    return cur.rowcount


def add_source_candidate(conn, url, domain, found_on, reason):
    with _write_lock:
        cur = conn.execute(
            "INSERT OR IGNORE INTO source_candidates (url, domain, found_on, reason, created_at)"
            " VALUES (?,?,?,?,?)", (url, domain, found_on, reason, now_iso()))
        conn.commit()
    return cur.rowcount


def record_run(conn, run):
    cols = ("source_name", "source_url", "started_at", "finished_at", "ok", "http_status",
            "pages_fetched", "events_found", "events_inserted", "events_merged",
            "possible_found", "error")
    with _write_lock:
        conn.execute("INSERT INTO source_runs (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))),
                     [run.get(c) for c in cols])
        conn.commit()


def list_table(conn, table, limit=500):
    assert table in ("possible_events", "source_candidates", "submissions", "source_runs")
    return [dict(r) for r in conn.execute("SELECT * FROM %s ORDER BY id DESC LIMIT ?" % table, (limit,))]


def load_seed(conn, path, communes):
    """Carga eventos semilla. Devuelve dict con conteos. Idempotente (dedupe)."""
    if not os.path.exists(path):
        return {"inserted": 0, "merged": 0, "unchanged": 0}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    events = data.get("events", data) if isinstance(data, dict) else data
    counts = {"inserted": 0, "merged": 0, "unchanged": 0}
    for ev in events:
        ev = dict(ev)
        ev["origin"] = "seed"
        _, action = upsert_event(conn, ev, communes)
        counts[action] += 1
    return counts


def is_new(ev, days=3):
    try:
        return datetime.fromisoformat(ev["discovered_at"]) >= datetime.now() - timedelta(days=days)
    except (TypeError, ValueError, KeyError):
        return False
