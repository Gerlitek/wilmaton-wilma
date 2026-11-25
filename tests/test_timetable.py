"""Lukujärjestyksen ruudukko ja HTML (keksityllä datalla, ei Wilmaa eikä Chromea)."""
import unittest
from datetime import date, timedelta

from oma_wilma.timetable import themes
from oma_wilma.models import Lesson
from oma_wilma.timetable.grid import build, format_time, parse_days, parse_lunch, parse_snack, parse_week, short_name
from oma_wilma.timetable.pdf import _slug, render_html
from tests.helpers import KIIA

MON = date(2026, 11, 30)


def les(weekday, start, end, subject):
    return Lesson(KIIA, (MON + timedelta(days=weekday)).isoformat(), start, end, subject)


WEEK = [
    les(0, "08:35", "09:20", "Suomen kieli ja kirjallisuus"),
    les(0, "09:35", "10:20", "Matematiikka"),
    les(0, "12:00", "12:45", "Liikunta yhteinen a"),
    les(1, "08:35", "09:20", "Matematiikka"),
    les(1, "08:35", "09:20", "Ryhmäkohtainen tuki 1lk"),
    les(1, "09:35", "10:20", "Tukiopetus (varaus)"),
    les(3, "12:00", "12:45", "Englanti, A1"),   # torstai alkaa ruokailun jälkeen
]


class NamesAndParsingTest(unittest.TestCase):
    def test_short_names(self):
        self.assertEqual(short_name("Kuvataide yhteinen a"), "Kuvataide")
        self.assertEqual(short_name("Englanti, A1"), "Englanti")
        self.assertEqual(short_name("Tukiopetus (varaus)"), "Tukiopetus")
        self.assertEqual(short_name("Ryhmäkohtainen tuki 1lk"), "Ryhmäkohtainen tuki")
        self.assertEqual(short_name("Suomen kieli ja kirjallisuus"), "Äidinkieli")
        self.assertEqual(short_name("Uskonto/Elämänkatsomustieto"), "Uskonto")
        self.assertEqual(short_name("Uskonto/Elämänkatsomustieto", {"Uskonto/Elämänkatsomustieto": "ET"}), "ET")
        self.assertEqual(short_name("Kuvataide yhteinen a", {"Kuvataide": "Kuviss"}), "Kuviss")

    def test_days(self):
        self.assertEqual(parse_days("ma, ke"), {0, 2})
        self.assertEqual(parse_days("tue thu"), {1, 3})
        self.assertEqual(parse_days("mon,wed,fri"), {0, 2, 4})
        self.assertEqual(parse_days("5"), {4})
        self.assertEqual(parse_days("torstai"), {3})
        with self.assertRaises(ValueError):
            parse_days("t")
        self.assertEqual(parse_snack(["ti", "Kiia=pe"]), [(None, {1}), ("Kiia", {4})])

    def test_lunch_week_time(self):
        self.assertEqual(parse_lunch("11.35–12.00"), ("11:35", "12:00"))
        self.assertIsNone(parse_lunch(""))
        self.assertEqual(parse_week("next", date(2026, 11, 25)), MON)
        self.assertEqual(parse_week("this", date(2026, 11, 25)), date(2026, 11, 23))
        self.assertEqual(parse_week("2026-12-03"), MON)
        self.assertEqual(format_time("08:35"), "8.35")
        self.assertEqual(parse_week("tama", date(2026, 11, 25)), date(2026, 11, 23))
        self.assertEqual(_slug("Åsa-Äijö"), "asa-aijo")


class BuildTest(unittest.TestCase):
    def test_grid_overlap_and_support(self):
        tt = build(WEEK, KIIA, MON)
        self.assertEqual([(r.start, r.end) for r in tt.rows], [("08:35", "09:20"), ("09:35", "10:20"), ("12:00", "12:45")])
        tue = tt.rows[0].lessons[1]
        self.assertEqual([e.name for e in tue], ["Matematiikka", "Ryhmäkohtainen tuki"])
        self.assertTrue(tue[1].support)
        self.assertEqual(tt.pe_days, [True, False, False, False, False])
        self.assertEqual(tt.empty_days, [False, False, True, False, True])

    def test_drop_support(self):
        tt = build(WEEK, KIIA, MON, drop_support=True)
        self.assertEqual([e.name for e in tt.rows[0].lessons[1]], ["Matematiikka"])
        self.assertEqual(tt.rows[1].lessons[1], [])

    def test_breaks_and_lunch(self):
        tt = build(WEEK, KIIA, MON, breaks="all", lunch=("11:35", "12:00"))
        kinds = [(r.kind, r.start, r.end) for r in tt.rows]
        self.assertEqual(kinds, [("lesson", "08:35", "09:20"), ("break", "09:20", "09:35"), ("lesson", "09:35", "10:20"),
                                 ("lunch", "10:20", "12:00"), ("lesson", "12:00", "12:45")])
        self.assertEqual(tt.rows[1].at_school, [True, True, False, False, False])
        # Maanantaina koulussa ennen ja jälkeen; torstaina tullaan ruokailuun, tiistaina koulu loppuu ennen.
        self.assertEqual(tt.rows[3].at_school, [True, False, False, True, False])
        self.assertEqual(tt.starts_after_lunch, [False, False, None, True, None])
        html = render_html(tt, themes.get("green"), start_emoji=True)
        self.assertIn("Maanantai<span class=\"start\">☀️", html)
        self.assertIn("Torstai<span class=\"start\">🌙", html)
        self.assertIsNone(build(WEEK, KIIA, MON).starts_after_lunch[0])

    def test_meals_only(self):
        tt = build(WEEK, KIIA, MON, breaks="lunch", lunch=("11:35", "12:00"))
        self.assertEqual([r.kind for r in tt.rows], ["lesson", "lesson", "lunch", "lesson"])
        self.assertEqual([r.kind for r in build(WEEK, KIIA, MON, breaks="lunch").rows], ["lesson"] * 3)

    def test_break_without_lunch_needs_lesson_before(self):
        tt = build(WEEK, KIIA, MON, breaks="all")
        self.assertEqual(tt.rows[3].kind, "break")
        self.assertEqual(tt.rows[3].at_school, [True, False, False, False, False])

    def test_other_weeks_ignored(self):
        other = Lesson(KIIA, "2026-12-07", "08:35", "09:20", "Musiikki")
        self.assertEqual(build([other], KIIA, MON).rows, [])


class RenderTest(unittest.TestCase):
    def test_html(self):
        tt = build(WEEK, KIIA, MON, breaks="all", lunch=("11:35", "12:00"), snack_days={2})
        html = render_html(tt, themes.get("green"), pe_emoji=True)
        self.assertIn("<title>Lukujärjestys – Kiia</title>", html)
        self.assertIn("🎽", html)
        self.assertIn("🍎 välipala", html)
        self.assertIn("ruokailu", html)
        self.assertNotIn("🎽", render_html(tt, themes.get("green")))

    def test_pixel_title_and_theme_lookup(self):
        self.assertEqual(len(themes.pixel_text("Ödä")), 7)
        self.assertEqual(themes.pixel_text("???"), [])
        with self.assertRaises(ValueError):
            themes.get("sininen")
        self.assertEqual(themes.get("vihreä").name, "green")
        self.assertEqual(themes.get("sydän").name, "heart")
        self.assertEqual(themes.get("vihrea").name, "green")
        self.assertIn("Kiia", themes.get("heart").background("Kiia"))


if __name__ == "__main__":
    unittest.main()
