"""Parsing de fecha, hora y precio en español (solo librería estándar).

Regla de honestidad: cuando un dato no se puede extraer con certeza, se
devuelve None / "pending". Nunca se completa con un valor supuesto.
"""
import re
import unicodedata
from datetime import date, timedelta

MONTHS = {
    "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4, "mayo": 5, "may": 5, "junio": 6, "jun": 6,
    "julio": 7, "jul": 7, "agosto": 8, "ago": 8, "septiembre": 9,
    "setiembre": 9, "sep": 9, "sept": 9, "set": 9, "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11, "diciembre": 12, "dic": 12,
}
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

FREE_WORDS = ("gratis", "gratuito", "gratuita", "entrada liberada", "liberado",
              "liberada", "sin costo", "free", "acceso libre", "entrada libre")


def strip_accents(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize(text):
    """Minúsculas, sin acentos, sin puntuación, espacios simples."""
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9()]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(text or "").lower()).strip("-")


def _safe_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


def _infer_year(month, day, ref):
    """Año para fechas sin año: el del ref, o el siguiente si ya pasó hace >60 días."""
    cand = _safe_date(ref.year, month, day)
    if cand and cand < ref - timedelta(days=60):
        cand = _safe_date(ref.year + 1, month, day)
    return cand


def parse_date_range(text, ref=None):
    """Devuelve (inicio, fin) como 'YYYY-MM-DD' o (None, None).

    Soporta: 2026-10-17, 17/10/2026, 17-10-2026, '17 de octubre de 2026',
    'sábado 17 de octubre', '17 oct 2026', 'del 6 al 13 de noviembre',
    '6 y 7 de noviembre', '30 de septiembre al 2 de octubre de 2026'.
    """
    if not text:
        return None, None
    ref = ref or date.today()
    t = strip_accents(text).lower()

    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})", t)
    if m:
        d = _safe_date(*m.groups())
        if d:
            m2 = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})", t[m.end():])
            d2 = _safe_date(*m2.groups()) if m2 else None
            return d.isoformat(), (d2.isoformat() if d2 and d2 >= d else None)

    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2}|\d{2})\b", t)
    if m:
        dd, mm, yy = m.groups()
        yy = int(yy) + (2000 if len(yy) == 2 else 0)
        d = _safe_date(yy, mm, dd)
        if d:
            return d.isoformat(), None

    # Rango con mes distinto: "30 de septiembre al 2 de octubre de 2026"
    m = re.search(
        r"\b(\d{1,2})\s*(?:de\s+)?(%s)\.?\s*(?:de\s+(20\d{2}))?\s*(?:al|a|hasta(?: el)?|-)\s*(?:el\s+)?(\d{1,2})\s*(?:de\s+)?(%s)\.?(?:\s*(?:de|del)?\s*(20\d{2}))?"
        % (_MONTH_RE, _MONTH_RE), t)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        y = y2 or y1
        if y:
            s = _safe_date(y1 or y, MONTHS[m1], d1)
            e = _safe_date(y, MONTHS[m2], d2)
            if s and e and s > e and not y1:
                s = _safe_date(int(y) - 1, MONTHS[m1], d1)
        else:
            s = _infer_year(MONTHS[m1], d1, ref)
            e = _safe_date(s.year if s else ref.year, MONTHS[m2], d2) if s else None
            if s and e and e < s:
                e = _safe_date(s.year + 1, MONTHS[m2], d2)
        if s:
            return s.isoformat(), (e.isoformat() if e and e >= s else None)

    # Rango mismo mes: "del 6 al 13 de noviembre (de 2026)", "6 y 7 de noviembre"
    m = re.search(
        r"\b(\d{1,2})\s*(?:al|a|y|-|hasta el)\s*(\d{1,2})\s*(?:de\s+)?(%s)\.?(?:\s*(?:de|del)?\s*(20\d{2}))?"
        % _MONTH_RE, t)
    if m:
        d1, d2, mon, y = m.groups()
        if y:
            s, e = _safe_date(y, MONTHS[mon], d1), _safe_date(y, MONTHS[mon], d2)
        else:
            s = _infer_year(MONTHS[mon], d1, ref)
            e = _safe_date(s.year, MONTHS[mon], d2) if s else None
        if s:
            return s.isoformat(), (e.isoformat() if e and e > s else None)

    m = re.search(r"\b(\d{1,2})\s*(?:de\s+)?(%s)\.?(?:\s*(?:de|del)?\s*(20\d{2}))?\b" % _MONTH_RE, t)
    if m:
        d, mon, y = m.groups()
        dt = _safe_date(y, MONTHS[mon], d) if y else _infer_year(MONTHS[mon], d, ref)
        if dt:
            return dt.isoformat(), None
    return None, None


def parse_date(text, ref=None):
    return parse_date_range(text, ref)[0]


def _hhmm(h, mnt="0", ampm=None):
    h, mnt = int(h), int(mnt or 0)
    if ampm:
        ampm = ampm.replace(".", "").replace(" ", "")
        if ampm == "pm" and h < 12:
            h += 12
        if ampm == "am" and h == 12:
            h = 0
    if 0 <= h <= 23 and 0 <= mnt <= 59:
        return "%02d:%02d" % (h, mnt)
    return None


_TIME_RE = re.compile(
    r"(?<![\d$.,])\b(\d{1,2})(?:[:.h](\d{2})(?!\d))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?\s*(hrs?\.?|horas|h\b)?", re.I)


def parse_time_range(text):
    """Devuelve (inicio, fin) 'HH:MM' o (None, None).

    Una cifra sola sin ':' ni 'hrs' ni am/pm se ignora (podría ser un día o
    un precio). Soporta '19:30', '19.30 hrs', '7:30 PM', '19 horas',
    '15:00 a 21:00', 'de 15 a 21 hrs'.
    """
    if not text:
        return None, None
    t = strip_accents(text).lower()
    t = re.sub(r"\b20\d{2}-\d{2}-\d{2}t", " ", t)  # ISO 8601 con hora
    m = re.search(r"\bde\s+(\d{1,2})\s+a\s+(\d{1,2})\s*(hrs?|horas)\b", t)
    if m:
        return _hhmm(m.group(1)), _hhmm(m.group(2))
    found = []
    for m in _TIME_RE.finditer(t):
        h, mnt, ampm, unit = m.groups()
        if mnt is None and not ampm and not unit:
            continue
        # evitar confundir fechas tipo 17.10.2026 con horas
        if mnt and re.match(r"[./-]\d", t[m.end(2):m.end(2) + 2]):
            continue
        val = _hhmm(h, mnt, ampm.replace(" ", "") if ampm else None)
        if val:
            found.append((m.start(), val))
    if not found:
        return None, None
    start = found[0][1]
    end = None
    if len(found) > 1:
        between = t[found[0][0]:found[1][0]]
        if re.search(r"\b(a|al|hasta|y)\b|-|–", between):
            end = found[1][1]
    else:
        m = re.search(r"\b(?:de\s+)?(\d{1,2})\s+a\s+(\d{1,2})[:.](\d{2})", t)
        if m:
            return _hhmm(m.group(1)), _hhmm(m.group(2), m.group(3))
    return start, end


def parse_time(text):
    return parse_time_range(text)[0]


def parse_price(text):
    """Devuelve (valor_mínimo_en_CLP | None, estado) con estado en
    'free' | 'paid' | 'pending'."""
    if not text:
        return None, "pending"
    t = strip_accents(str(text)).lower()
    amounts = []
    for m in re.finditer(r"\$\s?(\d{1,3}(?:[.,]\d{3})+|\d+)", t):
        raw = re.sub(r"[.,]", "", m.group(1))
        if raw.isdigit():
            amounts.append(int(raw))
    for m in re.finditer(r"\b(\d{1,3}(?:\.\d{3})+|\d{4,7})\s*(?:clp|pesos)\b", t):
        amounts.append(int(m.group(1).replace(".", "")))
    amounts = [a for a in amounts if a > 0]
    if amounts:
        return min(amounts), "paid"
    if any(w in t for w in FREE_WORDS):
        return 0, "free"
    if re.search(r"\$\s?0\b", t):
        return 0, "free"
    return None, "pending"


CATEGORY_KEYWORDS = {
    "Empresarial": ("emprend", "empresa", "negocio", "pyme", "seminario", "congreso",
                    "networking", "camara de comercio", "innovacion", "startup",
                    "capacitacion", "feria laboral", "exportad", "rueda de negocios"),
    "Comunidad": ("feria", "deporte", "corrida", "maraton", "taller", "operativo",
                  "vecinos", "familia", "infantil", "fonda", "fiesta costumbrista",
                  "trilla", "aniversario comunal", "comunidad", "torneo", "cicletada"),
    "Cultura": ("concierto", "teatro", "obra", "danza", "ballet", "exposicion",
                "muestra", "cine", "festival", "musica", "opera", "orquesta",
                "museo", "libro", "lectura", "patrimonio", "arte", "recital"),
}


def guess_category(text):
    """Categoría por palabras clave; 'Cultura' es el valor por defecto."""
    t = normalize(text)
    scores = {c: sum(1 for k in kws if k in t) for c, kws in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Cultura"


def detect_commune(text, communes):
    """Busca el nombre de alguna comuna en el texto (sin acentos, palabra completa).

    Prefiere el nombre más largo ("San Pedro de la Paz" antes que "Paz").
    Evita 'Los Angeles' de EE.UU. si el texto menciona California/USA.
    """
    t = " " + normalize(text) + " "
    if re.search(r"\b(california|usa|estados unidos|ee uu)\b", t):
        t = t.replace(" los angeles ", " ")
    for name in sorted(communes, key=len, reverse=True):
        n = normalize(name)
        if re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(n), t):
            return name
    return None
