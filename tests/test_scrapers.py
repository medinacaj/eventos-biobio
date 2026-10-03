"""Scrapers probados con HTML/XML de ejemplo y un fetcher falso (sin red)."""
import unittest
from datetime import date

from tests.helpers import COMMUNES, db, memory_db
import discovery
from scrapers import deep_crawler, generic_events, rss, sitemap, ticketing, runner
from scrapers.common import FetchResult, parse_page

SRC = {"name": "Teatro Demo", "url": "https://teatro.demo.cl/", "commune": "Concepción", "source_type": "venue",
       "source_priority": 1, "official": True, "deep_crawl": True, "max_pages": 10, "max_depth": 2, "timeout": 5,
       "radar_only": False, "parser": "generic", "enabled": True}

EVENT_PAGE = """<html><head><title>Obra</title>
<meta property="og:image" content="https://teatro.demo.cl/afiche.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"TheaterEvent",
"name":"La Negra Ester","startDate":"2030-11-07T20:00:00-03:00",
"location":{"@type":"Place","name":"Sala Principal","address":{"@type":"PostalAddress","streetAddress":"Av. X 1","addressLocality":"Concepción"}},
"offers":[{"@type":"Offer","price":"8000","priceCurrency":"CLP"},{"@type":"Offer","price":"5000","priceCurrency":"CLP"}],
"eventStatus":"https://schema.org/EventScheduled"}</script></head><body><h1>La Negra Ester</h1></body></html>"""

HOME = """<html><body><a href="/cartelera/">Cartelera</a><a href="/obra-negra-ester/">La Negra Ester (evento)</a>
<a href="/contacto">Contacto</a><a href="https://otro-centro-cultural.cl/agenda">Agenda centro cultural</a>
<p>Sábado 7 de noviembre de 2030: función especial</p></body></html>"""

LISTING = """<html><head><script type="application/ld+json">[
{"@type":"Event","name":"Feria del Libro","startDate":"2030-12-01","isAccessibleForFree":true,
 "location":{"@type":"Place","name":"Plaza","address":"Plaza de Armas, Lota"}},
{"@type":"Event","name":"Show en Santiago","startDate":"2030-12-02","location":{"name":"Movistar Arena","address":"Santiago"}},
{"@type":"Event","name":"Cancelado","startDate":"2030-12-03","eventStatus":"EventCancelled","location":"Teatro, Coronel"}
]</script></head></html>"""

FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Concierto en Tomé el 20 de noviembre de 2030</title><link>https://n.cl/1</link><description>&lt;p&gt;Gratis&lt;/p&gt;</description></item>
<item><title>Nota sin fecha</title><link>https://n.cl/2</link><description>nada</description></item>
</channel></rss>"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://teatro.demo.cl/evento/obra-1/</loc></url><url><loc>https://teatro.demo.cl/quienes-somos/</loc></url></urlset>"""


def fake_fetcher(pages):
    def f(url, timeout=20, **_):
        if url in pages:
            return FetchResult(url, 200, url, pages[url], "text/html")
        return FetchResult(url, 404, error="HTTP 404")
    return f


class GenericTests(unittest.TestCase):
    def test_jsonld_event(self):
        evs, pos = generic_events.extract(EVENT_PAGE, "https://teatro.demo.cl/obra/", SRC, COMMUNES)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual((e["title"], e["date"], e["time"], e["commune"]), ("La Negra Ester", "2030-11-07", "20:00", "Concepción"))
        self.assertEqual((e["price_value"], e["price_status"], e["status"]), (5000, "paid", "Confirmado"))
        self.assertEqual(e["image_url"], "https://teatro.demo.cl/afiche.jpg")
        self.assertTrue(e["single_event_page"])

    def test_listing_filters_commune_and_status(self):
        src = dict(SRC, commune=None, parser="ticketing")
        evs, pos = ticketing.extract(LISTING, "https://tickets.cl/", src, COMMUNES)
        titles = {e["title"]: e for e in evs}
        self.assertEqual(set(titles), {"Feria del Libro", "Cancelado"})
        self.assertEqual(titles["Feria del Libro"]["commune"], "Lota")
        self.assertEqual(titles["Feria del Libro"]["price_status"], "free")
        self.assertEqual(titles["Cancelado"]["status"], "Cancelado")
        self.assertEqual(titles["Cancelado"]["price_status"], "pending")
        self.assertTrue(any(p["title"] == "Show en Santiago" for p in pos))

    def test_radar_source_never_publishes(self):
        evs, pos = generic_events.extract(EVENT_PAGE, "https://n.cl/x", dict(SRC, radar_only=True), COMMUNES)
        self.assertEqual(evs, [])
        self.assertTrue(any(p["title"] == "La Negra Ester" for p in pos))

    def test_text_only_goes_to_possible(self):
        evs, pos = generic_events.extract(HOME, "https://teatro.demo.cl/", SRC, COMMUNES, ref=date(2030, 10, 1))
        self.assertEqual(evs, [])
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["date"], "2030-11-07")

    def test_parse_page_skips_scripts(self):
        p = parse_page("<p>Hola</p><script>var x='19:30 1 de enero'</script>")
        self.assertEqual(p.blocks, ["Hola"])


class FeedSitemapTests(unittest.TestCase):
    def test_rss(self):
        pos = rss.possible_events_from_feed(FEED, {"name": "N", "url": "https://n.cl"}, COMMUNES, ref=date(2030, 10, 1))
        self.assertEqual(len(pos), 1)
        self.assertEqual((pos[0]["date"], pos[0]["commune"]), ("2030-11-20", "Tomé"))

    def test_sitemap(self):
        urls, subs = sitemap.parse_sitemap(SITEMAP)
        self.assertEqual(len(urls), 2)
        f = fake_fetcher({"https://teatro.demo.cl/sitemap.xml": SITEMAP})
        self.assertEqual(sitemap.event_urls_from_sitemap("https://teatro.demo.cl/", fetcher=f),
                         ["https://teatro.demo.cl/evento/obra-1/"])

    def test_bad_xml(self):
        self.assertEqual(rss.parse_feed("<no"), [])
        self.assertEqual(sitemap.parse_sitemap("<no"), ([], []))


class CrawlTests(unittest.TestCase):
    PAGES = {"https://teatro.demo.cl/": HOME, "https://teatro.demo.cl/obra-negra-ester/": EVENT_PAGE,
             "https://teatro.demo.cl/cartelera/": "<html><body>Sin eventos</body></html>"}

    def test_crawl(self):
        res = deep_crawler.crawl(SRC, COMMUNES, fetcher=fake_fetcher(self.PAGES), ref=date(2030, 10, 1))
        self.assertIsNone(res.error)
        self.assertEqual(res.pages, 3)
        self.assertEqual([e["title"] for e in res.events], ["La Negra Ester"])
        self.assertEqual(res.candidates[0][1], "otro-centro-cultural.cl")

    def test_crawl_unreachable_start(self):
        res = deep_crawler.crawl(SRC, COMMUNES, fetcher=fake_fetcher({}))
        self.assertEqual(res.error, "HTTP 404")
        self.assertEqual(res.events, [])

    def test_runner_end_to_end_records_real_counts(self):
        conn = memory_db()
        bad = dict(SRC, name="Caída", url="https://caida.cl/")
        summary = runner.refresh(conn, sources=[SRC, bad], communes=COMMUNES,
                                 fetcher=fake_fetcher(self.PAGES), max_workers=2)
        self.assertEqual((summary["sources_attempted"], summary["sources_ok"], summary["sources_failed"]), (2, 1, 1))
        self.assertEqual(summary["events_inserted"], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT origin FROM events").fetchone()[0], "crawl")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM source_candidates").fetchone()[0], 1)
        # segunda corrida: el mismo evento no se duplica
        summary2 = runner.refresh(conn, sources=[SRC], communes=COMMUNES, fetcher=fake_fetcher(self.PAGES))
        self.assertEqual(summary2["events_inserted"], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)


class ConfigTests(unittest.TestCase):
    def test_communes(self):
        self.assertEqual(len(COMMUNES), 33)
        by = {}
        for c in COMMUNES:
            by[c["province"]] = by.get(c["province"], 0) + 1
            self.assertTrue(-39 < c["lat"] < -36 and -74 < c["lon"] < -71, c["name"])
        self.assertEqual(by, {"Concepción": 12, "Arauco": 7, "Biobío": 14})

    def test_sources_valid_and_honest(self):
        sources = discovery.load_sources()
        self.assertEqual(discovery.validate_sources(sources, COMMUNES), [])
        insta = [s for s in sources if "instagram" in s["url"]]
        self.assertTrue(all(not s["enabled"] for s in insta))
        for s in sources:
            self.assertIsInstance(s["verified_live"], bool)
            self.assertTrue(s["notes"])


if __name__ == "__main__":
    unittest.main()
