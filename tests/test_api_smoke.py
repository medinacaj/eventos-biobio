"""Smoke test end-to-end: levanta el servidor real en un puerto local y prueba la API con urllib."""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from tests.helpers import ROOT  # noqa: F401
os.environ["EVENTOS_QUIET"] = "1"
import app  # noqa: E402
import launcher  # noqa: E402


class ApiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ.pop("ADMIN_TOKEN", None)
        port = launcher.free_port(18765)
        cls.httpd = app.create_server("127.0.0.1", port, db_path=os.path.join(cls.tmp, "t.db"))
        cls.base = "http://127.0.0.1:%d" % port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        assert launcher.wait_health(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.ctx.conn.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.status, r.headers.get("Content-Type"), r.read()

    def get_json(self, path):
        s, _, body = self.get(path)
        return s, json.loads(body)

    def post(self, path, data):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health(self):
        s, d = self.get_json("/health")
        self.assertEqual((s, d["ok"]), (200, True))

    def test_events_and_filters(self):
        s, d = self.get_json("/api/events")
        self.assertEqual(s, 200)
        self.assertEqual(d["count"], len(d["events"]))
        seed_n = d["count"]
        with open(os.path.join(ROOT, "data", "seed_events.json"), encoding="utf-8") as f:
            self.assertEqual(seed_n, len(json.load(f)["events"]))
        _, d2 = self.get_json("/api/events?commune=Tom%C3%A9")
        self.assertTrue(all(e["commune"] == "Tomé" for e in d2["events"]))
        _, d3 = self.get_json("/api/events?price_status=free&category=Cultura")
        self.assertTrue(all(e["price_status"] == "free" for e in d3["events"]))
        _, d4 = self.get_json("/api/events?date_from=2099-01-01")
        self.assertEqual(d4["count"], 0)
        s, _ = self.get_json_err("/api/events?date_from=no-es-fecha")
        self.assertEqual(s, 400)
        if d["events"]:
            s, ev = self.get_json("/api/events/%d" % d["events"][0]["id"])
            self.assertIn("changes", ev)
        s, _ = self.get_json_err("/api/events/999999")
        self.assertEqual(s, 404)

    def get_json_err(self, path):
        try:
            return self.get_json(path)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_status_and_coverage_are_live(self):
        _, st = self.get_json("/api/status")
        _, ev = self.get_json("/api/events")
        self.assertEqual(st["events_total"], ev["count"])
        self.assertEqual(st["communes_total"], 33)
        self.assertEqual(st["sources_verified_live"], 0)
        _, cov = self.get_json("/api/coverage")
        self.assertEqual(len(cov["communes"]), 33)
        self.assertEqual(sum(c["events_total"] for c in cov["communes"]), st["events_total"])

    def test_lists(self):
        for path, key in (("/api/communes", "communes"), ("/api/sources", "sources"),
                          ("/api/possible-events", "possible_events"), ("/api/source-candidates", "source_candidates")):
            s, d = self.get_json(path)
            self.assertEqual(s, 200)
            self.assertIn(key, d)
        _, d = self.get_json("/api/communes")
        self.assertEqual(len(d["communes"]), 33)

    def test_submission_flow(self):
        _, before = self.get_json("/api/events")
        s, d = self.post("/api/submissions", {"title": "Feria vecinal de prueba", "date": "2030-01-15",
                                              "commune": "Lebu", "time": "10:00"})
        self.assertEqual((s, d["status"]), (201, "Pendiente de revisión"))
        _, after = self.get_json("/api/events")
        self.assertEqual(before["count"], after["count"])  # nunca se publica automáticamente
        s, d = self.post("/api/submissions", {"title": "x", "date": "mañana", "commune": "Santiago", "time": "25:00"})
        self.assertEqual(s, 400)
        self.assertGreaterEqual(len(d["errors"]), 3)

    def test_static(self):
        s, ctype, body = self.get("/")
        self.assertEqual(s, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"Eventos Regi", body)
        s, ctype, _ = self.get("/app.js")
        self.assertIn("javascript", ctype)
        s, _ = self.get_json_err("/../app.py")
        self.assertEqual(s, 404)

    def test_unknown_api(self):
        s, _ = self.get_json_err("/api/nada")
        self.assertEqual(s, 404)


if __name__ == "__main__":
    unittest.main()
