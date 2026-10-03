"""Lectura de feeds RSS/Atom. Los ítems se guardan como POSIBLES eventos."""
import re
import xml.etree.ElementTree as ET
from datetime import date

import metadata

ATOM = "{http://www.w3.org/2005/Atom}"


def _strip_html(s):
    return " ".join(re.sub(r"<[^>]+>", " ", s or "").split())


def parse_feed(xml_text):
    """Devuelve lista de dicts {title, link, summary, published}."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):
        items.append({"title": (it.findtext("title") or "").strip(),
                      "link": (it.findtext("link") or "").strip(),
                      "summary": _strip_html(it.findtext("description")),
                      "published": it.findtext("pubDate")})
    for it in root.iter(ATOM + "entry"):
        link = it.find(ATOM + "link")
        items.append({"title": (it.findtext(ATOM + "title") or "").strip(),
                      "link": link.get("href") if link is not None else "",
                      "summary": _strip_html(it.findtext(ATOM + "summary") or it.findtext(ATOM + "content")),
                      "published": it.findtext(ATOM + "updated")})
    return items


def possible_events_from_feed(xml_text, source, communes, ref=None):
    ref = ref or date.today()
    names = [c["name"] for c in communes]
    out = []
    for it in parse_feed(xml_text):
        text = it["title"] + ". " + it["summary"]
        d = metadata.parse_date(text, ref)
        if not d or d < ref.isoformat():
            continue
        out.append({"title": it["title"][:300], "date": d,
                    "commune": metadata.detect_commune(text, names) or source.get("commune"),
                    "source": source["name"], "source_url": it["link"] or source["url"],
                    "raw_text": it["summary"][:2000], "reason": "Ítem RSS con fecha futura"})
    return out
