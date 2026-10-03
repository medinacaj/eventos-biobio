"""Servidor HTTP local + API JSON sobre SQLite (solo librería estándar).

Uso: python app.py [--port 8765] [--host 127.0.0.1]
"""
import argparse
import json
import mimetypes
import os
import re
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import db
import discovery
import metadata
from scrapers import runner

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SEED_PATH = os.path.join(BASE_DIR, "data", "seed_events.json")
CRAWLED_PATH = os.path.join(BASE_DIR, "data", "crawled_events.json")
MAX_BODY = 64 * 1024


def load_env(path=os.path.join(BASE_DIR, ".env")):
    """Lector mínimo de .env (KEY=VALUE). No sobrescribe variables ya definidas."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class AppContext:
    def __init__(self, db_path=None, load_seed=True):
        self.conn = db.connect(db_path)
        db.init_db(self.conn)
        self.communes = discovery.load_communes()
        self.sources = discovery.load_sources()
        self.commune_names = {c["name"] for c in self.communes}
        self.seed_result = db.load_seed(self.conn, SEED_PATH, self.communes) if load_seed else None
        self.crawled_result = (db.load_crawled(self.conn, CRAWLED_PATH, self.communes)
                               if load_seed else None)


def _valid_date(s):
    try:
        return date.fromisoformat(s).isoformat()
    except (TypeError, ValueError):
        return None


def validate_submission(body, commune_names):
    errors = []
    sub = {k: (str(body.get(k)).strip() if body.get(k) is not None else None) for k in (
        "title", "description", "date", "time", "venue", "commune", "category",
        "price_text", "contact", "source_url")}
    if not sub["title"] or len(sub["title"]) < 4 or len(sub["title"]) > 200:
        errors.append("El título es obligatorio (4 a 200 caracteres).")
    if not _valid_date(sub["date"]):
        errors.append("La fecha es obligatoria (AAAA-MM-DD).")
    if sub["commune"] not in commune_names:
        errors.append("La comuna debe ser una de las 33 comunas del Biobío.")
    if sub["time"] and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", sub["time"]):
        errors.append("La hora debe tener formato HH:MM.")
    if sub["category"] and sub["category"] not in db.CATEGORIES:
        errors.append("Categoría no válida.")
    if sub["source_url"] and not re.match(r"^https?://", sub["source_url"]):
        errors.append("El enlace debe comenzar con http:// o https://")
    for k in ("description", "venue", "price_text", "contact"):
        if sub[k] and len(sub[k]) > 2000:
            errors.append("El campo %s es demasiado largo." % k)
    return sub, errors


def make_handler(ctx):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EventosBiobio/1.0"

        def log_message(self, fmt, *args):
            if os.environ.get("EVENTOS_QUIET") != "1":
                super().log_message(fmt, *args)

        # ---------------------------------------------------------- helpers
        def _json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("Cuerpo demasiado grande")
            raw = self.rfile.read(n) if n else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("Se esperaba un objeto JSON")
            return data

        def _static(self, path):
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            full = os.path.realpath(os.path.join(STATIC_DIR, rel))
            if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
                return self._json({"error": "No encontrado"}, 404)
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ---------------------------------------------------------- GET
        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            p = u.path.rstrip("/") or "/"
            try:
                if p == "/health":
                    return self._json({"ok": True, "time": db.now_iso()})
                if p == "/api/events":
                    for k in ("date_from", "date_to"):
                        if q.get(k) and not _valid_date(q[k]):
                            return self._json({"error": "%s inválida" % k}, 400)
                    events = db.query_events(
                        ctx.conn, date_from=q.get("date_from"), date_to=q.get("date_to"),
                        commune=q.get("commune") or None, category=q.get("category") or None,
                        price_status=q.get("price_status") or None, q=q.get("q") or None)
                    for e in events:
                        e["is_new"] = db.is_new(e)
                    return self._json({"count": len(events), "events": events})
                m = re.fullmatch(r"/api/events/(\d+)", p)
                if m:
                    ev = db.get_event(ctx.conn, int(m.group(1)))
                    if not ev:
                        return self._json({"error": "No encontrado"}, 404)
                    ev["is_new"] = db.is_new(ev)
                    return self._json(ev)
                if p == "/api/status":
                    st = db.compute_status(ctx.conn, ctx.sources, ctx.communes)
                    st["refresh"] = runner.state()
                    return self._json(st)
                if p == "/api/coverage":
                    return self._json(db.compute_coverage(ctx.conn, ctx.sources, ctx.communes))
                if p == "/api/communes":
                    return self._json({"communes": ctx.communes})
                if p == "/api/sources":
                    return self._json({"sources": discovery.public_sources(ctx.sources)})
                if p == "/api/possible-events":
                    return self._json({"possible_events": db.list_table(ctx.conn, "possible_events")})
                if p == "/api/source-candidates":
                    return self._json({"source_candidates": db.list_table(ctx.conn, "source_candidates")})
                if p == "/api/submissions":
                    return self._json({"submissions": db.list_table(ctx.conn, "submissions")})
                if p == "/api/source-runs":
                    return self._json({"source_runs": db.list_table(ctx.conn, "source_runs", 200)})
                if p.startswith("/api/"):
                    return self._json({"error": "Ruta no encontrada"}, 404)
                return self._static(u.path)
            except Exception as exc:  # nunca dejar al cliente colgado
                return self._json({"error": "Error interno: %s" % exc}, 500)

        # ---------------------------------------------------------- POST
        def do_POST(self):
            p = urlparse(self.path).path.rstrip("/")
            try:
                body = self._body()
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json({"error": str(exc)}, 400)
            if p == "/api/submissions":
                sub, errors = validate_submission(body, ctx.commune_names)
                if errors:
                    return self._json({"errors": errors}, 400)
                sid = db.add_submission(ctx.conn, sub)
                return self._json({"id": sid, "status": "Pendiente de revisión",
                                   "message": "Gracias. Tu evento quedó pendiente de revisión; "
                                              "no se publica automáticamente."}, 201)
            if p == "/api/admin/refresh":
                token = os.environ.get("ADMIN_TOKEN")
                if token and self.headers.get("X-Admin-Token") != token:
                    return self._json({"error": "Token de administración inválido"}, 403)
                if runner.state()["running"]:
                    return self._json({"error": "Ya hay una actualización en curso"}, 409)
                only = body.get("sources") if isinstance(body.get("sources"), list) else None
                t = threading.Thread(target=runner.refresh, kwargs={
                    "conn": ctx.conn, "sources": ctx.sources, "communes": ctx.communes,
                    "only": only}, daemon=True)
                t.start()
                return self._json({"started": True, "message": "Actualización iniciada. "
                                   "Consulta /api/status para ver el resultado."}, 202)
            return self._json({"error": "Ruta no encontrada"}, 404)

    return Handler


def create_server(host="127.0.0.1", port=8765, db_path=None):
    load_env()
    ctx = AppContext(db_path=db_path)
    httpd = ThreadingHTTPServer((host, port), make_handler(ctx))
    httpd.daemon_threads = True
    httpd.ctx = ctx
    return httpd


def main():
    ap = argparse.ArgumentParser(description="Eventos Región del Biobío")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    httpd = create_server(args.host, args.port, args.db)
    print("Eventos Región del Biobío en http://%s:%d  (Ctrl+C para salir)" % (args.host, args.port))
    print("Semilla cargada:", httpd.ctx.seed_result)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
