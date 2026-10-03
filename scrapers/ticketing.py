"""Plataformas de ticketing.

Las plataformas nacionales listan eventos de todo Chile; solo se conservan
los que el recinto/dirección ubica en una comuna del Biobío. Usa el JSON-LD
de cada ficha (si la plataforma lo publica). Si el sitio carga sus eventos
por JavaScript, este scraper no verá nada: se reporta como 0 eventos, no se
inventa.
"""
from scrapers.generic_events import events_from_jsonld, possible_events_from_text


def extract(html, page_url, source, communes, ref=None):
    events, possibles = events_from_jsonld(html, page_url, source, communes)
    # En catálogos nacionales la comuna por defecto de la fuente no aplica.
    if not source.get("commune"):
        events = [e for e in events if e.get("commune")]
    if source.get("radar_only"):
        possibles += [{"title": e["title"], "date": e["date"], "commune": e["commune"],
                       "source": e["source"], "source_url": e["source_url"],
                       "raw_text": e.get("venue") or "", "reason": "Ticketing radar: requiere revisión"}
                      for e in events]
        events = []
    if not events and source.get("commune"):
        possibles += possible_events_from_text(html, page_url, source, communes, ref)
    return events, possibles
