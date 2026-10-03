"""Extracción de la imagen oficial publicada por la propia fuente.

Solo se usan imágenes que la página declara: og:image, twitter:image o la
propiedad "image" de su JSON-LD. Nunca se generan imágenes.
"""
import json
from html.parser import HTMLParser
from urllib.parse import urljoin

_SKIP_HINTS = ("favicon", "logo", "sprite", "placeholder", "default-share", "blank.")


class _ImageMetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.og = []
        self.twitter = []
        self.jsonld_blocks = []
        self._in_jsonld = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content", "").strip()
            if not content:
                return
            if key in ("og:image", "og:image:url", "og:image:secure_url"):
                self.og.append(content)
            elif key in ("twitter:image", "twitter:image:src"):
                self.twitter.append(content)
        elif tag == "script" and "ld+json" in a.get("type", "").lower():
            self._in_jsonld = True
            self._buf = []

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld_blocks.append("".join(self._buf))


def parse_jsonld_blocks(blocks):
    """Devuelve una lista plana de objetos JSON-LD (expande @graph y listas)."""
    out = []

    def walk(obj):
        if isinstance(obj, list):
            for o in obj:
                walk(o)
        elif isinstance(obj, dict):
            if "@graph" in obj:
                walk(obj["@graph"])
            out.append(obj)

    for raw in blocks:
        raw = raw.strip()
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except ValueError:
            continue
    return out


def _jsonld_image(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _jsonld_image(value[0])
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    return None


def extract_official_image(html, base_url=""):
    """Devuelve la URL absoluta de la imagen oficial o None.

    Prioridad: JSON-LD de un Event > og:image > twitter:image > JSON-LD genérico.
    Se descartan URLs que parecen logos/favicons.
    """
    if not html:
        return None
    p = _ImageMetaParser()
    try:
        p.feed(html)
    except Exception:  # HTML muy roto: no inventamos nada
        return None
    objs = parse_jsonld_blocks(p.jsonld_blocks)
    event_imgs, other_imgs = [], []
    for o in objs:
        img = _jsonld_image(o.get("image"))
        if img:
            types = o.get("@type")
            types = types if isinstance(types, list) else [types]
            (event_imgs if any(str(t).endswith("Event") for t in types) else other_imgs).append(img)
    for url in event_imgs + p.og + p.twitter + other_imgs:
        url = (url or "").strip()
        if not url or url.startswith("data:"):
            continue
        if any(h in url.lower() for h in _SKIP_HINTS):
            continue
        absolute = urljoin(base_url, url)
        if absolute.startswith(("http://", "https://")):
            return absolute
    return None
