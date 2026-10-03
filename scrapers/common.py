"""Utilidades HTTP y de HTML compartidas por los scrapers (solo stdlib)."""
import gzip
import re
import ssl
import time
import urllib.error
import urllib.request
import urllib.robotparser
import zlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag

USER_AGENT = ("EventosBiobioBot/1.0 (+app local de agenda regional; "
              "respeta robots.txt; contacto en README)")
MAX_BYTES = 3 * 1024 * 1024
EVENT_URL_HINTS = ("evento", "agenda", "cartelera", "actividad", "panorama", "programa",
                   "espectaculo", "concierto", "obra", "festival", "feria", "funcion",
                   "taller", "events", "event", "calendar", "calendario")

_robots_cache = {}


class FetchResult:
    def __init__(self, url, status=None, final_url=None, text="", content_type="", error=None):
        self.url = url
        self.status = status
        self.final_url = final_url or url
        self.text = text
        self.content_type = content_type
        self.error = error

    @property
    def ok(self):
        return self.error is None and self.status is not None and 200 <= self.status < 300


def robots_allowed(url, timeout=10):
    parts = urlparse(url)
    root = "%s://%s" % (parts.scheme, parts.netloc)
    rp = _robots_cache.get(root)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            res = fetch(root + "/robots.txt", timeout=timeout, check_robots=False)
            if res.ok:
                rp.parse(res.text.splitlines())
            else:
                rp.parse([])  # sin robots.txt accesible: permitido
        except Exception:
            rp.parse([])
        _robots_cache[root] = rp
    return rp.can_fetch(USER_AGENT, url)


def _decode(raw, headers):
    enc = (headers.get("Content-Encoding") or "").lower()
    if enc == "gzip":
        raw = gzip.decompress(raw)
    elif enc == "deflate":
        raw = zlib.decompress(raw)
    ctype = headers.get("Content-Type") or ""
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    charset = m.group(1) if m else None
    if not charset:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4000], re.I)
        charset = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def fetch(url, timeout=20, check_robots=True, retries=1):
    """GET con User-Agent propio, límite de tamaño y robots.txt.

    Nunca lanza excepción: los errores quedan en FetchResult.error.
    """
    if check_robots:
        try:
            if not robots_allowed(url, timeout=timeout):
                return FetchResult(url, error="Bloqueado por robots.txt")
        except Exception as exc:  # pragma: no cover
            return FetchResult(url, error="robots.txt: %s" % exc)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept-Language": "es-CL,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
        "Accept-Encoding": "gzip, deflate"})
    ctx = ssl.create_default_context()
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read(MAX_BYTES + 1)[:MAX_BYTES]
                return FetchResult(url, resp.status, resp.geturl(), _decode(raw, resp.headers),
                                   resp.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            return FetchResult(url, exc.code, error="HTTP %s" % exc.code)
        except Exception as exc:
            last_err = "%s: %s" % (type(exc).__name__, exc)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return FetchResult(url, error=last_err)


class LinkTextParser(HTMLParser):
    """Recoge enlaces (href, texto) y el texto visible por bloques."""
    BLOCK = {"p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td",
             "br", "time", "span", "a", "header", "footer"}
    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.blocks = []
        self.title = ""
        self.headings = []
        self._skip = 0
        self._a = None
        self._buf = []
        self._in_title = False
        self._heading = None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
            return
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._a = [a["href"], []]
        if tag == "title":
            self._in_title = True
        if tag in ("h1", "h2", "h3"):
            self._heading = []
        if tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "a" and self._a:
            self.links.append((self._a[0], " ".join("".join(self._a[1]).split())))
            self._a = None
        if tag == "title":
            self._in_title = False
        if tag in ("h1", "h2", "h3") and self._heading is not None:
            h = " ".join("".join(self._heading).split())
            if h:
                self.headings.append(h)
            self._heading = None
        if tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._a:
            self._a[1].append(data)
        if self._heading is not None:
            self._heading.append(data)
        self._buf.append(data)

    def _flush(self):
        txt = " ".join("".join(self._buf).split())
        if txt:
            self.blocks.append(txt)
        self._buf = []

    def close(self):
        super().close()
        self._flush()


def parse_page(html):
    p = LinkTextParser()
    try:
        p.feed(html or "")
        p.close()
    except Exception:
        pass
    return p


def absolute_links(html, base_url):
    out = []
    for href, text in parse_page(html).links:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        u = urldefrag(urljoin(base_url, href))[0]
        if u.startswith(("http://", "https://")):
            out.append((u, text))
    return out


def same_site(a, b):
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb


def looks_like_event_url(url, text=""):
    low = (url + " " + (text or "")).lower()
    return any(h in low for h in EVENT_URL_HINTS)
