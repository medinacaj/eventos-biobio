"""Extractor genérico de eventos desde HTML.

Política de publicación:
- Solo datos ESTRUCTURADOS (JSON-LD schema.org/Event) con título, fecha y
  comuna identificables se convierten en eventos publicados.
- Todo lo demás (texto con fechas, notas de prensa, listados sin estructura)
  se guarda como "posible evento" para revisión humana. Nunca se completa un
  dato faltante con un valor supuesto.
"""
from datetime import date, timedelta
from urllib.parse import urljoin

import metadata
from images import extract_official_image, parse_jsonld_blocks, _ImageMetaParser
from scrapers.common import parse_page

STATUS_MAP = {
    "eventcancelled": "Cancelado",
    "eventrescheduled": "Reprogramado",
    "eventpostponed": "Reprogramado",
    "eventscheduled": "Confirmado",
    "eventmovedonline": "Por confirmar",
}


def _jsonld_objects(html):
    p = _ImageMetaParser()
    try:
        p.feed(html or "")
    except Exception:
        return []
    return parse_jsonld_blocks(p.jsonld_blocks)


def _is_event(obj):
    t = obj.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.endswith("Event") for x in types)


def _text(v):
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("name") or v.get("@value") or ""
    if isinstance(v, list):
        return " ".join(_text(x) for x in v)
    return ""


def _location(obj):
    loc = obj.get("location")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, str):
        return loc, "", loc
    if not isinstance(loc, dict):
        return "", "", ""
    venue = loc.get("name") or ""
    addr = loc.get("address")
    if isinstance(addr, dict):
        parts = [addr.get("streetAddress"), addr.get("addressLocality"), addr.get("addressRegion")]
        address = ", ".join(p for p in parts if p)
        locality = addr.get("addressLocality") or ""
    else:
        address = addr or ""
        locality = ""
    return venue, address, " ".join([venue, address, locality])


def _price(obj):
    if obj.get("isAccessibleForFree") in (True, "true", "True"):
        return 0, "free"
    offers = obj.get("offers")
    offers = offers if isinstance(offers, list) else [offers] if offers else []
    prices = []
    for o in offers:
        if not isinstance(o, dict):
            continue
        for k in ("price", "lowPrice"):
            v = o.get(k)
            try:
                if v not in (None, ""):
                    prices.append(float(str(v).replace(",", ".")))
            except ValueError:
                pass
        if o.get("availability", "").lower().endswith("soldout"):
            return (int(min(prices)) if prices else None), "paid"
    if prices:
        lo = min(prices)
        return (0, "free") if lo == 0 else (int(lo), "paid")
    return None, "pending"


def _iso_parts(value):
    """'2026-10-17T19:30:00-03:00' -> ('2026-10-17', '19:30')."""
    if not value or not isinstance(value, str):
        return None, None
    d = value[:10]
    if len(d) == 10 and d[4] == "-" and d[7] == "-":
        t = value[11:16] if len(value) >= 16 and value[10] in "T " else None
        if t == "00:00" and len(value) <= 19:
            t = None  # medianoche sin zona suele significar "sin hora"
        return d, t
    return metadata.parse_date(value), metadata.parse_time(value)


def events_from_jsonld(html, page_url, source, communes):
    """Devuelve (eventos, posibles) a partir del JSON-LD de la página."""
    names = [c["name"] for c in communes]
    events, possibles = [], []
    objs = [o for o in _jsonld_objects(html) if _is_event(o)]
    for o in objs:
        title = " ".join(_text(o.get("name")).split())
        d, t = _iso_parts(o.get("startDate"))
        ed, et = _iso_parts(o.get("endDate"))
        venue, address, loc_text = _location(o)
        commune = metadata.detect_commune(loc_text, names) or source.get("commune")
        url = urljoin(page_url, o.get("url") or page_url)
        if not title or not d:
            continue
        if not commune:
            possibles.append({"title": title, "date": d, "commune": None, "source": source["name"],
                              "source_url": url, "raw_text": loc_text,
                              "reason": "Evento estructurado sin comuna del Biobío identificable"})
            continue
        price_value, price_status = _price(o)
        status_raw = str(o.get("eventStatus") or "").rsplit("/", 1)[-1].lower()
        img = o.get("image")
        img = img[0] if isinstance(img, list) and img else img
        img = img.get("url") if isinstance(img, dict) else img
        desc = " ".join(_text(o.get("description")).split())[:1200]
        events.append({
            "title": title, "description": desc or None, "date": d,
            "end_date": ed if ed and ed != d else None, "time": t,
            "end_time": et if ed == d else None,
            "venue": venue or None, "address": address or None, "commune": commune,
            "category": metadata.guess_category(title + " " + desc),
            "price_value": price_value, "price_status": price_status,
            "status": STATUS_MAP.get(status_raw, "Confirmado" if t else "Por confirmar"),
            "source": source["name"], "source_url": url,
            "source_type": source.get("source_type"), "source_priority": source.get("source_priority", 3),
            "official": bool(source.get("official")),
            "image_url": urljoin(page_url, img) if isinstance(img, str) and img else None,
            "single_event_page": len(objs) == 1,
        })
    if len(events) == 1 and not events[0]["image_url"]:
        events[0]["image_url"] = extract_official_image(html, page_url)
    return events, possibles


def possible_events_from_text(html, page_url, source, communes, ref=None, horizon_days=240):
    """Heurística conservadora: bloques de texto que contienen una fecha futura.

    Solo produce *posibles* eventos (pendientes de revisión), nunca eventos
    publicados.
    """
    ref = ref or date.today()
    names = [c["name"] for c in communes]
    page = parse_page(html)
    title_hint = page.headings[0] if page.headings else page.title.strip()
    out, seen = [], set()
    limit = ref + timedelta(days=horizon_days)
    for block in page.blocks:
        if len(block) < 12 or len(block) > 600:
            continue
        d = metadata.parse_date(block, ref)
        if not d or not (ref.isoformat() <= d <= limit.isoformat()):
            continue
        title = block if len(block) <= 140 else (title_hint or block[:140])
        key = (metadata.normalize(title), d)
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "date": d,
                    "commune": metadata.detect_commune(block, names) or source.get("commune"),
                    "source": source["name"], "source_url": page_url, "raw_text": block,
                    "reason": "Texto con fecha futura sin datos estructurados"})
        if len(out) >= 30:
            break
    return out


def extract(html, page_url, source, communes, ref=None):
    events, possibles = events_from_jsonld(html, page_url, source, communes)
    if source.get("radar_only"):
        # Fuentes radar (prensa, catálogos nacionales sin filtro): nada se publica directo.
        for e in events:
            possibles.append({"title": e["title"], "date": e["date"], "commune": e["commune"],
                              "source": e["source"], "source_url": e["source_url"],
                              "raw_text": e.get("venue") or "", "reason": "Fuente radar: requiere revisión"})
        events = []
    if not events:
        possibles.extend(possible_events_from_text(html, page_url, source, communes, ref))
    return events, possibles
