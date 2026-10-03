import unittest
from datetime import date

from tests.helpers import COMMUNES  # noqa: F401  (asegura sys.path)
import metadata

REF = date(2026, 10, 3)


class DateTests(unittest.TestCase):
    def t(self, text, expected, ref=REF):
        self.assertEqual(metadata.parse_date(text, ref), expected, text)

    def test_formats(self):
        self.t("2026-10-17", "2026-10-17")
        self.t("17/10/2026", "2026-10-17")
        self.t("17-10-2026", "2026-10-17")
        self.t("17.10.26", "2026-10-17")
        self.t("Sábado 17 de octubre de 2026, 19:30 hrs", "2026-10-17")
        self.t("17 de Octubre", "2026-10-17")
        self.t("17 oct 2026", "2026-10-17")
        self.t("4 de octubre en Tomé", "2026-10-04")
        self.t("1 de septiembre", "2026-09-01")  # 32 días atrás: mismo año

    def test_year_rollover(self):
        self.t("15 de enero", "2027-01-15")
        self.t("15 de enero", "2026-01-15", ref=date(2026, 1, 10))

    def test_ranges(self):
        r = lambda s: metadata.parse_date_range(s, REF)
        self.assertEqual(r("del 6 al 13 de noviembre"), ("2026-11-06", "2026-11-13"))
        self.assertEqual(r("6 y 7 de noviembre de 2026"), ("2026-11-06", "2026-11-07"))
        self.assertEqual(r("23 al 30 de septiembre de 2026"), ("2026-09-23", "2026-09-30"))
        self.assertEqual(r("30 de diciembre al 2 de enero"), ("2026-12-30", "2027-01-02"))
        self.assertEqual(r("30 de septiembre al 2 de octubre de 2026"), ("2026-09-30", "2026-10-02"))

    def test_invalid(self):
        self.t("", None)
        self.t("sin fecha", None)
        self.t("31 de febrero de 2026", None)
        self.t("Próximamente", None)


class TimeTests(unittest.TestCase):
    def test_times(self):
        p = metadata.parse_time
        self.assertEqual(p("19:30"), "19:30")
        self.assertEqual(p("a las 19.30 hrs"), "19:30")
        self.assertEqual(p("7:30 PM"), "19:30")
        self.assertEqual(p("7 pm"), "19:00")
        self.assertEqual(p("12:00 a.m."), "00:00")
        self.assertEqual(p("19 horas"), "19:00")
        self.assertEqual(p("20 hrs."), "20:00")
        self.assertEqual(p("2026-10-17T19:30:00-03:00"), "19:30")

    def test_no_false_time(self):
        p = metadata.parse_time
        self.assertIsNone(p("17 de octubre"))
        self.assertIsNone(p("Entrada $5.000"))
        self.assertIsNone(p(""))
        self.assertIsNone(p("17.10.2026"))
        self.assertIsNone(p("25:00"))

    def test_ranges(self):
        r = metadata.parse_time_range
        self.assertEqual(r("De 15:00 a 21:00 horas"), ("15:00", "21:00"))
        self.assertEqual(r("15.00 - 21.00 hrs"), ("15:00", "21:00"))
        self.assertEqual(r("de 15 a 21 hrs"), ("15:00", "21:00"))
        self.assertEqual(r("19:30"), ("19:30", None))


class PriceTests(unittest.TestCase):
    def test_prices(self):
        p = metadata.parse_price
        self.assertEqual(p("$7.000 general; $5.000 estudiantes"), (5000, "paid"))
        self.assertEqual(p("Entrada: $ 12.500"), (12500, "paid"))
        self.assertEqual(p("Desde $15000"), (15000, "paid"))
        self.assertEqual(p("10.000 pesos"), (10000, "paid"))
        self.assertEqual(p("Entrada liberada"), (0, "free"))
        self.assertEqual(p("Gratuito, con inscripción"), (0, "free"))
        self.assertEqual(p("GRATIS"), (0, "free"))
        self.assertEqual(p("$0"), (0, "free"))

    def test_pending(self):
        p = metadata.parse_price
        self.assertEqual(p(""), (None, "pending"))
        self.assertEqual(p(None), (None, "pending"))
        self.assertEqual(p("Por confirmar"), (None, "pending"))
        self.assertEqual(p("Consultar en boletería"), (None, "pending"))


class MiscTests(unittest.TestCase):
    def test_detect_commune(self):
        names = [c["name"] for c in COMMUNES]
        d = metadata.detect_commune
        self.assertEqual(d("Gimnasio Municipal de Tome", names), "Tomé")
        self.assertEqual(d("Av. Siempre Viva 123, San Pedro de la Paz", names), "San Pedro de la Paz")
        self.assertEqual(d("Teatro Municipal, Los Ángeles, Biobío", names), "Los Ángeles")
        self.assertIsNone(d("Crypto.com Arena, Los Angeles, California", names))
        self.assertIsNone(d("Movistar Arena, Santiago", names))

    def test_guess_category(self):
        self.assertEqual(metadata.guess_category("Concierto sinfónico"), "Cultura")
        self.assertEqual(metadata.guess_category("Seminario de emprendimiento pyme"), "Empresarial")
        self.assertEqual(metadata.guess_category("Corrida familiar"), "Comunidad")
        self.assertEqual(metadata.guess_category("xyz"), "Cultura")


if __name__ == "__main__":
    unittest.main()
