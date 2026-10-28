"""Kokeiden synkka: Wilman tulevat kokeet -> kalenterit `Wilma <etunimi>`. Erillään viesteistä (`sync_messages.py`).

Kokeet tulevat Wilmasta rakenteisena tietona (ei tekoälyä), kunkin oppilaan omana listanaan. Tapahtuman kalenteri johdetaan
oppilaasta, ja ennen kirjoitusta tarkistetaan, että jokainen tapahtuma on oikean lapsen kalenterissa.
"""
from __future__ import annotations

from . import models
from .events import build_exam_events
from .report import format_events

SYNC_LIMIT = 200   # jos haku palauttaa näin monta, se voi olla katkaistu, eikä poistoja tehdä


def run(student: str | None, dry_run: bool) -> int:
    exams = models.upcoming_exams(student, SYNC_LIMIT)
    events = build_exam_events(exams)
    print(format_events("KOKEET", events))
    if dry_run:
        print(f"KUIVA-AJO, mitään ei kirjoitettu. {len(events)} tapahtumaa.")
        return 0

    from .calendar_export import export_events          # EventKit tarvitaan vasta viennissä

    complete = student is None and len(exams) < SYNC_LIMIT      # vain täydellisestä hausta saa päätellä, mikä on poistunut
    result = export_events(events, remove_missing=complete, students=models.students())
    print(f"Kalenteriin: {result['saved']} tapahtumaa, poistettu {result['removed']} (peruttu tai siirretty).")
    return 0
