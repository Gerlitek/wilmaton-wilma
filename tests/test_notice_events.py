"""Tapahtumien rakennus (notice_events.py): viikot lukujärjestykseen, yhdistäminen, muistutukset ja omistajuus."""
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from oma_wilma import calendars, events, messages, notices, report
from oma_wilma.models import Exam, Lesson, Student
from .helpers import KIIA, ONNI, info, msg, answer, item, SKATING, ITEM, WEEK_TEXT, WEEK_ITEM, TWO_WEEKS


class BuildTest(unittest.TestCase):
    def items(self, *specs):
        return [{"info": info(), "kind": k, "date": date(2026, 11, 5), "title": t, "bring": b} for k, t, b in specs]

    def test_title_emoji_kind_and_gear_first(self):
        ev = notices.build_events(self.items(("pe", "luistelu", "luistimet ja kypärä")))[0]
        self.assertEqual(ev["title"], "🎽Luistelu: luistimet ja kypärä")
        self.assertEqual(ev["calendar"], "Wilma Kiia")
        self.assertEqual(ev["alarm"], datetime(2026, 11, 4, 18, 0))

    def test_photo_day_has_its_own_emoji_without_gear(self):
        self.assertEqual(notices.build_events(self.items(("photo", "kuvauspäivä", "")))[0]["title"], "📸Kuvaus: kuvauspäivä")

    def test_same_kind_same_day_merged_other_kind_separate(self):
        evs = notices.build_events(self.items(("pe", "uinti", "uimavarusteet"), ("pe", "uinti", "uimavarusteet"),
                                              ("pe", "sisäliikunta", "sisäkengät"), ("photo", "kuvauspäivä", "")))
        self.assertEqual(len(evs), 2)
        pe = next(e for e in evs if e["kind"] == "pe")
        self.assertEqual(pe["title"], "🎽Uinti; Sisäliikunta")

    def test_uid_ignores_model_wording(self):
        a = notices.build_events(self.items(("pe", "luistelu", "luistimet")))[0]["uid"]
        b = notices.build_events(self.items(("pe", "jääliikunta", "luistimet ja kypärä")))[0]["uid"]
        self.assertEqual(a, b)

    def test_message_text_not_in_notes(self):
        ev = notices.build_events([{**self.items(("pe", "luistelu", "luistimet"))[0], "info": info()}])[0]
        self.assertNotIn("Torstaina", ev["notes"])


class InfoAndParentsEventsTest(unittest.TestCase):
    def one(self, kind, title, organizer=None):
        it = {"info": info(), "kind": kind, "date": date(2026, 11, 4), "title": title, "bring": "", "organizer": organizer,
              "src": "1001:7"}
        return notices.build_events([it])[0]

    def test_info_event_is_clearly_labelled_and_has_no_reminder(self):
        e = self.one("info", "Hyvinvointialue – vanhempainilta", "Hyvinvointialue")
        self.assertEqual(e["title"], "ℹ️Tiedoksi: Hyvinvointialue – vanhempainilta")
        self.assertIsNone(e["alarm"])
        self.assertEqual(e["extra_alarms"], [])
        self.assertIn("ei koulun oma tilaisuus", e["notes"])

    def test_school_parents_evening_has_two_reminders(self):
        e = self.one("parents", "vanhempainilta")
        self.assertEqual(e["title"], "👪Vanhempainilta")
        self.assertEqual(e["alarm"], datetime(2026, 11, 3, 18, 0))
        self.assertEqual(e["extra_alarms"], [datetime(2026, 11, 1, 18, 0)])

    def test_alarm_description_handles_every_case(self):
        self.assertEqual(report.describe_alarms(self.one("info", "ilta", "Hyvinvointialue")), "ei muistutusta")
        self.assertEqual(report.describe_alarms(self.one("event", "juhla")), "muistutus 03.11. 18:00")
        self.assertEqual(report.describe_alarms(self.one("parents", "vanhempainilta")), "muistutus 01.11. 18:00, 03.11. 18:00")

    def test_sources_recorded(self):
        self.assertEqual(self.one("event", "juhla")["sources"], ["1001:7"])

    def test_titles_do_not_repeat_themselves(self):
        self.assertEqual(events.make_title("trip", "retki Nuuksioon – eväät"), "🚌Retki: Nuuksioon – eväät")
        self.assertEqual(events.make_title("photo", "kuvauspäivä"), "📸Kuvaus: kuvauspäivä")
        self.assertEqual(events.make_title("pe", "luistelu: luistimet"), "🎽Luistelu: luistimet")


class ExpandWeeksTest(unittest.TestCase):
    today = date(2026, 10, 28)   # keskiviikko, viikko 44

    def lessons_for(self, student, monday):
        base = monday
        l = lambda off, subj, start: Lesson(KIIA, (base + timedelta(days=off)).isoformat(), start, "10:00", subj)
        return [l(0, "Matematiikka", "08:00"), l(1, "Liikunta yhteinen a", "09:15"), l(3, "Liikunta yhteinen a", "12:00")]

    def expanded(self, lessons_for=None):
        m = msg(WEEK_TEXT, sent=date(2026, 10, 26))
        items, _ = notices.interpret(m, answer(WEEK_ITEM), self.today)
        return notices.expand_weeks(items, lessons_for or self.lessons_for, self.today)

    def test_week_placed_on_pe_lesson_days_not_yet_past(self):
        # viikko 44: ti 27.10. on jo mennyt, to 29.10. jää; viikko 45: ti 3.11. ja to 5.11.
        self.assertEqual([(i["date"].isoformat(), i["time"]) for i in self.expanded()],
                         [("2026-10-29", "12:00"), ("2026-11-03", "09:15"), ("2026-11-05", "12:00")])

    def test_events_from_expanded_weeks(self):
        evs = notices.build_events(self.expanded())
        self.assertEqual(len(evs), 3)
        self.assertEqual(evs[0]["title"], "🎽Sisäliikunta: sisäkengät ja…")
        self.assertIn("klo 12:00", evs[0]["notes"])

    def test_fallback_to_monday_without_schedule(self):
        def broken(student, monday):
            raise RuntimeError("ei yhteyttä")
        got = self.expanded(broken)
        self.assertEqual([(i["date"], i["title"]) for i in got],
                         [(self.today, "sisäliikunta (vko 44)"), (date(2026, 11, 2), "sisäliikunta (vko 45)")])

    def test_non_pe_week_goes_to_monday(self):
        m = msg("Kuvauspäivä on ensi viikolla.", sent=date(2026, 10, 26))
        items, _ = notices.interpret(m, answer(item(category="kuvaus", title="kuvauspäivä", bring="", relative_week="ensi viikko")), self.today)
        got = notices.expand_weeks(items, self.lessons_for, self.today)
        self.assertEqual([(i["kind"], i["date"]) for i in got], [("photo", date(2026, 11, 2))])


class WeeklyProgramTest(unittest.TestCase):
    today = date(2026, 10, 26)
    sent = date(2026, 10, 26)

    def lessons_for(self, student, monday):
        l = lambda off, start: Lesson(KIIA, (monday + timedelta(days=off)).isoformat(), start, "10:00", "Liikunta yhteinen a")
        return [l(1, "09:35"), l(2, "08:35")]

    def run_(self, *items):
        found, notes = notices.interpret(msg(TWO_WEEKS, sent=self.sent), answer(*items), self.today)
        return found, notes

    def events(self, found):
        return notices.build_events(notices.expand_weeks(found, self.lessons_for, self.today))

    def test_each_week_gets_only_its_own_activity(self):
        good = [item(title="luistelu", bring="luistimet ja kypärä", weeks=[44]),
                item(title="sisäliikunta", bring="liikuntavaatteet", weeks=[45])]
        evs = self.events(self.run_(*good)[0])
        by_week = {e["date"].isocalendar().week: e["title"] for e in evs}
        self.assertEqual(by_week[44], "🎽Luistelu: luistimet ja kypärä")
        self.assertEqual(by_week[45], "🎽Sisäliikunta: liikuntavaatteet")

    def test_broad_item_loses_to_week_specific_one(self):
        # tyypillinen virhe: yksi sisäliikuntaitem kummallekin viikolle + erillinen luistelu viikolle 44
        bad = [item(title="sisäliikunta", bring="liikuntavaatteet", weeks=[44, 45]),
               item(title="luistelu", bring="luistimet ja kypärä", weeks=[44])]
        found, _ = self.run_(*bad)
        self.assertEqual(sorted((i["week"].isocalendar().week, i["title"]) for i in found),
                         [(44, "luistelu"), (45, "sisäliikunta")])
        evs = self.events(found)
        self.assertFalse([e for e in evs if e["date"].isocalendar().week == 44 and "sisäliikunta" in e["title"].casefold()])
        self.assertEqual({e["date"].isocalendar().week for e in evs if "sisäliikunta" in e["title"].casefold()}, {45})

    def test_prompt_demands_one_activity_per_week(self):
        seen = {}
        def ask(prompt, schema):
            seen["p"] = prompt
            return {"items": []}
        notices.interpret(msg(TWO_WEEKS, sent=self.sent), ask, self.today)
        self.assertIn("jos viikolla on luistelua, siellä ei ole muuta liikuntaa", " ".join(seen["p"].split()))
        self.assertIn("tee jokaisesta asiasta ja viikosta oma rivi", " ".join(seen["p"].split()))

    def test_newest_weekly_message_replaces_older_and_state_text(self):
        old = {"info": info(sent=date(2026, 10, 20), mid=1), "kind": "pe", "title": "sisäliikunta", "bring": "",
               "date": date(2026, 10, 28), "from_week": True}
        new = {**old, "info": info(sent=date(2026, 10, 26), mid=2), "title": "luistelu", "bring": "luistimet"}
        stale = {notices.build_events([new])[0]["uid"]: {"texts": ["sisäliikunta"], "lines": ["Asia: sisäliikunta"]}}
        ev = notices.build_events([old, new], previous=stale)[0]
        self.assertEqual(ev["title"], "🎽Luistelu: luistimet")
        self.assertNotIn("sisäliikunta", ev["notes"])


class OwnershipTest(unittest.TestCase):
    """Tapahtuma ei saa koskaan päätyä väärän lapsen kalenteriin."""
    students = [KIIA, ONNI]

    def event_for(self, student):
        items = [{"info": info(student=student), "kind": "pe", "date": date(2026, 11, 5), "title": "uinti", "bring": "",
                  "src": f"{student.number}:7"}]
        return notices.build_events(items)[0]

    def test_each_event_goes_to_its_own_childs_calendar(self):
        self.assertEqual(self.event_for(KIIA)["calendar"], "Wilma Kiia")
        self.assertEqual(self.event_for(ONNI)["calendar"], "Wilma Onni")
        calendars.verify_owners([self.event_for(KIIA), self.event_for(ONNI)], self.students)      # ei poikkeusta

    def test_wrong_calendar_aborts_before_anything_is_written(self):
        wrong = {**self.event_for(KIIA), "calendar": "Wilma Onni"}
        with self.assertRaises(SystemExit) as cm:
            calendars.verify_owners([self.event_for(ONNI), wrong], self.students)
        self.assertIn("Mitään ei kirjoitettu", str(cm.exception))

    def test_unknown_student_aborts(self):
        stranger = {**self.event_for(KIIA), "student": "9999"}
        with self.assertRaises(SystemExit):
            calendars.verify_owners([stranger], self.students)

    def test_same_first_name_aborts(self):
        twin = Student("2002", "Kiia Korhonen")
        with self.assertRaises(SystemExit) as cm:
            calendars.check_unique_calendars([KIIA, twin])
        self.assertIn("sama kalenterin nimi", str(cm.exception))

    def test_events_carry_the_childs_name_and_origin(self):
        e = self.event_for(ONNI)
        self.assertTrue(e["notes"].startswith("Oppilas: Onni"))
        self.assertEqual(e["origin"], "viesti")
        exam = events.exam_event(Exam(ONNI, "2026-11-05", None, "Matematiikka", "Koe", None, None))
        self.assertEqual((exam["origin"], exam["calendar"]), ("koe", "Wilma Onni"))
        self.assertTrue(exam["notes"].startswith("Oppilas: Onni"))

    def test_message_opened_under_another_student_is_refused(self):
        i = info(student=KIIA)
        other = {"student": {"studentNumber": "1002"}, "message": {"content": "x"}}
        with mock.patch.object(messages.bridge, "run", return_value=other):
            with self.assertRaises(messages.bridge.WilmaError):
                messages.read_message(i)
        same = {"student": {"studentNumber": "1001"}, "message": {"content": "x"}}
        with mock.patch.object(messages.bridge, "run", return_value=same):
            self.assertEqual(messages.read_message(i).text, "x")

    def test_output_is_grouped_by_child_under_a_section_title(self):
        out = report.format_events("VIESTIT", [self.event_for(ONNI), self.event_for(KIIA)])
        self.assertEqual(out.splitlines()[0], "=== VIESTIT ===")
        self.assertLess(out.index("Wilma Kiia"), out.index("Wilma Onni"))
        self.assertIn("[viesti 7]", out)

    def test_trace_lists_model_proposals_and_result(self):
        trace = []
        notices.interpret(msg(SKATING), answer(ITEM), date(2026, 11, 2), trace=trace)
        self.assertEqual(trace[0], "malli ehdotti: liikunta | luistelu | luistimet ja kypärä [torstai]")
        self.assertEqual(trace[-1], "kalenteriin 1 asiaa")

class MergeAcrossRunsTest(unittest.TestCase):
    """Saman päivän asiat eri viesteistä yhdistyvät; viestin uudelleenkäsittely korvaa sen oman vanhan osuuden."""

    def items(self, title, bring, mid, kind="pe"):
        return [{"info": info(mid=mid), "kind": kind, "date": date(2026, 11, 5), "title": title, "bring": [bring],
                 "src": f"1001:{mid}"}]

    def state_of(self, event):
        return {event["uid"]: {"parts": event["parts"]}}

    def test_new_message_same_day_keeps_the_earlier_messages_text(self):
        first = notices.build_events(self.items("luistelu", "luistimet", 1))[0]
        second = notices.build_events(self.items("sisäliikunta", "sisäkengät", 2), previous=self.state_of(first))[0]
        self.assertEqual(second["title"], "🎽Luistelu; Sisäliikunta")
        self.assertIn("(luistelu): luistimet", second["notes"])
        self.assertIn("(sisäliikunta): sisäkengät", second["notes"])
        self.assertEqual(second["sources"], ["1001:1", "1001:2"])

    def test_reprocessed_message_replaces_its_own_old_part_instead_of_merging_with_itself(self):
        first = notices.build_events(self.items("luistelu", "luistimet", 1))[0]
        again = notices.build_events(self.items("luistelu", "luistimet, kypärä, maila", 1), previous=self.state_of(first),
                                     reprocessed={"1001:1"})[0]
        self.assertEqual(again["title"], "🎽Luistelu: luistimet, kypärä, maila")      # ei "Luistelu: luistimet; Luistelu: ..."
        self.assertEqual(again["sources"], ["1001:1"])

    def test_reprocessing_one_message_keeps_the_other_messages_part(self):
        a = notices.build_events(self.items("luistelu", "luistimet", 1))[0]
        both = notices.build_events(self.items("uinti", "uimapuku", 2), previous=self.state_of(a))[0]
        redone = notices.build_events(self.items("luistelu", "luistimet ja kypärä", 1), previous=self.state_of(both),
                                      reprocessed={"1001:1"})[0]
        self.assertEqual(redone["title"], "🎽Uinti; Luistelu")
        self.assertIn("luistimet ja kypärä", redone["notes"])
        self.assertIn("uimapuku", redone["notes"])
        self.assertNotIn("Ota mukaan (luistelu): luistimet\n", redone["notes"])

    def test_same_message_and_text_again_is_not_duplicated(self):
        first = notices.build_events(self.items("luistelu", "luistimet", 1))[0]
        again = notices.build_events(self.items("luistelu", "luistimet", 1), previous=self.state_of(first))[0]
        self.assertEqual(again["title"], first["title"])

    def test_weekly_program_newest_message_replaces_everything(self):
        old = [{**i, "from_week": True, "info": info(sent=date(2026, 10, 20), mid=1)} for i in self.items("sisäliikunta", "x", 1)]
        new = [{**i, "from_week": True, "info": info(sent=date(2026, 10, 26), mid=2)} for i in self.items("luistelu", "luistimet", 2)]
        stale = {notices.build_events(new)[0]["uid"]: {"parts": {"1001:0": {"texts": ["Vanha"], "lines": ["Vanha"]}}}}
        ev = notices.build_events(old + new, previous=stale)[0]
        self.assertEqual(ev["title"], "🎽Luistelu: luistimet")
        self.assertNotIn("Vanha", ev["notes"])


class WeeklyMergeKeepsTheStickTest(unittest.TestCase):
    """Uudempi vastaus samasta lajista ei pudota aiemman viestin valinnaista mailaa."""

    def weekly(self, title, mid, sent, bring, optional=(), uncertain=""):
        return {"info": info(sent=sent, mid=mid), "kind": "pe", "date": date(2026, 10, 28), "title": title, "from_week": True,
                "bring": list(bring), "optional": list(optional), "forbidden": [], "uncertain": uncertain, "src": f"1001:{mid}"}

    def test_newer_reply_without_the_stick_keeps_the_older_messages_stick(self):
        older = self.weekly("luistelu", 1, date(2026, 10, 26), ["luistimet", "kypärä", "ulkovaatetus (takki, hanskat)"], ["maila"])
        newer = self.weekly("luistelu", 2, date(2026, 10, 27), ["luistimet", "kypärä", "ulkovaatetus (takki, hanskat)"],
                            uncertain="viikonpäivä ei selvä")
        ev = notices.build_events([older, newer])[0]
        self.assertEqual(ev["title"], "🎽Luistelu: luistimet")
        self.assertIn("Halutessaan voi ottaa (luistelu): maila", ev["notes"])
        self.assertNotIn("TARKISTA", ev["notes"])                       # toinen viesti oli varma
        self.assertEqual(ev["sources"], ["1001:1", "1001:2"])

    def test_day_named_row_with_the_stick_is_kept_when_a_newer_weekly_reply_lacks_it(self):
        """Todellinen tilanne: vanhempi viesti nimeää päivän (rivi ilman from_week), uudempi vastaus on viikkotasolla."""
        dayrow = {**self.weekly("luistelu", 1, date(2026, 10, 26), ["luistimet", "kypärä"], ["maila"]), "from_week": False}
        reply = self.weekly("luistelu", 2, date(2026, 10, 26), ["luistimet", "kypärä"])
        reply["info"] = info(sent=date(2026, 10, 26), mid=2)
        ev = notices.build_events([dayrow, {**reply, "info": info(sent=date(2026, 10, 27), mid=2)}])[0]
        self.assertEqual(ev["title"], "🎽Luistelu: luistimet")
        self.assertEqual(ev["sources"], ["1001:1", "1001:2"])

    def test_newest_message_decides_the_activity_older_other_activity_is_dropped(self):
        older = self.weekly("sisäliikunta", 1, date(2026, 10, 20), ["sisäkengät"])
        newer = self.weekly("luistelu", 2, date(2026, 10, 26), ["luistimet"])
        self.assertEqual(notices.build_events([older, newer])[0]["title"], "🎽Luistelu: luistimet")

    def test_required_item_wins_over_the_same_item_as_optional(self):
        older = self.weekly("luistelu", 1, date(2026, 10, 26), ["luistimet"], ["maila"])
        newer = self.weekly("luistelu", 2, date(2026, 10, 27), ["luistimet", "maila"])
        ev = notices.build_events([older, newer])[0]
        self.assertEqual(ev["title"], "🎽Luistelu: luistimet")
        self.assertNotIn("Halutessaan", ev["notes"])

    def test_uncertain_stays_only_if_every_message_is_uncertain(self):
        a = self.weekly("luistelu", 1, date(2026, 10, 26), ["luistimet"], uncertain="epäselvä")
        b = self.weekly("luistelu", 2, date(2026, 10, 27), ["luistimet"], uncertain="epäselvä")
        self.assertIn("TARKISTA", notices.build_events([a, b])[0]["notes"])


class OneRowPerWeekTest(unittest.TestCase):
    """Malli antaa yhden viikkonumeron per rivi (`week`), joten viikon 44 luistelu ja viikon 45 sisäliikunta eivät sekoitu."""
    sent = date(2026, 10, 26)

    def lessons_for(self, student, monday):
        return [Lesson(KIIA, (monday + timedelta(days=1)).isoformat(), "09:35", "10:00", "Liikunta yhteinen a")]

    def test_each_row_has_its_own_week_and_lands_on_that_weeks_pe_lesson(self):
        rows = [item(title="luistelu", bring=["luistimet"], week=44), item(title="sisäliikunta", bring=["vesipullo"], week=45)]
        found, notes = notices.interpret(msg(TWO_WEEKS, sent=self.sent), answer(*rows), date(2026, 10, 26))
        evs = notices.build_events(notices.expand_weeks(found, self.lessons_for, date(2026, 10, 26)))
        self.assertEqual(notes, [])
        self.assertEqual([(e["date"].isoformat(), e["title"]) for e in evs],
                         [("2026-10-27", "🎽Luistelu: luistimet"), ("2026-11-03", "🎽Sisäliikunta: vesipullo")])

    def test_week_field_is_described_in_the_trace(self):
        trace = []
        notices.interpret(msg(TWO_WEEKS, sent=self.sent), answer(item(week=44)), date(2026, 10, 26), trace=trace)
        self.assertIn("[vko 44]", trace[0])


class OutsideOrganizerTitleTest(unittest.TestCase):
    def test_organizer_is_shown_even_when_the_model_wrote_its_own_short_title(self):
        it = {"info": info(), "kind": "info", "date": date(2026, 11, 4), "title": "Seurakunta – vanhempainilta",
              "short_title": "vanhempainilta klo 18", "bring": [], "organizer": "Seurakunta", "src": "1001:7"}
        self.assertEqual(notices.build_events([it])[0]["title"], "ℹ️Tiedoksi: Seurakunta – Vanhempainilta klo 18")

    def test_organizer_not_repeated_when_the_title_already_starts_with_it(self):
        it = {"info": info(), "kind": "info", "date": date(2026, 11, 4), "title": "x", "short_title": "Seurakunta: ilta klo 18",
              "bring": [], "organizer": "Seurakunta", "src": "1001:7"}
        self.assertEqual(notices.build_events([it])[0]["title"], "ℹ️Tiedoksi: Seurakunta: ilta klo 18")


class TitleLabelTest(unittest.TestCase):
    def test_label_is_not_repeated_even_with_punctuation(self):
        self.assertEqual(events.make_title("parents", "Vanhempainilta: klo 18.00"), "👪Vanhempainilta: Klo 18.00")
        self.assertEqual(events.make_title("parents", "vanhempainilta - klo 18"), "👪Vanhempainilta: Klo 18")
        self.assertEqual(events.make_title("trip", "retki Nuuksioon"), "🚌Retki: Nuuksioon")

    def test_a_longer_word_starting_with_the_label_is_not_cut(self):
        self.assertEqual(events.make_title("photo", "kuvauspäivä"), "📸Kuvaus: kuvauspäivä")


class ShortTitleTest(unittest.TestCase):
    """Otsikko mahtuu puhelimen pienelle näytölle: laji ja tärkein varuste. Koko lista (maila mukaan) on muistiinpanoissa."""

    def event(self, short_title, bring=("luistimet", "kypärä"), optional=("maila",)):
        it = {"info": info(), "kind": "pe", "date": date(2026, 11, 5), "title": "luistelu", "short_title": short_title,
              "bring": list(bring), "optional": list(optional), "src": "1001:7"}
        return notices.build_events([it])[0]

    def test_models_short_title_is_used_when_it_fits(self):
        self.assertEqual(self.event("luistelu: luistimet")["title"], "🎽Luistelu: luistimet")

    def test_code_builds_the_short_title_when_models_is_too_long_or_missing(self):
        long = "Luistelu: luistimet, kypärä, ulkovaatetus, maila halutessa"
        self.assertEqual(self.event(long)["title"], "🎽Luistelu: luistimet")
        self.assertEqual(self.event("")["title"], "🎽Luistelu: luistimet")

    def test_title_never_exceeds_the_phone_width_but_the_notes_carry_everything(self):
        e = self.event("")
        self.assertLessEqual(len(e["title"]) - 1, events.MAX_TEXT + len("Luistelu"))
        self.assertIn("Ota mukaan (luistelu): luistimet; kypärä", e["notes"])
        self.assertIn("Halutessaan voi ottaa (luistelu): maila", e["notes"])

    def test_optional_item_only_in_title_when_nothing_is_required(self):
        self.assertEqual(self.event("", bring=[], optional=["maila"])["title"], "🎽Luistelu: maila halutessa")

    def test_two_activities_on_one_day_show_only_their_names(self):
        base = {"info": info(), "kind": "pe", "date": date(2026, 11, 5), "bring": ["x"], "optional": [], "src": "1001:7"}
        e = notices.build_events([{**base, "title": "uinti"}, {**base, "title": "luistelu", "src": "1001:8"}])[0]
        self.assertEqual(e["title"], "🎽Uinti; Luistelu")


class UncertainEventTest(unittest.TestCase):
    def event(self, uncertain):
        it = {"info": info(), "kind": "event", "date": date(2026, 11, 5), "title": "juhla", "bring": [], "uncertain": uncertain,
              "src": "1001:7"}
        return notices.build_events([it])[0]

    def test_uncertain_event_is_marked_visibly_in_title_and_notes(self):
        e = self.event("päivä ei käy selvästi ilmi")
        self.assertEqual(e["title"], "📌⚠️Tapahtuma: juhla")
        self.assertIn("⚠️ TARKISTA: päivä ei käy selvästi ilmi", e["notes"])

    def test_certain_event_has_no_marker(self):
        e = self.event("")
        self.assertEqual(e["title"], "📌Tapahtuma: juhla")
        self.assertNotIn("TARKISTA", e["notes"])


class SettingsDrivenTest(unittest.TestCase):
    """Mieltymykset ovat config.toml:ssa, ei koodissa."""

    def test_reminder_defaults_and_overrides(self):
        self.assertEqual(events.reminders({}), {"hour": 18, "exam_days": 2, "parents_days": (1, 3)})
        got = events.reminders({"reminders": {"hour": 20, "exam_days_before": 3, "parents_days_before": [2]}})
        self.assertEqual(got, {"hour": 20, "exam_days": 3, "parents_days": (2,)})

    def test_alarm_days_per_kind(self):
        rem = events.reminders({})
        self.assertEqual((events.alarm_days("event", rem), events.alarm_days("parents", rem), events.alarm_days("info", rem)),
                         ((1,), (1, 3), ()))

    def test_pe_subject_words_decide_which_lessons_count(self):
        lesson = lambda subj, day: Lesson(KIIA, day, "09:00", "10:00", subj)
        lessons = [lesson("Liikunta yhteinen a", "2026-11-03"), lesson("Gymnastik", "2026-11-04"), lesson("Matematiikka", "2026-11-05")]
        pe_item = {"info": info(), "kind": "pe", "week": date(2026, 11, 2), "weeknr": 45, "title": "uinti", "bring": [], "span": 1}
        got = lambda words: [i["date"].isoformat() for i in notices.expand_weeks([pe_item], lambda s, m: lessons, date(2026, 11, 2), words)]
        self.assertEqual(got(("liikunta",)), ["2026-11-03"])
        self.assertEqual(got(("liikunta", "gymnastik")), ["2026-11-03", "2026-11-04"])


if __name__ == "__main__":
    unittest.main()
