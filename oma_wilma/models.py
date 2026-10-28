"""Oma, vakaa muoto wilmai:n JSONista. Muutokset CLI:n muodossa korjataan vain täällä."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from . import bridge


@dataclass(frozen=True)
class Student:
    number: str
    name: str
    wilma: str | None = None


def is_student(student: Student, ref: str | None) -> bool:
    """Viite on oppilasnumero tai nimen alku (kirjainkoolla ei väliä), esim. "Kiia" tai "1001"."""
    ref = (ref or "").strip().casefold()
    return bool(ref) and (ref == student.number.casefold() or student.name.casefold().startswith(ref))


@dataclass(frozen=True)
class Exam:
    student: Student
    date: str  # YYYY-MM-DD
    time: str | None  # "08:30", jos koulu antaa
    subject: str
    name: str
    topic: str | None  # mitä luetaan kokeeseen
    teacher: str | None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def parse_student(raw: dict[str, Any]) -> Student:
    return Student(number=str(raw.get("studentNumber", "")), name=str(raw.get("name", "")), wilma=raw.get("wilma"))


def parse_students(data: dict[str, Any]) -> list[Student]:
    return [parse_student(s) for s in data.get("students", [])]


def parse_exams(data: dict[str, Any]) -> list[Exam]:
    """`wilma exams --json`: { students: [{ student, exams: [{ date, time, subject, name, topic, teacher }] }] }"""
    exams: list[Exam] = []
    for entry in data.get("students", []):
        student = parse_student(entry.get("student", {}))
        for e in entry.get("exams", []):
            exams.append(
                Exam(
                    student=student,
                    date=str(e.get("date", "")),
                    time=e.get("time") or None,
                    subject=str(e.get("subject") or e.get("name") or ""),
                    name=str(e.get("name") or ""),
                    topic=e.get("topic") or None,
                    teacher=e.get("teacher") or None,
                )
            )
    return sorted(exams, key=lambda x: (x.date, x.time or "", x.student.name))


def students() -> list[Student]:
    return parse_students(bridge.run(["students"]))


def upcoming_exams(student: str | None = None, limit: int = 20) -> list[Exam]:
    args = ["exams", "--limit", str(limit)]
    if student:
        args += ["--student", student]
    return parse_exams(bridge.run(args))


@dataclass(frozen=True)
class Lesson:
    student: Student
    date: str  # YYYY-MM-DD
    start: str | None
    end: str | None
    subject: str


def parse_schedule(data: dict[str, Any]) -> list[Lesson]:
    """`wilma schedule --json`: { students: [{ student, lessons: [{ date, start, end, subject, ... }] }] }"""
    out: list[Lesson] = []
    for entry in data.get("students", []):
        student = parse_student(entry.get("student", {}))
        for l in entry.get("lessons", []):
            out.append(Lesson(student, str(l.get("date", "")), l.get("start") or None, l.get("end") or None,
                              str(l.get("subject") or "")))
    return sorted(out, key=lambda x: (x.date, x.start or ""))


def week_schedule(student: str, monday: date, today: date | None = None) -> list[Lesson]:
    """Oppilaan viikon (maanantaista alkaen) tunnit. Tämä ja ensi viikko haetaan yhdellä kutsulla, muut päivä kerrallaan."""
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    if monday == this_monday:
        return parse_schedule(bridge.run(["schedule", "week", "--student", student]))
    if monday == this_monday + timedelta(weeks=1):
        return parse_schedule(bridge.run(["schedule", "next-week", "--student", student]))
    lessons: list[Lesson] = []
    for i in range(5):
        lessons += parse_schedule(bridge.run(["schedule", (monday + timedelta(days=i)).isoformat(), "--student", student]))
    return lessons


def parse_note_summaries(data: dict[str, Any]) -> dict[str, list[str]]:
    """`wilma notes --json`: { students: [{ student, notes: [{ date, subject, typeLabel, ... }] }] } -> oppilasnumero -> rivit
    "2026-10-20 Poissaolo (Matematiikka)". Vain päivä, merkinnän laji ja aine: opettajan vapaata tekstiä ei oteta mukaan."""
    out: dict[str, list[str]] = {}
    for entry in data.get("students", []):
        number = parse_student(entry.get("student", {})).number
        out[number] = [f"{n.get('date', '')} {n.get('typeLabel') or 'merkintä'}" + (f" ({n['subject']})" if n.get("subject") else "")
                       for n in entry.get("notes", [])]
    return out


def recent_note_summaries(student: str, days: int = 30) -> list[str] | None:
    """Oppilaan viimeaikaiset merkinnät (poissaolot, myöhästymiset ym.) tiivistettynä. None, jos haku ei onnistu: viestien tulkinta
    jatkuu silloin ilman tätä tietoa."""
    try:
        return parse_note_summaries(bridge.run(["notes", "--days", str(days), "--student", student])).get(student, [])
    except bridge.WilmaError:
        return None
