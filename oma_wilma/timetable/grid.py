"""Lukujärjestys tulostettavaksi: viikon tunnit ruudukoksi (rivit = oppitunnit ja välitunnit, sarakkeet = ma–pe).

Puhdasta logiikkaa, joten testattavissa ilman Wilmaa. Haku on models.week_schedule:ssa, piirto timetable_pdf.py:ssä.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..models import Lesson, Student

WEEKDAYS = ["Maanantai", "Tiistai", "Keskiviikko", "Torstai", "Perjantai"]
DEFAULT_SUPPORT_WORDS = ["tukiopetus", "ryhmäkohtainen tuki"]
WORLDVIEW_SUBJECT = "Uskonto/Elämänkatsomustieto"
WORLDVIEW = {"religion": "Uskonto", "ethics": "ET", "both": "Uskonto / ET"}  # --worldview: kumpi nimi näytetään
WORLDVIEW_ALIASES = {"uskonto": "religion", "et": "ethics", "molemmat": "both"}
DEFAULT_NAMES = {"Suomen kieli ja kirjallisuus": "Äidinkieli", WORLDVIEW_SUBJECT: WORLDVIEW["religion"]}

# Viikonpäivät komentoriviltä: suomeksi (ma, tiistai ...), englanniksi (mon, tue ...) tai numerona (1 = maanantai).
_DAY_WORDS = [("maanantai", "monday"), ("tiistai", "tuesday"), ("keskiviikko", "wednesday"), ("torstai", "thursday"),
              ("perjantai", "friday")]


@dataclass(frozen=True)
class Entry:
    name: str
    pe: bool = False
    support: bool = False


@dataclass
class Row:
    kind: str            # "lesson", "break" tai "lunch"
    start: str           # "08:35"
    end: str
    lessons: list[list[Entry]] = field(default_factory=list)  # oppitunti: päivittäiset tunnit (ma–pe)
    at_school: list[bool] = field(default_factory=list)       # välitunti: onko lapsi silloin koulussa (ma–pe)


@dataclass
class Timetable:
    student: Student
    monday: date
    rows: list[Row]
    pe_days: list[bool]
    snack_days: list[bool]
    empty_days: list[bool]
    starts_after_lunch: list[bool | None]  # None: ei tunteja tai ruokatauon aikaa ei tiedetä

    @property
    def first_name(self) -> str:
        return self.student.name.split()[0] if self.student.name.strip() else self.student.number


def _has_word(subject: str, words: Iterable[str]) -> bool:
    s = subject.casefold()
    return any(w.casefold() in s for w in words if w)


def short_name(subject: str, names: dict[str, str] | None = None) -> str:
    """Aineen nimi lapselle: "Kuvataide yhteinen a" -> "Kuvataide", "Englanti, A1" -> "Englanti". `names` korvaa nimiä
    (alkuperäinen tai siistitty nimi avaimena)."""
    names = {**DEFAULT_NAMES, **(names or {})}
    if subject in names:
        return names[subject]
    s = re.sub(r"\s+yhteinen\b.*$", "", subject, flags=re.IGNORECASE)
    s = re.sub(r",\s*[A-B]\d\b.*$", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"\s+\d+\s*lk\.?$", "", s, flags=re.IGNORECASE).strip()
    return names.get(s, s) or subject


def parse_days(text: str) -> set[int]:
    """"mon,wed" / "ma ke" / "1,3" -> viikonpäivien indeksit (0 = maanantai)."""
    out: set[int] = set()
    for part in re.split(r"[\s,;]+", text.strip().casefold()):
        if not part:
            continue
        if part.isdigit() and 1 <= int(part) <= 5:
            out.add(int(part) - 1)
            continue
        hits = [i for i, (fi, en) in enumerate(_DAY_WORDS)
                if (len(part) >= 2 and fi.startswith(part)) or (len(part) >= 3 and en.startswith(part))]
        if len(hits) != 1:
            raise ValueError(f"tuntematon viikonpäivä: {part!r} (mon tue wed thu fri tai ma ti ke to pe)")
        out.add(hits[0])
    return out


def parse_snack(rules: Iterable[str]) -> list[tuple[str | None, set[int]]]:
    """--snack-arvot: "ti,to" koskee kaikkia lapsia, "Kiia=ti,to" vain yhtä (oppilasnumero tai nimen alku)."""
    out: list[tuple[str | None, set[int]]] = []
    for rule in rules:
        ref, sep, days = rule.partition("=")
        out.append((ref.strip(), parse_days(days)) if sep else (None, parse_days(ref)))
    return out


def parse_lunch(text: str | None) -> tuple[str, str] | None:
    """"11:35-12:00" (tai 11.35–12.00) -> ("11:35", "12:00"). Tyhjä -> None."""
    if not text or not text.strip():
        return None
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})\s*", text)
    if not m:
        raise ValueError(f"ruokatunti muodossa 11:35-12:00, ei {text!r}")
    h1, m1, h2, m2 = m.groups()
    return f"{int(h1):02d}:{m1}", f"{int(h2):02d}:{m2}"


def parse_week(text: str, today: date | None = None) -> date:
    """"next"/"ensi" (oletus), "this"/"tama" tai päivämäärä YYYY-MM-DD -> viikon maanantai."""
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    key = (text or "next").strip().casefold()
    if key in ("next", "ensi", "seuraava"):
        return this_monday + timedelta(weeks=1)
    if key in ("this", "tama", "tämä", "nyt"):
        return this_monday
    try:
        day = date.fromisoformat(key)
    except ValueError:
        raise ValueError(f"viikko on next, this tai päivämäärä YYYY-MM-DD, ei {text!r}") from None
    return day - timedelta(days=day.weekday())


def build(lessons: Iterable[Lesson], student: Student, monday: date, *, drop_support: bool = False,
          support_words: Iterable[str] = DEFAULT_SUPPORT_WORDS, pe_words: Iterable[str] = ("liikunta",),
          names: dict[str, str] | None = None, breaks: str = "none", lunch: tuple[str, str] | None = None,
          snack_days: Iterable[int] = ()) -> Timetable:
    """Oppilaan viikon tunnit ruudukoksi. Samaan aikaan olevat tunnit (esim. luokassa oleva tukiopettaja) samaan ruutuun,
    varsinainen tunti ensin. `breaks`: "none", "lunch" (vain ruokailu) tai "all" (kaikki välitunnit);
    `lunch`-aikaan osuva väli on ruokailu."""
    support_words, pe_words = list(support_words), list(pe_words)
    days = [(monday + timedelta(days=i)).isoformat() for i in range(5)]
    by_slot: dict[tuple[str, str], list[list[Entry]]] = {}
    for lesson in lessons:
        if lesson.date not in days or not lesson.start or not lesson.end:
            continue
        support = _has_word(lesson.subject, support_words)
        if support and drop_support:
            continue
        entry = Entry(short_name(lesson.subject, names), _has_word(lesson.subject, pe_words), support)
        cell = by_slot.setdefault((lesson.start, lesson.end), [[] for _ in days])[days.index(lesson.date)]
        if all(e.name != entry.name for e in cell):
            cell.append(entry)
    for cells in by_slot.values():
        for cell in cells:
            cell.sort(key=lambda e: e.support)

    slots = sorted(by_slot)

    def day_has(i: int, test) -> bool:
        return any(by_slot[s][i] and test(s) for s in slots)

    rows: list[Row] = []
    latest_end = None
    for start, end in slots:
        is_lunch = bool(latest_end and lunch and lunch[0] < start and latest_end < lunch[1])
        if latest_end and latest_end < start and (breaks == "all" or (breaks == "lunch" and is_lunch)):
            b_start, b_end = latest_end, start
            at_school = []
            for i in range(5):
                before = day_has(i, lambda s: s[1] <= b_start)
                after = day_has(i, lambda s: s[0] >= b_end)
                # Ruokailuun tullaan myös suoraan kotoa, jos päivä alkaa heti ruokailun jälkeen.
                right_after = day_has(i, lambda s: s[0] == b_end)
                at_school.append(after and (before or (is_lunch and right_after)))
            rows.append(Row("lunch" if is_lunch else "break", b_start, b_end, at_school=at_school))
        rows.append(Row("lesson", start, end, lessons=by_slot[(start, end)]))
        latest_end = max(latest_end or end, end)

    snack = set(snack_days)
    firsts = [next((s[0] for s in slots if by_slot[s][i]), None) for i in range(5)]
    return Timetable(
        student=student, monday=monday, rows=rows,
        pe_days=[any(e.pe for s in slots for e in by_slot[s][i]) for i in range(5)],
        snack_days=[i in snack for i in range(5)],
        empty_days=[not day_has(i, lambda s: True) for i in range(5)],
        starts_after_lunch=[None if not lunch or not firsts[i] else firsts[i] >= lunch[0] for i in range(5)],
    )


def format_time(hhmm: str) -> str:
    """"08:35" -> "8.35" (suomalainen tapa)."""
    h, _, m = hhmm.partition(":")
    return f"{int(h)}.{m}" if h.isdigit() else hhmm
