"""Tulosteet: tapahtumat osioittain (KOKEET / VIESTIT) lapsen kalenterin mukaan ryhmiteltynä sekä kokeiden lista.

Tuloste ei sisällä viestin tekstiä, vain tiivistetyt otsikot, päivät, muistutukset ja viestin tunniste.
"""
from __future__ import annotations

from . import models


def describe_alarms(event: dict) -> str:
    """Muistutukset tulostetta varten: "muistutus 27.10. 18:00", useita tai "ei muistutusta"."""
    alarms = ([event["alarm"]] if event.get("alarm") else []) + list(event.get("extra_alarms") or [])
    if not alarms:
        return "ei muistutusta"
    return "muistutus " + ", ".join(f"{a:%d.%m. %H:%M}" for a in sorted(alarms))


def format_events(title: str, events: list[dict]) -> str:
    """Osion otsikko ja sen alla tapahtumat lapsen kalenterin mukaan ryhmiteltynä."""
    lines = [f"=== {title} ==="]
    if not events:
        return "\n".join(lines + ["(ei tapahtumia)"])
    for calendar in sorted({e["calendar"] for e in events}):
        lines.append(calendar)
        for e in sorted((x for x in events if x["calendar"] == calendar), key=lambda x: x["date"]):
            source = (f"  [viesti {', '.join(sorted({s.split(':')[1] for s in e['sources']}))}]"
                      if e.get("sources") else "")
            lines.append(f"  {e['date']}  {e['title']}  ({describe_alarms(e)}){source}")
    return "\n".join(lines)


def format_exams(exams: list[models.Exam]) -> str:
    """`exams`-komennon teksti: kokeet oppilaittain."""
    if not exams:
        return "(ei tulevia kokeita)"
    lines: list[str] = []
    current = None
    for e in exams:
        if e.student != current:
            current = e.student
            lines += ["", e.student.name] if lines else [e.student.name]
        when = f"{e.date} {e.time}" if e.time else e.date
        topic = f" – {e.topic}" if e.topic else ""
        teacher = f" ({e.teacher})" if e.teacher else ""
        lines.append(f"  {when}  {e.subject}{topic}{teacher}")
    return "\n".join(lines)
