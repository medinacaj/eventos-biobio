"""actualizar.py con fetcher falso y archivos temporales (sin red)."""
import json
import os
import shutil
import tempfile
import unittest

from tests.helpers import COMMUNES, ROOT, db, memory_db
import actualizar
from tests.test_scrapers import EVENT_PAGE, HOME, fake_fetcher

PAGES = {"https://teatro.demo.cl/": HOME, "https://teatro.demo.cl/obra-negra-ester/": EVENT_PAGE}
SOURCES = {"_notes": "", "sources": [
    {"name": "Teatro Demo", "url": "https://teatro.demo.cl/", "enabled": True, "source_type": "venue",
     "source_priority": 1, "official": True, "deep_crawl": True, "max_pages": 5, "max_depth": 1, "timeout": 5,
     "radar_only": False, "commune": "Concepción", "province": "Concepción", "parser": "generic",
     "verified_live": False, "notes": "No verificada en vivo: algo; el scraper NUNCA se ejecutó contra esta URL. Nota propia."},
    {"name": "Caída", "url": "https://caida.cl/", "enabled": True, "source_type": "municipal",
     "source_priority": 1, "official": True, "deep_crawl": False, "max_pages": 1, "max_depth": 0, "timeout": 5,
     "radar_only": False, "commune": "Lota", "province": "Concepción", "parser": "generic",
     "verified_live": True, "notes": "Nota de Lota."},
    {"name": "Apagada", "url": "https://x.cl/", "enabled": False, "source_type": "media", "source_priority": 3,
     "official": False, "deep_crawl": False, "max_pages": 1, "max_depth": 0, "timeout": 5, "radar_only": True,
     "commune": None, "province": None, "parser": "generic", "verified_live": False, "notes": "Off."}]}


class ActualizarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.crawled = os.path.join(self.tmp, "crawled.json")
        self.sources = os.path.join(self.tmp, "sources.json")
        with open(self.sources, "w", encoding="utf-8") as f:
            json.dump(SOURCES, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_once(self):
        return actualizar.main([], fetcher=fake_fetcher(PAGES), crawled_path=self.crawled,
                               sources_path=self.sources)

    def test_snapshot_and_sources_updated_from_real_responses(self):
        self.assertEqual(self.run_once(), 0)
        with open(self.crawled, encoding="utf-8") as f:
            snap = json.load(f)
        self.assertEqual([e["title"] for e in snap["events"]], ["La Negra Ester"])
        self.assertEqual({r["source_name"]: r["ok"] for r in snap["runs"]}, {"Teatro Demo": 1, "Caída": 0})
        with open(self.sources, encoding="utf-8") as f:
            src = {s["name"]: s for s in json.load(f)["sources"]}
        self.assertTrue(src["Teatro Demo"]["verified_live"])
        self.assertTrue(src["Teatro Demo"]["notes"].startswith("Verificada en vivo el "))
        self.assertTrue(src["Teatro Demo"]["notes"].endswith("Nota propia."))
        self.assertNotIn("NUNCA", src["Teatro Demo"]["notes"])
        self.assertFalse(src["Caída"]["verified_live"])  # antes true: ahora refleja la falla real
        self.assertIn("falló", src["Caída"]["notes"])
        self.assertEqual(src["Apagada"]["notes"], "Off.")
        self.assertNotIn("last_live_check", src["Apagada"])

    def test_second_run_no_duplicates_and_notes_not_stacked(self):
        self.run_once()
        self.run_once()
        with open(self.crawled, encoding="utf-8") as f:
            snap = json.load(f)
        self.assertEqual(len(snap["events"]), 1)
        self.assertEqual(snap["summary"]["events_inserted"], 0)
        with open(self.sources, encoding="utf-8") as f:
            src = {s["name"]: s for s in json.load(f)["sources"]}
        self.assertEqual(src["Teatro Demo"]["notes"].count("Verificada en vivo"), 1)
        self.assertEqual(src["Caída"]["notes"].count("falló"), 1)

    def test_app_loads_snapshot_idempotently(self):
        self.run_once()
        conn = memory_db()
        r1 = db.load_crawled(conn, self.crawled, COMMUNES)
        r2 = db.load_crawled(conn, self.crawled, COMMUNES)
        self.assertEqual((r1["inserted"], r2["inserted"]), (1, 0))
        self.assertEqual(r2["runs"], 0)
        st = db.compute_status(conn, [], COMMUNES)
        self.assertEqual((st["events_crawled"], st["sources_with_successful_run"]), (1, 1))

    def test_missing_snapshot_is_fine(self):
        r = db.load_crawled(memory_db(), os.path.join(self.tmp, "no.json"), COMMUNES)
        self.assertEqual(r["inserted"], 0)

    def test_repo_snapshot_valid_if_present(self):
        path = os.path.join(ROOT, "data", "crawled_events.json")
        if os.path.exists(path):
            db.load_crawled(memory_db(), path, COMMUNES)


if __name__ == "__main__":
    unittest.main()
