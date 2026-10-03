"""Registro de fuentes: configuración (sources.json, communes.json) y
fuentes candidatas descubiertas durante el rastreo."""
import json
import os
from urllib.parse import urlparse

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(BASE_DIR, "config", "sources.json")
COMMUNES_PATH = os.path.join(BASE_DIR, "config", "communes.json")

REQUIRED_FIELDS = ("name", "url", "enabled", "source_type", "source_priority", "official",
                   "deep_crawl", "max_pages", "max_depth", "timeout", "radar_only", "commune",
                   "province", "parser", "verified_live", "notes")


def load_communes(path=COMMUNES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["communes"]


def load_sources(path=SOURCES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["sources"]


def validate_sources(sources, communes):
    """Devuelve lista de problemas (vacía si todo está bien)."""
    names = {c["name"] for c in communes}
    problems = []
    seen = set()
    for i, s in enumerate(sources):
        for f in REQUIRED_FIELDS:
            if f not in s:
                problems.append("fuente %d (%s): falta campo %s" % (i, s.get("name"), f))
        if s.get("commune") and s["commune"] not in names:
            problems.append("fuente %s: comuna desconocida %s" % (s.get("name"), s["commune"]))
        if s.get("name") in seen:
            problems.append("fuente duplicada: %s" % s.get("name"))
        seen.add(s.get("name"))
        if s.get("verified_live") and not s.get("notes"):
            problems.append("fuente %s: verified_live sin notas" % s.get("name"))
    return problems


def public_sources(sources):
    return [{k: s.get(k) for k in REQUIRED_FIELDS + ("url_evidence",)} for s in sources]


def register_candidates(conn, candidates, known_sources):
    """Guarda dominios externos aún no configurados como fuentes candidatas."""
    known = {urlparse(s["url"]).netloc.lower().removeprefix("www.") for s in known_sources}
    added = 0
    for url, host, found_on, reason in candidates:
        if host.removeprefix("www.") in known:
            continue
        added += db.add_source_candidate(conn, url, host, found_on, reason)
    return added
