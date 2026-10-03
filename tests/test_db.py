import json
import unittest

from tests.helpers import COMMUNES, db, ev, memory_db


class SchemaTests(unittest.TestCase):
    def test_tables_exist(self):
        conn = memory_db()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("events", "event_changes", "source_candidates", "possible_events", "submissions", "source_runs"):
            self.assertIn(t, names)

    def test_events_columns(self):
        conn = memory_db()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
        required = """id title description date end_date time end_time venue address commune province category
        tags audience access price_value price_status status source source_url source_type source_priority official
        sources_json image_url image_official latitude longitude location_accuracy discovered_at updated_at
        changed_at created_at dedupe_key""".split()
        self.assertEqual(set(required) - cols, set())

    def test_insert_and_read(self):
        conn = memory_db()
        eid, action = db.upsert_event(conn, ev(tags=["música"]), COMMUNES)
        self.assertEqual(action, "inserted")
        got = db.get_event(conn, eid)
        self.assertEqual(got["title"], "Concierto de prueba")
        self.assertEqual(got["province"], "Concepción")
        self.assertEqual(got["tags"], ["música"])
        self.assertEqual(got["location_accuracy"], "comuna")
        self.assertEqual(len(got["sources"]), 1)
        self.assertEqual(got["changes"], [])

    def test_missing_fields_rejected(self):
        conn = memory_db()
        with self.assertRaises(ValueError):
            db.upsert_event(conn, ev(date=None), COMMUNES)
        with self.assertRaises(ValueError):
            db.upsert_event(conn, ev(commune=""), COMMUNES)

    def test_invalid_category_and_status_normalized(self):
        conn = memory_db()
        eid, _ = db.upsert_event(conn, ev(category="Rarísima", status="Inventado", price_status="x"), COMMUNES)
        got = db.get_event(conn, eid)
        self.assertIn(got["category"], db.CATEGORIES)
        self.assertIn(got["status"], db.STATUSES)
        self.assertEqual(got["price_status"], "pending")

    def test_query_filters(self):
        conn = memory_db()
        db.upsert_event(conn, ev(title="Feria costumbrista", category="Comunidad", commune="Yumbel",
                                 price_status="free", price_value=0, source_url="https://y/1"), COMMUNES)
        db.upsert_event(conn, ev(title="Seminario pyme", category="Empresarial", date="2030-06-01",
                                 source_url="https://c/2"), COMMUNES)
        self.assertEqual(len(db.query_events(conn, commune="Yumbel")), 1)
        self.assertEqual(len(db.query_events(conn, category="Empresarial")), 1)
        self.assertEqual(len(db.query_events(conn, price_status="free")), 1)
        self.assertEqual(len(db.query_events(conn, date_from="2030-05-11")), 1)
        self.assertEqual(len(db.query_events(conn, date_to="2030-05-10")), 1)
        self.assertEqual(len(db.query_events(conn, q="costumbrista")), 1)
        self.assertEqual(len(db.query_events(conn, q="COSTUMBRISTA yumbel".split()[0])), 1)

    def test_status_and_coverage_computed_from_db(self):
        conn = memory_db()
        sources = [{"name": "S1", "url": "https://s1", "commune": "Lota", "enabled": True, "verified_live": False}]
        st = db.compute_status(conn, sources, COMMUNES)
        self.assertEqual(st["events_total"], 0)
        self.assertEqual(st["sources_verified_live"], 0)
        db.upsert_event(conn, ev(commune="Lota", date="2099-01-01"), COMMUNES)
        db.upsert_event(conn, ev(title="Algo pasado", commune="Lota", date="2000-01-01", source_url="https://o"), COMMUNES)
        st = db.compute_status(conn, sources, COMMUNES)
        self.assertEqual((st["events_total"], st["events_current"], st["events_past"]), (2, 1, 1))
        self.assertEqual(st["communes_with_events"], 1)
        cov = db.compute_coverage(conn, sources, COMMUNES)
        self.assertEqual(len(cov["communes"]), 33)
        lota = [c for c in cov["communes"] if c["commune"] == "Lota"][0]
        self.assertEqual((lota["events_total"], lota["events_current"], lota["sources_configured"]), (2, 1, 1))

    def test_submission_pending(self):
        conn = memory_db()
        sid = db.add_submission(conn, {"title": "Mi evento", "date": "2030-01-01", "commune": "Lebu"})
        row = conn.execute("SELECT status FROM submissions WHERE id=?", (sid,)).fetchone()
        self.assertEqual(row[0], "Pendiente de revisión")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_seed_file_loads_and_is_idempotent(self):
        conn = memory_db()
        r1 = db.load_seed(conn, db.os.path.join(db.BASE_DIR, "data", "seed_events.json"), COMMUNES)
        r2 = db.load_seed(conn, db.os.path.join(db.BASE_DIR, "data", "seed_events.json"), COMMUNES)
        self.assertEqual(r1["merged"] + r1["unchanged"], 0)
        self.assertEqual(r2["inserted"], 0)
        n = conn.execute("SELECT COUNT(*) FROM events WHERE origin='seed'").fetchone()[0]
        self.assertEqual(n, r1["inserted"])

    def test_seed_events_have_citable_sources(self):
        with open(db.os.path.join(db.BASE_DIR, "data", "seed_events.json"), encoding="utf-8") as f:
            data = json.load(f)
        for e in data["events"]:
            self.assertTrue(e["source_url"].startswith("http"), e["title"])
            self.assertTrue(e.get("verification"), e["title"])


if __name__ == "__main__":
    unittest.main()
