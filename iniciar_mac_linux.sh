#!/usr/bin/env sh
# Inicia Eventos Región del Biobío (requiere Python 3.9+; sin dependencias externas).
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else echo "No se encontró Python 3. Instálalo desde https://www.python.org/downloads/"; exit 1; fi
exec "$PY" launcher.py "$@"
