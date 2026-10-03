"""Orquestación de la actualización: rastrea las fuentes habilitadas en
paralelo (concurrent.futures) y escribe los resultados en SQLite desde un
único hilo."""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import db
import discovery
from scrapers import deep_crawler, rss
from scrapers.common import fetch

_state = {"running": False, "started_at": None, "finished_at": None, "summary": None}
_lock = threading.Lock()


def state():
    return dict(_state)


def _run_source(source, communes, fetcher):
    if source.get("parser") == "rss":
        res = deep_crawler.CrawlResult()
        page = fetcher(source["url"], timeout=int(source.get("timeout") or 20))
        res.http_status = page.status
        if page.ok:
            res.pages = 1
            res.possibles = rss.possible_events_from_feed(page.text, source, communes)
        else:
            res.error = page.error or "HTTP %s" % page.status
        return res
    return deep_crawler.crawl(source, communes, fetcher=fetcher)


def refresh(conn, sources=None, communes=None, fetcher=fetch, max_workers=6, only=None):
    """Ejecuta el rastreo. Devuelve un resumen con cifras REALES de esta corrida."""
    sources = sources if sources is not None else discovery.load_sources()
    communes = communes if communes is not None else discovery.load_communes()
    todo = [s for s in sources if s.get("enabled") and s.get("parser") != "none"
            and (not only or s["name"] in only)]
    with _lock:
        if _state["running"]:
            return {"error": "Ya hay una actualización en curso"}
        _state.update(running=True, started_at=db.now_iso(), finished_at=None, summary=None)
    summary = {"sources_attempted": len(todo), "sources_ok": 0, "sources_failed": 0,
               "events_found": 0, "events_inserted": 0, "events_merged": 0,
               "possible_events": 0, "candidates": 0, "errors": []}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {pool.submit(_run_source, s, communes, fetcher): (s, db.now_iso()) for s in todo}
            for fut in as_completed(futs):
                s, started = futs[fut]
                run = {"source_name": s["name"], "source_url": s["url"], "started_at": started}
                try:
                    res = fut.result()
                except Exception as exc:  # error inesperado del parser
                    res = deep_crawler.CrawlResult()
                    res.error = "%s: %s" % (type(exc).__name__, exc)
                ins = mer = 0
                for ev in res.events:
                    try:
                        _, action = db.upsert_event(conn, dict(ev, origin="crawl"), communes)
                    except ValueError:
                        continue
                    ins += action == "inserted"
                    mer += action == "merged"
                pos = sum(db.add_possible_event(conn, p) for p in res.possibles)
                cand = discovery.register_candidates(conn, res.candidates, sources)
                ok = res.error is None
                run.update(finished_at=db.now_iso(), ok=1 if ok else 0, http_status=res.http_status,
                           pages_fetched=res.pages, events_found=len(res.events),
                           events_inserted=ins, events_merged=mer, possible_found=pos,
                           error=res.error)
                db.record_run(conn, run)
                summary["sources_ok" if ok else "sources_failed"] += 1
                summary["events_found"] += len(res.events)
                summary["events_inserted"] += ins
                summary["events_merged"] += mer
                summary["possible_events"] += pos
                summary["candidates"] += cand
                if not ok:
                    summary["errors"].append({"source": s["name"], "error": res.error})
    finally:
        with _lock:
            _state.update(running=False, finished_at=db.now_iso(), summary=summary)
    return summary
