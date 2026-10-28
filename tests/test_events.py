import unittest
from datetime import date, datetime

from oma_wilma import events, models
from oma_wilma.models import Exam, Student

KIIA = Student("1001", "Kiia Virtanen")
ONNI = Student("1002", "Onni Virtanen")


def exam(student=KIIA, day="2026-11-05", subject="Matematiikka", topic="Murtoluvut", time_=None, name="Koe 2", teacher="Aho"):
    return Exam(student, day, time_, subject, name, topic, teacher)


class TitleTest(unittest.TestCase):
    def test_title_starts_with_emoji_and_kind(self):
        e = events.exam_event(exam())
        self.assertEqual(e["title"], "📝Koe: Matematiikka – Murtoluvut")

    def test_title_without_topic(self):
        self.assertEqual(events.exam_event(exam(topic=None))["title"], "📝Koe: Matematiikka")

    def test_long_title_cut_at_word_boundary(self):
        t = events.exam_event(exam(topic="Murtoluvut, desimaaliluvut, prosentit ja suhteet sekä kertaus kappaleet 4-9"))["title"]
        self.assertTrue(t.endswith("…"))
        self.assertLessEqual(len(t), len("📝Koe: ") + events.MAX_TEXT)
        self.assertNotIn("kappaleet 4-9", t)

    def test_topic_and_teacher_in_notes(self):
        n = events.exam_event(exam(time_="08:30"))["notes"]
        for part in ("Aine: Matematiikka", "Luettava: Murtoluvut", "Kello: 08:30", "Opettaja: Aho"):
            self.assertIn(part, n)


class CalendarTest(unittest.TestCase):
    def test_calendar_per_student(self):
        self.assertEqual(events.exam_event(exam(KIIA))["calendar"], "Wilma Kiia")
        self.assertEqual(events.exam_event(exam(ONNI))["calendar"], "Wilma Onni")

    def test_alarm_two_days_before_at_18(self):
        self.assertEqual(events.exam_event(exam(day="2026-11-05"))["alarm"], datetime(2026, 11, 3, 18, 0))


class UidTest(unittest.TestCase):
    def test_uid_ignores_topic_and_teacher(self):
        a = events.exam_event(exam(topic="A", teacher="X"))["uid"]
        b = events.exam_event(exam(topic="B", teacher="Y"))["uid"]
        self.assertEqual(a, b)

    def test_uid_differs_by_student_day_subject(self):
        base = events.exam_event(exam())["uid"]
        self.assertNotEqual(base, events.exam_event(exam(ONNI))["uid"])
        self.assertNotEqual(base, events.exam_event(exam(day="2026-11-06"))["uid"])
        self.assertNotEqual(base, events.exam_event(exam(subject="Englanti"))["uid"])

    def test_same_subject_same_day_merged_not_duplicated(self):
        evs = events.build_exam_events([exam(topic="A"), exam(topic="B")])
        self.assertEqual(len(evs), 1)
        self.assertIn("A", evs[0]["notes"])
        self.assertIn("B", evs[0]["notes"])


class RemovalTest(unittest.TestCase):
    today = date(2026, 11, 1)

    def state(self):
        return {"a": {"kind": "exam", "date": "2026-11-05"}, "b": {"kind": "exam", "date": "2026-10-20"},
                "c": {"kind": "exam", "date": "2026-11-09"}}

    def test_only_future_missing_removed(self):
        self.assertEqual(events.plan_removals(self.state(), {"c"}, self.today), ["a"])

    def test_nothing_removed_when_all_present(self):
        self.assertEqual(events.plan_removals(self.state(), {"a", "b", "c"}, self.today), [])

    def test_past_never_removed(self):
        self.assertEqual(events.plan_removals(self.state(), set(), self.today), ["a", "c"])


if __name__ == "__main__":
    unittest.main()
