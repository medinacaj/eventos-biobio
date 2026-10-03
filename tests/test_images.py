import unittest

from tests.helpers import COMMUNES  # noqa: F401
from images import extract_official_image

OG = """<html><head><meta property="og:image" content="/wp-content/uploads/afiche.jpg">
<meta name="twitter:image" content="https://cdn.example/tw.jpg"></head><body></body></html>"""

TW_ONLY = """<head><meta name="twitter:image" content="https://cdn.example/tw.jpg"></head>"""

JSONLD = """<head><meta property="og:image" content="https://x.cl/og.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"WebPage","image":"https://x.cl/page.jpg"},
 {"@type":"MusicEvent","name":"Show","image":{"@type":"ImageObject","url":"https://x.cl/evento.jpg"}}]}</script></head>"""

LOGO_ONLY = """<head><meta property="og:image" content="https://x.cl/logo.png"></head>"""
BROKEN = """<head><script type="application/ld+json">{no es json</script>
<meta property="og:image" content="https://x.cl/ok.jpg"></head>"""


class ImageTests(unittest.TestCase):
    def test_og_image_resolved_absolute(self):
        self.assertEqual(extract_official_image(OG, "https://teatro.cl/obra/"), "https://teatro.cl/wp-content/uploads/afiche.jpg")

    def test_twitter_fallback(self):
        self.assertEqual(extract_official_image(TW_ONLY, "https://a.cl"), "https://cdn.example/tw.jpg")

    def test_jsonld_event_has_priority(self):
        self.assertEqual(extract_official_image(JSONLD, "https://x.cl"), "https://x.cl/evento.jpg")

    def test_logo_ignored_and_none_when_absent(self):
        self.assertIsNone(extract_official_image(LOGO_ONLY, "https://x.cl"))
        self.assertIsNone(extract_official_image("<html><body><img src='a.jpg'></body></html>", "https://x.cl"))
        self.assertIsNone(extract_official_image("", "https://x.cl"))

    def test_broken_jsonld_tolerated(self):
        self.assertEqual(extract_official_image(BROKEN, "https://x.cl"), "https://x.cl/ok.jpg")


if __name__ == "__main__":
    unittest.main()
