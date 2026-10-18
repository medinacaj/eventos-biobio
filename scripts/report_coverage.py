"""Genera matriz de cobertura regional basada exclusivamente en datos rastreados."""
import json
import sys
from collections import Counter
from pathlib import Path


def report(snapshot, communes, sources):
    catalog = json.loads(Path(snapshot).read_text(encoding="utf8"))
    communedata = json.loads(Path(communes).read_text(encoding="utf8"))
    sourcedata = json.loads(Path(sources).read_text(encoding="utf8"))
    names = [c["name"] for c in communedata["communes"]]
    srcs = sourcedata["sources"]
    runs = {r["source_name"]: r for r in catalog.get("runs", [])}
    counts = Counter(e.get("commune") for e in catalog.get("events", []))
    review = Counter(e.get("commune") for e in catalog.get("possible_events", []))
    lines = [
        "# Cobertura verificada · Eventos Región del Biobío",
        "",
        f"Snapshot: `{catalog.get('generated_at','sin fecha')}`",
        "",
        "Solo se consideran **eventos publicados** los incluidos en `events`. "
        "Una fuente HTTP 2xx o un candidato no equivalen a un evento verificado.",
        "",
        "| Comuna | Fuentes locales habilitadas | Fuentes HTTP 2xx | Eventos publicados | Candidatos por revisar |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in names:
        local = [s for s in srcs if s.get("commune") == name and s.get("enabled")]
        ok = sum(1 for s in local if runs.get(s["name"], {}).get("ok")
                 and 200 <= (runs.get(s["name"], {}).get("http_status") or 0) < 300)
        lines.append(f"| {name} | {len(local)} | {ok} | {counts[name]} | {review[name]} |")
    coverage = sum(bool(counts[n]) for n in names)
    lines += ["", f"**Cobertura publicada: {coverage}/{len(names)} comunas.**",
              "", "Nota: hay ticketeras y radares nacionales sin comuna confiable; "
              "sus candidatos no se publican automáticamente."]
    return "\n".join(lines)+"\n"


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("Uso: python scripts/report_coverage.py SNAPSHOT COMUNAS FUENTES SALIDA")
    result = report(sys.argv[1], sys.argv[2], sys.argv[3])
    path=Path(sys.argv[4])
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(result,encoding="utf8")
    print(result)
