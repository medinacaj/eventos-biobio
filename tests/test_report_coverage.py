import json
import tempfile
import unittest
from pathlib import Path
from scripts.report_coverage import report

class CoverageReportTests(unittest.TestCase):
    def test_published_coverage_excludes_unverified_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/"snapshot.json").write_text(json.dumps({
                "generated_at":"2026-10-18",
                "events":[{"commune":"Concepción"}],
                "possible_events":[{"commune":"Florida"},{"commune":"Florida"}],
                "runs":[{"source_name":"Municipal", "ok":1, "http_status":200}]
            }),encoding="utf8")
            (p/"communes.json").write_text(json.dumps({
                "communes":[{"name":"Concepción"},{"name":"Florida"}]
            }),encoding="utf8")
            (p/"sources.json").write_text(json.dumps({
                "sources":[{"name":"Municipal","commune":"Concepción","enabled":True}]
            }),encoding="utf8")
            result=report(p/"snapshot.json",p/"communes.json",p/"sources.json")
            self.assertIn("Cobertura publicada: 1/2 comunas",result)
            self.assertIn("| Florida | 0 | 0 | 0 | 2 |",result)

if __name__=="__main__":
    unittest.main()
