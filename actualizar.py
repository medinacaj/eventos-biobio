"""Actualización sin interfaz: rastrea las fuentes y guarda el resultado en
archivos versionables, para que una rutina en la nube haga commit y la app
local los cargue al arrancar.

Uso:
    python3 actualizar.py                    # todas las fuentes habilitadas
    python3 actualizar.py --only "Teatro Biobío"
    python3 actualizar.py --no-update-sources

Escribe:
    data/crawled_events.json   eventos rastreados + historial, corridas,
                               posibles eventos y fuentes candidatas
    config/sources.json        verified_live / last_live_check según la
                               respuesta REAL de cada fuente en esta corrida
"""
import argparse
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import db  # noqa: E402
import discovery  # noqa: E402
from scrapers import runner  # noqa: E402
from scrapers.common import fetch  # noqa: E402

CRAWLED_PATH = os.path.join(BASE_DIR, "data", "crawled_events.json")
_STATUS_PREFIX = re.compile(
    r"^(No verificada en vivo:.*?contra esta URL\.|Verificada en vivo el [^.]*\.|"
    r"Última verificación en vivo [^.]*\.(?: Error: [^\n]*?\.)?)\s*", re.S)


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def update_sources_file(path, runs):
    """Marca verified_live según la última petición real a cada fuente."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    by_name = {r["source_name"]: r for r in runs}
    changed = 0
    for s in cfg["sources"]:
        r = by_name.get(s["name"])
        if not r:
            continue
        ok = bool(r["ok"]) and r.get("http_status") is not None and 200 <= r["http_status"] < 300
        day = (r.get("finished_at") or "")[:10]
        if ok:
            prefix = "Verificada en vivo el %s (HTTP %s; %s página(s), %s evento(s))." % (
                day, r["http_status"], r.get("pages_fetched"), r.get("events_found"))
        else:
            err = (r.get("error") or "sin detalle").replace(".", ",")[:160]
            prefix = "Última verificación en vivo %s: falló. Error: %s." % (day, err)
        s["notes"] = prefix + " " + _STATUS_PREFIX.sub("", s.get("notes") or "")
        s["notes"] = s["notes"].strip()
        s["verified_live"] = ok
        s["last_live_check"] = {"at": r.get("finished_at"), "ok": ok, "http_status": r.get("http_status"),
                                "error": r.get("error")}
        changed += 1
    cfg["_notes"] = ("verified_live=true solo si la URL respondió (HTTP 2xx) a una petición real hecha por "
                     "actualizar.py en su última corrida; ver last_live_check. url_evidence indica de dónde salió la URL.")
    _write_json(path, cfg)
    return changed


def main(argv=None, fetcher=fetch, crawled_path=CRAWLED_PATH, sources_path=discovery.SOURCES_PATH):
    ap = argparse.ArgumentParser(description="Rastrea las fuentes y guarda data/crawled_events.json")
    ap.add_argument("--only", action="append", help="nombre exacto de una fuente (repetible)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-update-sources", action="store_true",
                    help="no modificar config/sources.json")
    args = ap.parse_args(argv)

    sources = discovery.load_sources(sources_path)
    communes = discovery.load_communes()
    conn = db.connect(":memory:")
    db.init_db(conn)
    previous = db.load_crawled(conn, crawled_path, communes)  # continuidad del historial
    started = db.now_iso()
    summary = runner.refresh(conn, sources=sources, communes=communes, fetcher=fetcher,
                             max_workers=args.workers, only=args.only)
    if "error" in summary:
        print(summary["error"])
        return 1
    runs = [dict(r) for r in conn.execute(
        "SELECT * FROM source_runs WHERE started_at >= ? ORDER BY source_name", (started,))]
    for r in runs:
        r.pop("id", None)
    pending = [dict(r) for r in conn.execute(
        "SELECT title, raw_text, date, commune, source, source_url, reason FROM possible_events"
        " WHERE date IS NULL OR date >= ? ORDER BY date LIMIT 500", (db.today_iso(),))]
    candidates = [dict(r) for r in conn.execute(
        "SELECT url, domain, found_on, reason FROM source_candidates ORDER BY id LIMIT 500")]
    events = db.export_crawled(conn)
    _write_json(crawled_path, {
        "_notes": "Generado por actualizar.py. Solo contiene lo que las fuentes publicaron en esta "
                  "corrida y en corridas anteriores; nada se completa a mano.",
        "generated_at": db.now_iso(),
        "summary": summary,
        "events": events,
        "runs": runs,
        "possible_events": pending,
        "source_candidates": candidates,
    })
    updated = 0 if args.no_update_sources else update_sources_file(sources_path, runs)
    ok = summary["sources_ok"]
    print("Fuentes intentadas: %d | respondieron: %d | fallaron: %d" % (
        summary["sources_attempted"], ok, summary["sources_failed"]))
    print("Eventos encontrados: %d (nuevos %d, fusionados %d) | eventos en snapshot: %d (antes %d)" % (
        summary["events_found"], summary["events_inserted"], summary["events_merged"], len(events),
        previous["inserted"] + previous["merged"] + previous["unchanged"]))
    print("Posibles eventos pendientes: %d | fuentes candidatas: %d" % (len(pending), len(candidates)))
    print("Fuentes con estado actualizado en sources.json: %d" % updated)
    for e in summary["errors"][:10]:
        print("  - %s: %s" % (e["source"], e["error"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
