"""Exige una corrida real satisfactoria antes de versionar datos del rastreador.

El éxito de una petición HTTP NO garantiza que la fuente publique eventos.
No inventa eventos ni cubre comunas sin evidencia.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path


def check(snapshot_path, communes_path):
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    communes = json.loads(Path(communes_path).read_text(encoding="utf-8"))
    summary = snap.get("summary") or {}
    runs = snap.get("runs") or []
    ok = [r for r in runs if r.get("ok") and isinstance(r.get("http_status"), int)
          and 200 <= r["http_status"] < 300]
    events = snap.get("events") or []
    valid = {s["source_name"] for s in ok}
    if not ok or not valid:
        raise ValueError("Ninguna fuente respondió con HTTP 2xx verificable; no publicar ni reemplazar datos")
    if summary.get("sources_ok") != len(ok):
        raise ValueError("Resumen de fuentes OK inconsistente con ejecuciones de HTTP 2xx")
    if summary.get("sources_attempted", 0) != len(runs):
        raise ValueError("Cantidad de fuentes intentadas distinta a corridas individuales")
    if not isinstance(events, list):
        raise ValueError("events debe ser lista")
    names = set()
    if isinstance(communes, dict):
        # config/communes.json puede tener clave 'communes'.
        content = communes.get("communes", [])
    else:
        content = communes
    for c in content:
        if isinstance(c, dict):
            names.add(c.get("name") or c.get("nombre") or c.get("commune"))
        elif isinstance(c, str):
            names.add(c)
    coverage = Counter(e.get("commune") for e in events if isinstance(e, dict))
    covered = len({name for name in coverage if name in names})
    lines = [
        "## Rastreo real de Eventos Biobío",
        f"- Fuentes intentadas: **{len(runs)}**",
        f"- Respuestas HTTP 2xx verificadas: **{len(ok)}**",
        f"- Fuentes fallidas: **{summary.get('sources_failed', 0)}**",
        f"- Eventos en snapshot: **{len(events)}**",
        f"- Candidatos derivados a revisión editorial: **{summary.get('quarantined_candidates', 0)}**",
        f"- Comunas con eventos rastreados: **{covered}/{len(names)}**",
        "",
        "Una respuesta HTTP exitosa no implica que se extrajeran eventos válidos.",
        "Ninguna comuna se considera cubierta sin un evento extraído.",
    ]
    report = "\n".join(lines) + "\n"
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf8") as out:
            out.write(report)
    return report


if __name__ == "__main__":
    try:
        check(sys.argv[1], sys.argv[2])
    except (OSError, ValueError, IndexError, KeyError, TypeError) as e:
        print(f"Rastreo rechazado: {e}", file=sys.stderr)
        sys.exit(1)
