"""Lectura de sitemaps XML para encontrar URLs de eventos."""
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from scrapers.common import fetch, looks_like_event_url

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def parse_sitemap(xml_text):
    """Devuelve (urls, sub_sitemaps)."""
    urls, subs = [], []
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return urls, subs
    tag = root.tag.replace(NS, "")
    for loc in root.iter(NS + "loc"):
        if loc.text:
            (subs if tag == "sitemapindex" else urls).append(loc.text.strip())
    return urls, subs


def event_urls_from_sitemap(base_url, fetcher=fetch, limit=50, timeout=20, max_subs=5):
    """Busca /sitemap.xml (y sus índices) y devuelve URLs con pinta de evento."""
    found, queue, seen = [], [urljoin(base_url, "/sitemap.xml"), urljoin(base_url, "/sitemap_index.xml")], set()
    subs_read = 0
    while queue and len(found) < limit:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        res = fetcher(u, timeout=timeout)
        if not res.ok:
            continue
        urls, subs = parse_sitemap(res.text)
        for s in subs:
            if subs_read < max_subs and looks_like_event_url(s):
                queue.append(s)
                subs_read += 1
        for x in urls:
            if looks_like_event_url(x) and x not in found:
                found.append(x)
    return found[:limit]
