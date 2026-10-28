"""Ulkopuolisen tahon tilaisuudet (organizers.py): malli päättää, koodi vain näyttää järjestäjän ja antaa vihjeet mallille."""
import unittest
from datetime import date

from oma_wilma import organizers, prompt


class OrganizerTest(unittest.TestCase):
    def test_model_says_school_does_not_organize_so_it_becomes_info(self):
        self.assertEqual(organizers.classify("parents", False, "hyvinvointialue"), ("info", "Hyvinvointialue"))
        self.assertEqual(organizers.classify("event", False, "  seurakunta  "), ("info", "Seurakunta"))
        self.assertEqual(organizers.classify("notice", False, ""), ("info", None))

    def test_school_organized_parents_evening_stays_important(self):
        self.assertEqual(organizers.classify("parents", True, "koulu"), ("parents", None))

    def test_unanswered_question_changes_nothing(self):
        self.assertEqual(organizers.classify("parents", None, "hyvinvointialue"), ("parents", None))

    def test_models_own_info_category_is_kept(self):
        self.assertEqual(organizers.classify("info", True, "Seurakunta"), ("info", "Seurakunta"))

    def test_only_school_kinds_are_downgraded(self):
        for kind in ("pe", "photo", "trip"):
            self.assertEqual(organizers.classify(kind, False, "hyvinvointialue"), (kind, None))

    def test_only_the_first_of_several_organizers_is_used(self):
        self.assertEqual(organizers.classify("event", False, "Seurakunta, Esimerkkiyhdistys")[1], "Seurakunta")
        self.assertEqual(organizers.classify("event", False, "seurakunta ja kaupunki")[1], "Seurakunta")

    def test_long_organizer_name_is_cut(self):
        _, name = organizers.classify("info", False, "A" * 80)
        self.assertEqual(len(name), organizers.MAX_ORGANIZER)

    def test_hints_come_from_settings_and_ignore_blanks(self):
        self.assertEqual(organizers.organizer_hints(["seurakunta", " ", "kirjasto "]), ["seurakunta", "kirjasto"])
        self.assertEqual(organizers.organizer_hints([]), [])


class PromptHintTest(unittest.TestCase):
    def test_known_outsiders_are_given_to_the_model_as_a_hint_not_a_rule(self):
        text = prompt.make_prompt("viesti", date(2026, 11, 2), ["seurakunta", "kirjasto"])
        self.assertIn("Tunnettuja ulkopuolisia järjestäjiä: seurakunta, kirjasto.", text)
        self.assertNotIn("Tunnettuja ulkopuolisia", prompt.make_prompt("viesti", date(2026, 11, 2)))

    def test_prompt_asks_model_to_flag_uncertainty_and_write_the_short_title(self):
        text = prompt.make_prompt("viesti", date(2026, 11, 2))
        self.assertIn("uncertain:", text)
        self.assertIn("short_title:", text)
        self.assertIn("bring_optional:", text)
        self.assertIn("organized_by_school:", text)
        self.assertIn("timing_evidence:", text)
        self.assertIn("vapaamuotoisia", text)                                  # viestit ovat aina vapaamuotoisia
        self.assertIn("halutessaan voi ottaa myös", text)                      # valinnaiset varusteet millä tahansa sanoilla
        self.assertNotIn("viimeaikaiset merkinnät", text)                      # ei lapsen merkintöjä, jos tietoa ei ole

    def test_childs_own_notes_are_given_so_conditional_messages_can_be_judged(self):
        none = prompt.make_prompt("viesti", date(2026, 11, 2), child_notes=[])
        self.assertIn("ei yhtään merkintää", none)
        some = prompt.make_prompt("viesti", date(2026, 11, 2), child_notes=["2026-10-20 Poissaolo (Matematiikka)"])
        self.assertIn("2026-10-20 Poissaolo (Matematiikka)", some)
        self.assertIn("vain poissaolleita", some)


if __name__ == "__main__":
    unittest.main()
