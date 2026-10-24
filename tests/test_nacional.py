"""Modo nacional: comunas de Chile, fuentes fuera del Biobío y región por evento (sin red)."""
import json
import os
import shutil
import tempfile
import unittest

from tests.helpers import COMMUNES, discovery
import actualizar
from scrapers import generic_events
from tests.test_scrapers import fake_fetcher

CHILE = discovery.load_communes(discovery.CHILE_COMMUNES_PATH)

VALPO_PAGE = """<html><head><script type="application/ld+json">{"@context":"https://schema.org",
"@type":"Event","name":"Concierto en el Parque","startDate":"2030-11-14T19:00:00-03:00",
"location":{"@type":"Place","name":"Pabellón","address":{"@type":"PostalAddress",
"streetAddress":"Calle Cárcel 471","addressLocality":"Valparaíso"}}}</script></head>
<body><h1>Concierto en el Parque</h1></body></html>"""
HOME = '<html><body><a href="/evento/concierto/">Concierto en el Parque (evento)</a></body></html>'
SOURCES = {"_notes": "", "sources": [
    {"name": "Parque Demo", "url": "https://parque.demo.cl/", "enabled": True, "source_type": "venue",
     "source_priority": 1, "official": True, "deep_crawl": True, "max_pages": 5, "max_depth": 1,
     "timeout": 5, "radar_only": False, "commune": "Valparaíso", "province": "Valparaíso",
     "region": "Valparaíso", "parser": "generic", "verified_live": False, "notes": "Prueba."}]}


class ChileCommunesTests(unittest.TestCase):
    def test_full_country_with_unique_names(self):
        self.assertEqual(len(CHILE), 346)
        self.assertEqual(len({c["name"] for c in CHILE}), 346)
        self.assertEqual(len({c["region"] for c in CHILE}), 16)

    def test_biobio_matches_regional_list_and_coordinates(self):
        biobio = {c["name"]: c for c in CHILE if c["region"] == "Biobío"}
        self.assertEqual(set(biobio), {c["name"] for c in COMMUNES})
        for c in COMMUNES:
            self.assertEqual((biobio[c["name"]]["lat"], biobio[c["name"]]["lon"]), (c["lat"], c["lon"]))

    def test_national_sources_are_valid_and_consistent(self):
        sources = discovery.load_sources(discovery.NATIONAL_SOURCES_PATH)
        self.assertEqual(discovery.validate_sources(sources, CHILE), [])
        by_name = {c["name"]: c for c in CHILE}
        for s in sources:
            self.assertTrue(s["url"].startswith("https://"), s["name"])
            self.assertIn("url_evidence", s)
            if s["commune"]:
                self.assertEqual(by_name[s["commune"]]["region"], s["region"], s["name"])
            self.assertFalse(s["verified_live"], "solo actualizar.py puede marcar verified_live")


class LocalityTests(unittest.TestCase):
    def test_address_locality_wins_over_venue_name(self):
        page = """<script type="application/ld+json">{"@type":"Event","name":"Acto","startDate":"2030-09-18",
        "location":{"name":"Plaza de la Independencia","address":{"addressLocality":"Concepción"}}}</script>"""
        src = {"name": "Agregador", "commune": None, "source_type": "aggregator"}
        events, _ = generic_events.events_from_jsonld(page, "https://a.cl/", src, CHILE)
        self.assertEqual(events[0]["commune"], "Concepción")


class NationalRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "national.json")
        self.sources = os.path.join(self.tmp, "sources.json")
        with open(self.sources, "w", encoding="utf-8") as f:
            json.dump(SOURCES, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_events_carry_region_and_sources_get_verified(self):
        pages = {"https://parque.demo.cl/": HOME, "https://parque.demo.cl/evento/concierto/": VALPO_PAGE}
        code = actualizar.main(["--nacional"], fetcher=fake_fetcher(pages), crawled_path=self.out,
                               sources_path=self.sources)
        self.assertEqual(code, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("--nacional", data["_notes"])
        [event] = data["events"]
        self.assertEqual((event["title"], event["commune"], event["region"]),
                         ("Concierto en el Parque", "Valparaíso", "Valparaíso"))
        with open(self.sources, encoding="utf-8") as f:
            source = json.load(f)["sources"][0]
        self.assertTrue(source["verified_live"])


if __name__ == "__main__":
    unittest.main()
