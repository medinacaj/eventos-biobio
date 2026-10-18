"""Chequeo del guardarraíl: ninguna corrida inventada se publicará."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.check_snapshot import check

class SnapshotGateTests(unittest.TestCase):
    def test_accepts_one_real_http_2xx_even_if_no_events(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "communes.json").write_text(json.dumps({"communes":[{"name":"Concepción"}]}), encoding="utf8")
            (path / "snap.json").write_text(json.dumps({
                "summary":{"sources_attempted":2,"sources_ok":1,"sources_failed":1},
                "runs":[
                    {"source_name":"A","ok":1,"http_status":200},
                    {"source_name":"B","ok":0,"http_status":403}
                ],"events":[]
            }), encoding="utf8")
            result=check(path/"snap.json",path/"communes.json")
            self.assertIn("Comunas con eventos rastreados: **0/1**", result)

    def test_rejects_no_live_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            (path/"communes.json").write_text(json.dumps({"communes":[{"name":"Concepción"}]}),encoding="utf8")
            (path/"snap.json").write_text(json.dumps({
                "summary":{"sources_attempted":1,"sources_ok":0,"sources_failed":1},
                "runs":[{"source_name":"A","ok":0,"http_status":403}],"events":[]
            }),encoding="utf8")
            with self.assertRaisesRegex(ValueError,"Ninguna fuente"):
                check(path/"snap.json",path/"communes.json")

if __name__=="__main__":
    unittest.main()
