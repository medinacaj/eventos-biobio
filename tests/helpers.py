import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import db  # noqa: E402
import discovery  # noqa: E402

COMMUNES = discovery.load_communes()


def memory_db():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


def ev(**kw):
    base = {"title": "Concierto de prueba", "date": "2030-05-10", "time": "19:00",
            "commune": "Concepción", "venue": "Teatro X", "category": "Cultura",
            "price_status": "pending", "source": "Fuente A", "source_url": "https://a.example/ev",
            "source_type": "venue", "source_priority": 1, "official": True}
    base.update(kw)
    return base
