"""Tapahtumalajit (KINDS), otsikot ja kokeiden tapahtumat (puhdasta logiikkaa: ei EventKitiä, ei verkkoa).

Tapahtuma on dict: uid, kind, origin, calendar, student, title, date, notes, alarm. Vienti kalenteriin on calendar_export.py:ssä,
kalenterin valinta calendars.py:ssä ja viestien tapahtumat notice_events.py:ssä.

Otsikon muoto on `<emoji><Laji>: <teksti>`, ja emoji on aina sama lajille. Emojin jälkeen ei ole välilyöntiä (tilaa
säästääkseen, kuten Daisy-kalenterissa). Laji ja aihe tulevat otsikon alkuun, jotta puhelimen pieneltä näytöltä
nähdään heti, mistä on kyse. Uusi laji (esim. läksy, retki) lisätään KINDS-tauluun, ja sen jälkeen otsikko, kuvaus ja
muistutus tehdään samalla tavalla.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta

from .calendars import calendar_name, owner_line
from .models import Exam

DEFAULT_REMINDER_HOUR = 18
EXAM_REMINDER_DAYS = 2               # kirja ehditään pyytää kotiin ja asia lukea
MAX_TEXT = 34                        # otsikon teksti: mahtuu puhelimen pienelle näytölle; pidempi katkaistaan sanan rajalla, tiedot ovat muistiinpanoissa

# laji -> (emoji, otsikon etuliite)
KINDS = {
    "exam": ("📝", "Koe"),
    "pe": ("🎽", ""),                         # laji kertoo itse (Luistelu: luistimet), ei etuliitettä
    "photo": ("📸", "Kuvaus"),
    "trip": ("🚌", "Retki"),
    "event": ("📌", "Tapahtuma"),
    "parents": ("👪", "Vanhempainilta"),    # koulun oma vanhempainilta: tärkeä, kaksi muistutusta
    "info": ("ℹ️", "Tiedoksi"),              # ulkopuolisen tahon tilaisuus (esim. hyvinvointialue): ei muistutusta
    "notice": ("❗", "Huom"),
}


def fit(text: str, limit: int = MAX_TEXT) -> str:
    """Katkaisee sanan rajalla ja lisää …, jos teksti ei mahdu."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0] if " " in text[: limit - 1] else text[: limit - 1]
    return cut.rstrip(" ,;:–-") + "…"


def reminders(cfg: dict | None = None) -> dict:
    """Muistutusajat: oletukset tai config.toml:n [reminders] (hour, exam_days_before, parents_days_before)."""
    from .config import settings
    r = (settings() if cfg is None else cfg).get("reminders", {})
    return {"hour": int(r.get("hour", DEFAULT_REMINDER_HOUR)), "exam_days": int(r.get("exam_days_before", EXAM_REMINDER_DAYS)),
            "parents_days": tuple(int(n) for n in r.get("parents_days_before", (1, 3)))}


def alarm_days(kind: str, rem: dict) -> tuple[int, ...]:
    """Montako päivää ennen tapahtumaa muistutus tulee: vanhempainillalle useampi, tiedoksi ei lainkaan, muille edellisenä iltana."""
    return {"parents": rem["parents_days"], "info": ()}.get(kind, (1,))


def mark_uncertain(title: str, kind: str) -> str:
    """⚠️ heti lajin emojin jälkeen: epävarma merkintä näkyy puhelimen pieneltä näytöltä."""
    emoji = KINDS[kind][0]
    return title.replace(emoji, emoji + "⚠️", 1)


SHARED_MARK = "👬"           # viesti tuli useammalle lapselle, mutta tapahtuma on vain yhden kalenterissa


def mark_shared(title: str, kind: str) -> str:
    """👬 heti lajin emojin jälkeen: sama viesti tuli sisaruksillekin, vaikka tapahtuma on vain tämän lapsen kalenterissa."""
    emoji = KINDS[kind][0]
    return title.replace(emoji, emoji + SHARED_MARK, 1)


def make_title(kind: str, text: str) -> str:
    """`<emoji><Laji>: <teksti>` ilman toistoa: "Retki: retki Nuuksioon" -> "Retki: Nuuksioon", "Vanhempainilta:
    vanhempainilta" -> "Vanhempainilta". Lajilla ilman etuliitettä (liikunta) otsikko on pelkkä teksti."""
    emoji, label = KINDS[kind]
    text = " ".join(text.split())
    if not label:
        return f"{emoji}{fit(text[:1].upper() + text[1:])}"
    if text.casefold() == label.casefold():
        return f"{emoji}{label}"
    stripped = re.sub(rf"^{re.escape(label)}(?![a-zåäö])[\s:–—-]*", "", text, count=1, flags=re.IGNORECASE)
    if stripped and stripped != text:                  # "Vanhempainilta: klo 18" -> "Klo 18" (etuliite lisätään kerran)
        text = stripped[:1].upper() + stripped[1:]
    return f"{emoji}{label}: {fit(text)}"


def _uid(student_number: str, kind: str, day: str, subject: str) -> str:
    """Tunniste ei riipu otsikosta, aiheesta tai opettajasta: niiden muuttuminen päivittää tapahtumaa eikä tee uutta."""
    return hashlib.sha1(f"{student_number}|{kind}|{day}|{subject.casefold()}".encode()).hexdigest()[:16]


def exam_event(exam: Exam, reminder_hour: int | None = None, days_before: int | None = None) -> dict:
    rem = reminders()
    reminder_hour = rem["hour"] if reminder_hour is None else reminder_hour
    days_before = rem["exam_days"] if days_before is None else days_before
    d = date.fromisoformat(exam.date)
    text = exam.subject + (f" – {exam.topic}" if exam.topic else "")
    lines = [owner_line(exam.student.name), f"Aine: {exam.subject}"]
    if exam.name and exam.name.casefold() != exam.subject.casefold():
        lines.append(f"Koe: {exam.name}")
    if exam.topic:
        lines.append(f"Luettava: {exam.topic}")
    if exam.time:
        lines.append(f"Kello: {exam.time}")
    if exam.teacher:
        lines.append(f"Opettaja: {exam.teacher}")
    lines.append("Muistutus: pyydä kirja kotiin ja muistuta lukemaan.")
    return {
        "uid": _uid(exam.student.number, "exam", exam.date, exam.subject),
        "kind": "exam", "origin": "koe",
        "calendar": calendar_name(exam.student.name),
        "student": exam.student.number,
        "title": make_title("exam", text),
        "date": d,
        "notes": "\n".join(lines),
        "alarm": datetime.combine(d - timedelta(days=days_before), time(reminder_hour)),
    }


def build_exam_events(exams: list[Exam], reminder_hour: int | None = None) -> list[dict]:
    """Yksi tapahtuma per koe. Jos sama tunniste tulee kahdesti (sama aine samana päivänä), jälkimmäinen yhdistetään
    ensimmäiseen kuvaukseen, jotta kumpikaan ei jää pois eikä tapahtuma tuplaannu."""
    out: dict[str, dict] = {}
    for e in exams:
        ev = exam_event(e, reminder_hour)
        if ev["uid"] in out:
            out[ev["uid"]]["notes"] += "\n\n" + ev["notes"]
        else:
            out[ev["uid"]] = ev
    return list(out.values())


def plan_removals(state: dict, wanted: set[str], today: date) -> list[str]:
    """Tulevat koetapahtumat, joita Wilmassa ei enää ole (peruttu tai siirretty toiselle päivälle).
    Menneitä ei koskaan poisteta: Wilma lakkaa näyttämästä koetta pian sen jälkeen, eikä sitä haluta pois kalenterista."""
    return [uid for uid, s in state.items()
            if s.get("kind") == "exam" and uid not in wanted and date.fromisoformat(s["date"]) > today]
