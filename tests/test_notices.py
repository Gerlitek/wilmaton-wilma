"""Viestin tulkinta (notices.py) ja varustelistat (gear.py)."""
import unittest
from datetime import date

from oma_wilma import gear, notices
from .helpers import info, msg, answer, item, SKATING, ITEM, WEEK_TEXT, WEEK_ITEM, SKATING_LIST, SKATING_PROPOSAL


class InterpretTest(unittest.TestCase):
    today = date(2026, 11, 2)

    def run_(self, text, *items, today=None, **kw):
        return notices.interpret(msg(text), answer(*items), today or self.today, **kw)

    def test_skating_item(self):
        items, notes = self.run_(SKATING, ITEM)
        self.assertEqual(notes, [])
        self.assertEqual([(i["kind"], i["date"], i["title"], i["bring"]) for i in items],
                         [("pe", date(2026, 11, 5), "luistelu", ["luistimet ja kypärä"])])

    def test_model_decides_time_expression_no_literal_phrase_needed(self):
        # viestissä lukee "vkot 44 ja 45" ja "ensi viikolla": malli päättelee viikot, koodi ei vaadi samaa sanaa
        m = msg(WEEK_TEXT, sent=date(2026, 10, 26))
        items, notes = notices.interpret(m, answer(WEEK_ITEM), date(2026, 10, 28))
        self.assertEqual(notes, [])
        self.assertEqual([i["week"] for i in items], [date(2026, 10, 26), date(2026, 11, 2)])

    def test_message_is_always_sent_to_model_with_send_date(self):
        seen = {}
        def ask(prompt, schema):
            seen["prompt"] = prompt
            return {"items": []}
        notices.interpret(msg("Muistakaa lukea kotona."), ask, self.today)
        self.assertIn("02.11.2026", seen["prompt"])
        self.assertIn("Muistakaa lukea kotona.", seen["prompt"])


    def test_tomorrow_is_computed_from_send_date_even_if_model_says_next_week(self):
        m = msg("Huomenna ulkoliikuntaa👍", sent=date(2026, 10, 29))
        items, notes = notices.interpret(m, answer(item(relative_week="ensi viikko")), date(2026, 10, 29))
        self.assertEqual((notes, [i["date"] for i in items]), ([], [date(2026, 10, 30)]))

    def test_tomorrow_does_not_override_explicit_week(self):
        m = msg("Huomenna kuvaus, ensi viikolla ulkoliikuntaa", sent=date(2026, 10, 29))
        items, _ = notices.interpret(m, answer(item(relative_week="ensi viikko")), date(2026, 10, 29))
        self.assertEqual([i.get("week") for i in items], [date(2026, 11, 2)])

    def test_no_time_expression_rejected(self):
        items, notes = self.run_(SKATING, item())
        self.assertEqual((items, notes), ([], ["ajankohta ei selvinnyt"]))

    def test_past_day_reported_not_added(self):
        items, notes = self.run_(SKATING, ITEM, today=date(2026, 11, 6))
        self.assertEqual((items, notes), ([], ["päivä on jo mennyt"]))

    def test_past_week_reported(self):
        m = msg(WEEK_TEXT, sent=date(2026, 10, 26))
        items, notes = notices.interpret(m, answer(item(title="sisäliikunta", bring="sisäkengät", weeks=[44])), date(2026, 11, 9))
        self.assertEqual((items, notes), ([], ["viikko on jo mennyt"]))


    def test_photo_day(self):
        text = "Valokuvaus on keskiviikkona 4.11. Muistakaa siistit vaatteet."
        items, _ = self.run_(text, item(category="kuvaus", title="valokuvaus", bring="siistit vaatteet", date="2026-11-04", timing_evidence="4.11."))
        self.assertEqual((items[0]["kind"], items[0]["date"]), ("photo", date(2026, 11, 4)))

    def test_unknown_category_dropped(self):
        items, _ = self.run_(SKATING, item(category="arvaus", weekday="torstai"))
        self.assertEqual(items, [])



class FlexibleInterpretationTest(unittest.TestCase):
    """Malli päättää merkityksen: koodi ei vaadi, että sen sanat löytyvät viestistä kirjaimellisesti."""
    today = date(2026, 11, 2)

    def test_paraphrased_title_and_items_are_accepted(self):
        text = "Torstaina mennään ulos luistelemaan. Muistakaa varusteet."
        found, notes = notices.interpret(msg(text), answer(item(title="jääurheilu", bring=["luistimet"], weekday="torstai")), self.today)
        self.assertEqual((len(found), notes), (1, []))

    def test_explain_shows_only_the_models_time_not_the_message(self):
        _, notes = notices.interpret(msg(SKATING), answer(ITEM), date(2026, 11, 6), explain=True)
        self.assertEqual(notes, ["päivä on jo mennyt [torstai]"])

    def test_models_uncertainty_is_carried_to_the_item_and_the_trace(self):
        trace = []
        found, _ = notices.interpret(msg(SKATING), answer(item(weekday="torstai", uncertain="päivä ei käy selvästi ilmi")),
                                     self.today, trace=trace)
        self.assertEqual(found[0]["uncertain"], "päivä ei käy selvästi ilmi")
        self.assertIn("EPÄVARMA: päivä ei käy selvästi ilmi", trace[0])

    def test_impossible_is_still_rejected_by_the_code(self):
        _, notes = notices.interpret(msg(SKATING), answer(item()), self.today)          # ei ajankohtaa
        self.assertEqual(notes, ["ajankohta ei selvinnyt"])


class FreeFormTimingTest(unittest.TestCase):
    """Viestit ovat vapaamuotoisia. Tarkka päivä hyväksytään, kun malli lainaa viestistä sanat, joista se käy ilmi. Lainaus voi
    olla mitä tahansa sanoja: mitään tiettyä sanaa tai muotoa ei vaadita."""
    today = date(2026, 10, 26)
    text = "Liikunta vkot 44 ja 45: viikolla 44 luistellaan ja viikolla 45 ollaan sisällä. Luistimet mukaan."

    def targets(self, text=None, **kw):
        found, _ = notices.interpret(msg(text or self.text, sent=date(2026, 10, 26)),
                                     answer(item(title="luistelu", bring=["luistimet"], **kw)), self.today)
        return found

    def test_invented_weekday_without_a_quote_stays_week_level(self):
        found = self.targets(weekday="keskiviikko", weeks=[44], timing_evidence="")
        self.assertEqual([(i.get("week"), i.get("date")) for i in found], [(date(2026, 10, 26), None)])

    def test_invented_quote_that_is_not_in_the_message_stays_week_level(self):
        found = self.targets(weekday="keskiviikko", weeks=[44], timing_evidence="keskiviikon tunnilla")
        self.assertIn("week", found[0])

    def test_real_quote_keeps_the_exact_weekday(self):
        text = "Keskiviikon liikuntatunnilla on viikolla 44 luistelua. Luistimet mukaan."
        found = self.targets(text, weekday="keskiviikko", weeks=[44], timing_evidence="Keskiviikon liikuntatunnilla")
        self.assertEqual([i["date"] for i in found], [date(2026, 10, 28)])

    def test_quote_matching_ignores_case_spacing_and_nbsp(self):
        text = "Torstaina\u00a0 luistellaan  ulkona. Luistimet mukaan."
        found = self.targets(text, weekday="torstai", timing_evidence="torstaina luistellaan")
        self.assertEqual([i["date"] for i in found], [date(2026, 10, 29)])

    def test_the_quote_can_be_any_words_the_message_happens_to_use(self):
        text = "Hei! Retki on sitten ihan ensi viikon perjantaina, eväät mukaan"
        found, _ = notices.interpret(msg(text, sent=date(2026, 10, 26)), answer(item(
            category="retki", title="retki", bring=["eväät"], weekday="perjantai", relative_week="ensi viikko",
            timing_evidence="ensi viikon perjantaina")), self.today)
        self.assertEqual([i["date"] for i in found], [date(2026, 11, 6)])

    def test_school_question_decides_info_not_a_word_list(self):
        text = "Hyvinvointialue kutsuu vanhemmat iltaan 4.11. klo 18."
        proposal = item(category="vanhempainilta", title="vanhempainilta", bring=[], date="2026-11-04", timing_evidence="4.11.",
                        organized_by_school=False, organizer="hyvinvointialue")
        found, _ = notices.interpret(msg(text, sent=date(2026, 10, 26)), answer(proposal), self.today)
        self.assertEqual((found[0]["kind"], found[0]["title"]), ("info", "Hyvinvointialue – vanhempainilta"))
        proposal["organized_by_school"] = True
        found, _ = notices.interpret(msg(text, sent=date(2026, 10, 26)), answer(proposal), self.today)
        self.assertEqual(found[0]["kind"], "parents")


class QuoteAndDateTest(unittest.TestCase):
    """Lainauksen tarkistus on sanatason (vapaamuotoinen viesti); numeroita sisältävä lainaus tarkoittaa päivämäärää."""
    sent = date(2026, 10, 26)

    def found(self, text, **kw):
        out, _ = notices.interpret(msg(text, sent=self.sent), answer(item(category="tapahtuma", title="juhla", bring=[], **kw)),
                                   self.sent)
        return out

    def test_quote_with_slightly_different_punctuation_still_counts(self):
        text = "Vanhempainilta on 4.11.2026 klo 18.00 koululla."
        found = self.found(text, date="2026-11-04", timing_evidence="4.11.2026 klo 18")
        self.assertEqual([i["date"] for i in found], [date(2026, 11, 4)])

    def test_explicit_date_beats_a_wrong_weekday_when_the_quote_has_digits(self):
        text = "Vanhempainilta 4.11.2026 klo 18 koululla."
        found = self.found(text, date="2026-11-04", weekday="torstai", week=45, timing_evidence="4.11.2026")
        self.assertEqual([i["date"] for i in found], [date(2026, 11, 4)])               # 4.11. on keskiviikko, ei torstai

    def test_weekday_quote_without_digits_computes_from_weekday_and_week(self):
        text = "Keskiviikkona viikolla 44 on juhla."
        found = self.found(text, date="2026-10-27", weekday="keskiviikko", week=44, timing_evidence="Keskiviikkona viikolla 44")
        self.assertEqual([i["date"] for i in found], [date(2026, 10, 28)])              # mallin oma päiväys oli väärin

    def test_quote_from_outside_the_message_is_not_accepted(self):
        text = "Viikolla 44 on juhla."
        found = self.found(text, weekday="keskiviikko", week=44, timing_evidence="keskiviikon aikana")
        self.assertEqual([(i.get("week"), i.get("date")) for i in found], [(date(2026, 10, 26), None)])


class GearTest(unittest.TestCase):
    def event(self, text=SKATING_LIST, proposal=SKATING_PROPOSAL):
        found, notes = notices.interpret(msg(text), answer(proposal), date(2026, 11, 2))
        self.assertEqual(notes, [])
        return notices.build_events(found)[0]

    def test_title_is_short_for_the_phone_and_the_stick_is_in_the_notes(self):
        self.assertEqual(self.event()["title"], "🎽Luistelu: luistimet")

    def test_notes_have_the_full_list_with_clothing_details_and_the_optional_stick(self):
        notes = self.event()["notes"]
        self.assertIn("Ota mukaan (luistelu): luistimet; kypärä; luistelemiseen sopiva ulkovaatetus "
                      "(kevyt takki, ulkohousut, hanskat, ohut pipo)", notes)
        self.assertIn("Halutessaan voi ottaa (luistelu): maila", notes)

    def test_no_stick_when_the_message_does_not_allow_it(self):
        text = "Luistelu torstaina. Ottakaa luistimet ja kypärä. Mailaa ei oteta mukaan."
        e = self.event(text, item(title="luistelu", weekday="torstai", bring=["luistimet", "kypärä"], do_not_bring=["maila"]))
        self.assertEqual(e["title"], "🎽Luistelu: luistimet")
        self.assertNotIn("halutessa", e["notes"])
        self.assertIn("Ei mukaan (luistelu): maila", e["notes"])


    def test_helpers(self):
        self.assertEqual(gear.as_list(["a", " a ", "", "b"]), ["a", "b"])
        self.assertEqual(gear.as_list("x"), ["x"])
        self.assertEqual(gear.as_list(None), [])
        self.assertEqual(gear.short("ulkovaatetus (kevyt takki, hanskat)"), "ulkovaatetus")
        self.assertEqual(gear.title_part(["luistimet", "kypärä"], []), "luistimet")
        self.assertEqual(gear.title_part([], ["maila"]), "maila halutessa")

    def test_string_bring_from_older_data_still_works(self):
        it = {"info": info(), "kind": "pe", "date": date(2026, 11, 5), "title": "uinti", "bring": "uimavarusteet"}
        self.assertEqual(notices.build_events([it])[0]["title"], "🎽Uinti: uimavarusteet")


if __name__ == "__main__":
    unittest.main()


class DayNamedOverridesWeekTest(unittest.TestCase):
    """Viestissä nimetty päivä (vaikka mennyt) ohittaa viikkotason liikunnan: ei luistelua lukujärjestyksen muille päiville."""

    def test_past_named_day_blocks_week_level_item_of_same_activity(self):
        from datetime import timedelta
        from .helpers import info
        i = info()
        monday = date(2026, 10, 26)
        week = {"info": i, "kind": "pe", "title": "luistelu", "week": monday, "weeknr": 44}
        other = {"info": i, "kind": "pe", "title": "sisäliikunta", "week": monday, "weeknr": 44}
        pins = {notices.pin_of({"info": i, "title": "luistelu", "date": monday + timedelta(days=2)})}
        self.assertEqual(notices.drop_overridden([week, other], pins), [other])
