"""Política conservadora de publicación para no atribuir eventos a la región equivocada.

Una URL nacional o una actividad interna no se convierte automáticamente
en evento público del Biobío solo porque su título contiene una comuna homónima.
Los descartados no se pierden: se envían a revisión manual.
"""
import re
import unicodedata


def _normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or ""))
                   if not unicodedata.combining(c)).strip().casefold()


def review_reason(event, source):
    """Motivo de cuarentena; None cuando cumple la política básica de publicación."""
    title = _normalized(event.get("title"))
    if re.match(r"^(eleccion(?:es)?|convocatoria\s+a\s+eleccion(?:es)?)\b", title):
        return "Proceso electoral/administrativo interno: verificar acceso público antes de difundir"
    if source.get("radar_only"):
        return "Fuente radar: requiere validación manual antes de publicación"
    if source.get("source_type") == "ticketing" and not source.get("commune"):
        return "Ticketera sin comuna fija: posible homónimo fuera de Biobío; revisar región y recinto"
    return None
