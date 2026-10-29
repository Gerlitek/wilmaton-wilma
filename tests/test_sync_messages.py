"""Viestien synkka (sync_messages.py): yhteiset viestit, käsiteltävien valinta, vanhentuneet, asetukset ja Ollama vain paikallisesti."""
import unittest
from datetime import date
from unittest import mock

from oma_wilma import models, config, messages, notices, ollama, organizers, sync_messages
from oma_wilma.models import Student
from .helpers import KIIA, ONNI, info, SKATING


class SharedMessageTest(unittest.TestCase):
    def both(self, mid=7):
        return [info(student=KIIA, mid=mid), info(student=ONNI, mid=mid)]

    def test_shared_message_kept_for_older_only(self):
        got = sync_messages.dedupe_shared(self.both(), ["Kiia"])
        self.assertEqual([(i.student.name, i.id) for i in got], [("Kiia Virtanen", 7)])

    def test_reference_by_number_or_name(self):
        self.assertEqual(sync_messages.dedupe_shared(self.both(), ["1002"])[0].student.name, "Onni Virtanen")
        self.assertEqual(sync_messages.dedupe_shared(self.both(), ["onni"])[0].student.name, "Onni Virtanen")

    def test_own_messages_of_younger_kept(self):
        infos = self.both(7) + [info(student=ONNI, mid=8)]
        got = sync_messages.dedupe_shared(infos, ["Kiia"])
        self.assertEqual(sorted((i.student.name.split()[0], i.id) for i in got), [("Kiia", 7), ("Onni", 8)])

    def test_no_setting_no_dedupe(self):
        self.assertEqual(len(sync_messages.dedupe_shared(self.both(), None)), 2)

    def test_kept_message_remembers_siblings(self):
        (got,) = sync_messages.dedupe_shared(self.both(), ["Kiia"])
        self.assertEqual(got.also_for, ("Onni Virtanen",))
        self.assertEqual(sync_messages.dedupe_shared([info(student=KIIA, mid=7)], ["Kiia"])[0].also_for, ())

    def test_copy_with_other_id_but_same_sender_subject_time_is_shared(self):
        at = "2026-10-26T15:02:00+02:00"
        mk = lambda st, mid, when=at: messages.MessageInfo(st, mid, "Aihe", date(2026, 10, 26), "Opettaja", True, 0, when)
        got = sync_messages.dedupe_shared([mk(KIIA, 1), mk(ONNI, 2)], ["Kiia"])
        self.assertEqual([i.student.name for i in got], ["Kiia Virtanen"])
        got = sync_messages.dedupe_shared([mk(KIIA, 1), mk(ONNI, 2, "2026-10-26T12:50:00+02:00")], ["Kiia"])
        self.assertEqual(len(got), 2)                       # eri aika = eri viesti

    def test_three_children_priority_order_decides_owner(self):
        mk = lambda st: messages.MessageInfo(st, 9, "Aihe", date(2026, 10, 26), "Opettaja", True, 0)
        aino = Student("1003", "Aino Virtanen")
        owner = lambda prio: sync_messages.dedupe_shared([mk(KIIA), mk(ONNI), mk(aino)], prio)[0].student.name.split()[0]
        self.assertEqual(owner(["Aino", "Kiia"]), "Aino")
        self.assertEqual(owner(["Onni", "Aino", "Kiia"]), "Onni")
        self.assertEqual(owner(["Kiia"]), "Kiia")

    def test_older_missing_from_group_keeps_one(self):
        self.assertEqual(len(sync_messages.dedupe_shared(self.both(), ["Aatos"])), 1)


class PendingTest(unittest.TestCase):
    today = date(2026, 11, 10)

    def test_processed_skipped_until_new_reply(self):
        a, b = info(sent=date(2026, 11, 5), mid=1, replies=0), info(sent=date(2026, 11, 5), mid=2, replies=1)
        state = {sync_messages.key(a): {"replies": 0}, sync_messages.key(b): {"replies": 0}}
        self.assertEqual([i.id for i in sync_messages.pending([a, b], state, 14, self.today)], [2])

    def test_old_messages_ignored(self):
        old = info(sent=date(2026, 10, 1))
        self.assertEqual(sync_messages.pending([old], {}, 14, self.today), [])

    def test_dry_run_opens_nothing(self):
        read = mock.Mock()
        with mock.patch.object(sync_messages, "load", return_value={}):
            items, _, count = sync_messages.collect([info(sent=date(2026, 11, 5))], 14, True, read=read, today=self.today)
        read.assert_not_called()
        self.assertEqual((items, count["would_open"]), ([], 1))

    def test_ollama_failure_not_marked_processed(self):
        def boom(prompt, schema):
            raise ollama.OllamaError("kaatui")
        with mock.patch.object(sync_messages, "load", return_value={}):
            _, state, count = sync_messages.collect([info(sent=date(2026, 11, 5))], 14, False, ask=boom,
                                                    read=lambda i: messages.Message(i, SKATING), today=self.today)
        self.assertEqual((state, count["failed"]), ({}, 1))


class ChildNotesTest(unittest.TestCase):
    def test_summaries_have_only_date_type_and_subject_not_the_teachers_text(self):
        data = {"students": [{"student": {"studentNumber": "1001", "name": "Kiia"},
                              "notes": [{"date": "2026-10-20", "typeLabel": "Poissaolo", "subject": "Matematiikka",
                                         "note": "yksityinen opettajan teksti"}]}]}
        got = models.parse_note_summaries(data)
        self.assertEqual(got, {"1001": ["2026-10-20 Poissaolo (Matematiikka)"]})
        self.assertNotIn("yksityinen", str(got))

    def test_notes_are_fetched_once_per_student_and_given_to_the_model(self):
        seen, fetched = [], []
        def ask(prompt_text, schema):
            seen.append(prompt_text)
            return {"items": []}
        def fetch(number):
            fetched.append(number)
            return []
        infos = [info(sent=date(2026, 11, 5), mid=1), info(sent=date(2026, 11, 5), mid=2)]
        with mock.patch.object(sync_messages, "load", return_value={}):
            sync_messages.collect(infos, 14, False, ask=ask, read=lambda i: messages.Message(i, "viesti"),
                                  today=date(2026, 11, 6), child_notes=fetch)
        self.assertEqual(fetched, ["1001"])
        self.assertTrue(all("ei yhtään merkintää" in p for p in seen))

    def test_failed_notes_fetch_does_not_stop_interpretation(self):
        seen = []
        with mock.patch.object(sync_messages, "load", return_value={}):
            sync_messages.collect([info(sent=date(2026, 11, 5))], 14, False, ask=lambda p, s: seen.append(p) or {"items": []},
                                  read=lambda i: messages.Message(i, "viesti"), today=date(2026, 11, 6), child_notes=lambda n: None)
        self.assertEqual(len(seen), 1)
        self.assertNotIn("omat viimeaikaiset merkinnät", seen[0])


class StaleEventsTest(unittest.TestCase):
    today = date(2026, 11, 2)

    def state(self):
        return {"a": {"sources": ["1:7"], "date": "2026-11-04"},          # uusi tulkinta ei enää tuota: poistetaan
                "b": {"sources": ["1:7"], "date": "2026-11-04"},          # tuotetaan yhä
                "c": {"sources": ["1:7", "1:8"], "date": "2026-11-04"},   # toinen lähdeviesti ei ollut mukana
                "d": {"sources": ["1:7"], "date": "2026-10-20"},          # mennyt
                "e": {"date": "2026-11-04"}}                              # vanha, ei lähteitä

    def test_only_unproduced_future_events_from_reprocessed_messages(self):
        self.assertEqual(sync_messages.stale_uids(self.state(), {"b"}, {"1:7"}, self.today), ["a"])

    def test_info_events_are_never_removed(self):
        state = {"i": {"sources": ["1:7"], "date": "2026-11-04", "kind": "info"}}
        self.assertEqual(sync_messages.stale_uids(state, set(), {"1:7"}, self.today), [])

    def test_nothing_removed_when_message_not_processed(self):
        self.assertEqual(sync_messages.stale_uids(self.state(), set(), set(), self.today), [])


class ParseTest(unittest.TestCase):
    def test_list_and_read(self):
        data = {"students": [{"student": {"studentNumber": "1", "name": "Kiia"},
                              "messages": [{"wilmaId": 7, "subject": "Hei", "sentAt": "2026-11-02T10:00:00+02:00",
                                            "senderName": "Aho", "unread": True, "replyCount": 1}]}]}
        (i,) = messages.parse_message_list(data)
        self.assertEqual((i.id, i.sent, i.reply_count, i.unread), (7, date(2026, 11, 2), 1, True))
        m = messages.parse_message(i, {"message": {"content": "Päämessu", "replies": [{"content": "Vastaus"}]}})
        self.assertEqual(m.text, "Päämessu\n\nVastaus")
        self.assertNotIn("Päämessu", repr(m))


class SettingsFileTest(unittest.TestCase):
    def test_missing_file_means_defaults(self):
        from oma_wilma import config
        self.assertEqual(config.settings(__import__("pathlib").Path("/nonexistent/config.toml")), {})

    def test_reads_messages_and_ollama_sections(self):
        import tempfile
        from pathlib import Path
        from oma_wilma import config
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "config.toml")
            f.write_text('[messages]\nolder_student = "Kiia"\nexternal_organizers = ["seurakunta"]\n[ollama]\nmodel = "x"\n')
            c = config.settings(f)
        self.assertEqual(c["messages"]["older_student"], "Kiia")
        self.assertEqual(ollama.settings(c), ("http://localhost:11434", "x"))
        self.assertEqual(organizers.organizer_hints(c["messages"]["external_organizers"]), ["seurakunta"])


class OllamaLocalOnlyTest(unittest.TestCase):
    def test_remote_url_refused(self):
        for url in ("http://example.com:11434", "https://api.openai.com", "http://192.168.1.5:11434"):
            with self.assertRaises(ollama.OllamaError):
                ollama.settings({"ollama": {"url": url}})

    def test_local_urls_ok(self):
        for url in ("http://localhost:11434", "http://127.0.0.1:11434"):
            self.assertEqual(ollama.settings({"ollama": {"url": url}})[0], url)

    def test_chat_refuses_before_sending(self):
        with mock.patch("urllib.request.urlopen") as op:
            with self.assertRaises(ollama.OllamaError):
                ollama.chat_json("salainen", {}, {"ollama": {"url": "http://example.com"}})
        op.assert_not_called()


if __name__ == "__main__":
    unittest.main()
