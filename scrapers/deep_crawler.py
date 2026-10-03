"""Rastreo acotado (BFS) dentro del sitio de una fuente."""
from urllib.parse import urlparse

from scrapers import generic_events, ticketing
from scrapers.common import absolute_links, fetch, looks_like_event_url, same_site
from scrapers.sitemap import event_urls_from_sitemap

PARSERS = {"generic": generic_events.extract, "ticketing": ticketing.extract}
CANDIDATE_HINTS = ("teatro", "cultura", "centro-cultural", "ticket", "entradas", "festival",
                   "agenda", "eventos", "museo", "biblioteca", "camara", "emprend")


class CrawlResult:
    def __init__(self):
        self.pages = 0
        self.events = []
        self.possibles = []
        self.candidates = []
        self.http_status = None
        self.error = None


def crawl(source, communes, fetcher=fetch, ref=None):
    res = CrawlResult()
    parser = PARSERS.get(source.get("parser") or "generic", generic_events.extract)
    start = source["url"]
    max_pages = int(source.get("max_pages") or 10) if source.get("deep_crawl") else 1
    max_depth = int(source.get("max_depth") or 1) if source.get("deep_crawl") else 0
    timeout = int(source.get("timeout") or 20)
    queue, seen = [(start, 0)], {start}
    if source.get("deep_crawl"):
        for u in event_urls_from_sitemap(start, fetcher=fetcher, limit=max_pages, timeout=timeout):
            if u not in seen and same_site(u, start):
                queue.append((u, 1))
                seen.add(u)
    while queue and res.pages < max_pages:
        url, depth = queue.pop(0)
        page = fetcher(url, timeout=timeout)
        if url == start:
            res.http_status = page.status
            if not page.ok:
                res.error = page.error or "HTTP %s" % page.status
                return res
        if not page.ok:
            continue
        res.pages += 1
        ev, pe = parser(page.text, page.final_url, source, communes, ref)
        res.events += ev
        res.possibles += pe
        for link, text in absolute_links(page.text, page.final_url):
            if same_site(link, start):
                if depth < max_depth and link not in seen and looks_like_event_url(link, text):
                    seen.add(link)
                    queue.append((link, depth + 1))
            else:
                host = urlparse(link).netloc.lower()
                low = (link + " " + text).lower()
                if host.endswith(".cl") and any(h in low for h in CANDIDATE_HINTS):
                    res.candidates.append((link, host, url, "Enlace externo con pinta de agenda/eventos"))
    return res
