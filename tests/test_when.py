"""Ajankohdan laskenta (when.py): päivät, viikot ja mallin keksimien yksityiskohtien torjunta."""
import unittest
from datetime import date

from oma_wilma import when
from .helpers import msg, answer, item, WEEK_ONLY


class ResolveWhenTest(unittest.TestCase):
    sent = date(2026, 11, 2)  # maanantai, viikko 45

    def r(self, **kw):
        return when.resolve_when(item(**kw), self.sent)

    def test_weekday_next_occurrence_and_today(self):
        self.assertEqual(self.r(weekday="torstai"), ([{"date": date(2026, 11, 5)}], None))
        self.assertEqual(self.r(weekday="maanantai"), ([{"date": self.sent}], None))

    def test_weekday_with_relative_week(self):
        self.assertEqual(self.r(weekday="tiistai", relative_week="ensi viikko"), ([{"date": date(2026, 11, 10)}], None))
        self.assertEqual(self.r(weekday="keskiviikko", relative_week="tämä viikko"), ([{"date": date(2026, 11, 4)}], None))

    def test_weekday_with_week_numbers(self):
        targets, _ = self.r(weekday="torstai", weeks=[45, 46])
        self.assertEqual([t["date"] for t in targets], [date(2026, 11, 5), date(2026, 11, 12)])

    def test_explicit_date_and_weekday_must_agree(self):
        self.assertEqual(self.r(date="2026-11-05", weekday="torstai"), ([{"date": date(2026, 11, 5)}], None))
        self.assertEqual(self.r(date="2026-11-05", weekday="perjantai")[1], "päiväys ja viikonpäivä ovat ristiriidassa")

    def test_weeks_and_relative_week_scope(self):
        targets, _ = self.r(weeks=[45, 46])
        self.assertEqual([(t["week"], t["weeknr"]) for t in targets], [(date(2026, 11, 2), 45), (date(2026, 11, 9), 46)])
        targets, _ = self.r(relative_week="ensi viikko")
        self.assertEqual((targets[0]["week"], targets[0]["weeknr"]), (date(2026, 11, 9), 46))

    def test_year_rollover_for_week_numbers(self):
        targets, _ = when.resolve_when(item(weeks=[1]), date(2026, 12, 28))
        self.assertEqual(targets[0]["week"], date(2027, 1, 4))

    def test_problems(self):
        self.assertEqual(self.r()[1], "ajankohta ei selvinnyt")
        self.assertEqual(self.r(date="31.2.")[1], "päiväys ei ole kelvollinen")
        self.assertEqual(self.r(date="2027-03-01")[1], "päivä ei ole lähiaikoina")
        self.assertEqual(self.r(date="2026-10-01")[1], "päivä ei ole lähiaikoina")
        self.assertEqual(self.r(weeks=[20])[1], "viikko ei ole lähiaikoina")

class ModelDecidesCodeCalculatesTest(unittest.TestCase):
    """Malli päättelee ajankohdan kielestä, koodi laskee päivät eikä tulkitse viestin sanoja."""
    sent = date(2026, 10, 26)

    def test_weekday_and_week_computed_in_code_ignoring_models_own_date(self):
        # mallin päiväys 27.10. on tiistai, vaikka viikonpäivä on keskiviikko: päivä lasketaan viikosta ja viikonpäivästä
        targets, problem = when.resolve_when(item(weekday="keskiviikko", date="2026-10-27", weeks=[44]), self.sent)
        self.assertEqual((problem, [t["date"] for t in targets]), (None, [date(2026, 10, 28)]))

    def test_week_only_proposal_stays_week_level(self):
        targets, _ = when.resolve_when(item(weeks=[44]), self.sent)
        self.assertEqual([(t["week"], t["weeknr"]) for t in targets], [(date(2026, 10, 26), 44)])

    def test_far_ahead_parents_evening_is_accepted(self):
        self.assertEqual(when.resolve_when(item(date="2027-01-12"), self.sent), ([{"date": date(2027, 1, 12)}], None))

    def test_no_time_at_all_is_rejected(self):
        self.assertEqual(when.resolve_when(item(), self.sent)[1], "ajankohta ei selvinnyt")


if __name__ == "__main__":
    unittest.main()
