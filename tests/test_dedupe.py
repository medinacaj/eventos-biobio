import json
import unittest

from tests.helpers import COMMUNES, db, ev, memory_db


class DedupeTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def test_same_event_two_sources_merged_keeps_both_sources(self):
        id1, a1 = db.upsert_event(self.conn, ev(title="Concierto Sinfónico de Primavera"), COMMUNES)
        id2, a2 = db.upsert_event(self.conn, ev(title="Concierto sinfonico de primavera", time="19:30",
                                                source="Medio B", source_url="https://b.example/nota",
                                                source_priority=3, official=False), COMMUNES)
        self.assertEqual((a1, a2), ("inserted", "merged"))
        self.assertEqual(id1, id2)
        self.assertEqual(self.count(), 1)
        srcs = json.loads(self.conn.execute("SELECT sources_json FROM events").fetchone()[0])
        self.assertEqual({s["url"] for s in srcs}, {"https://a.example/ev", "https://b.example/nota"})

    def test_lower_priority_source_does_not_overwrite_official_time(self):
        eid, _ = db.upsert_event(self.conn, ev(time="19:00"), COMMUNES)
        db.upsert_event(self.conn, ev(time="19:30", source_url="https://b", source_priority=3, official=False), COMMUNES)
        self.assertEqual(db.get_event(self.conn, eid)["time"], "19:00")

    def test_guard_time_gap_over_60_minutes_not_merged(self):
        db.upsert_event(self.conn, ev(title="La Pérgola de las Flores", time="17:00"), COMMUNES)
        _, action = db.upsert_event(self.conn, ev(title="La Pérgola de las Flores", time="20:00",
                                                  source_url="https://a.example/ev2"), COMMUNES)
        self.assertEqual(action, "inserted")
        self.assertEqual(self.count(), 2)

    def test_guard_time_gap_exactly_60_minutes_merged(self):
        db.upsert_event(self.conn, ev(title="Obra Única", time="19:00"), COMMUNES)
        _, action = db.upsert_event(self.conn, ev(title="Obra Única", time="20:00",
                                                  source_url="https://other", source_priority=3), COMMUNES)
        self.assertEqual(action, "merged")

    def test_guard_same_title_same_time_from_same_url_different_function_with_gap(self):
        db.upsert_event(self.conn, ev(title="Obra X", time="12:00"), COMMUNES)
        db.upsert_event(self.conn, ev(title="Obra X", time="18:00"), COMMUNES)
        self.assertEqual(self.count(), 2)

    def test_guard_parenthesis_content_not_merged(self):
        db.upsert_event(self.conn, ev(title="Obra X", time=None), COMMUNES)
        _, action = db.upsert_event(self.conn, ev(title="Obra X (2ª función)", time=None,
                                                  source_url="https://a.example/ev-2"), COMMUNES)
        self.assertEqual(action, "inserted")
        self.assertEqual(self.count(), 2)

    def test_guard_different_parenthesis_not_merged(self):
        db.upsert_event(self.conn, ev(title="Obra X (1ª función)"), COMMUNES)
        _, action = db.upsert_event(self.conn, ev(title="Obra X (2ª función)", source_url="https://z"), COMMUNES)
        self.assertEqual(action, "inserted")

    def test_same_parenthesis_merged(self):
        db.upsert_event(self.conn, ev(title="Obra X (estreno)"), COMMUNES)
        _, action = db.upsert_event(self.conn, ev(title="Obra X (Estreno)", source_url="https://z"), COMMUNES)
        self.assertEqual(action, "merged")

    def test_different_commune_or_date_not_merged(self):
        db.upsert_event(self.conn, ev(), COMMUNES)
        db.upsert_event(self.conn, ev(commune="Talcahuano", source_url="https://t"), COMMUNES)
        db.upsert_event(self.conn, ev(date="2030-05-11", source_url="https://d"), COMMUNES)
        self.assertEqual(self.count(), 3)

    def test_dissimilar_titles_not_merged(self):
        db.upsert_event(self.conn, ev(title="Concierto de rock"), COMMUNES)
        db.upsert_event(self.conn, ev(title="Feria de emprendedores", source_url="https://f"), COMMUNES)
        self.assertEqual(self.count(), 2)

    def test_changes_recorded_with_old_new_source(self):
        eid, _ = db.upsert_event(self.conn, ev(price_status="pending", venue=None), COMMUNES)
        db.upsert_event(self.conn, ev(price_status="paid", price_value=5000, venue="Sala Principal",
                                      status="Agotado", source="Fuente A2"), COMMUNES)
        e = db.get_event(self.conn, eid)
        fields = {c["field"]: c for c in e["changes"]}
        self.assertEqual(fields["price_value"]["new_value"], "5000")
        self.assertIsNone(fields["price_value"]["old_value"])
        self.assertEqual(fields["price_status"]["old_value"], "pending")
        self.assertEqual(fields["venue"]["new_value"], "Sala Principal")
        self.assertEqual(fields["status"]["new_value"], "Agotado")
        self.assertEqual(fields["status"]["source"], "Fuente A2")
        self.assertTrue(e["changed_at"])

    def test_reschedule_from_single_event_page_records_date_change(self):
        eid, _ = db.upsert_event(self.conn, ev(single_event_page=True), COMMUNES)
        eid2, action = db.upsert_event(self.conn, ev(date="2030-05-20", single_event_page=True), COMMUNES)
        self.assertEqual((eid, action), (eid2, "merged"))
        e = db.get_event(self.conn, eid)
        self.assertEqual(e["date"], "2030-05-20")
        self.assertEqual(e["status"], "Reprogramado")
        self.assertTrue(any(c["field"] == "date" and c["old_value"] == "2030-05-10" for c in e["changes"]))

    def test_season_listing_same_url_multiple_dates_not_merged(self):
        db.upsert_event(self.conn, ev(single_event_page=False), COMMUNES)
        db.upsert_event(self.conn, ev(date="2030-05-11", single_event_page=False), COMMUNES)
        self.assertEqual(self.count(), 2)

    def test_unchanged_reupsert(self):
        db.upsert_event(self.conn, ev(), COMMUNES)
        _, action = db.upsert_event(self.conn, ev(), COMMUNES)
        self.assertEqual(action, "unchanged")

    def test_titles_match_unit(self):
        self.assertTrue(db.titles_match("Concierto Inarbolece", "concierto  inarbolece"))
        self.assertFalse(db.titles_match("Obra X", "Obra X (2ª función)"))
        self.assertTrue(db.times_compatible("19:00", None))
        self.assertFalse(db.times_compatible("10:00", "11:01"))


if __name__ == "__main__":
    unittest.main()
