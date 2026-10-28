"""Kenen kalenteriin tapahtuma kuuluu. Tärkein turvaraja: tapahtuma ei saa koskaan päätyä väärän lapsen kalenteriin.

Jokaisella lapsella on oma kalenteri `Wilma <etunimi>`, ja tapahtuman kalenteri johdetaan aina sen oppilaan tiedoista,
jonka listalta tai viestistä asia tuli. Ennen kirjoitusta `verify_owners` tarkistaa vielä erikseen, että jokainen
tapahtuma on oikean lapsen kalenterissa, ja keskeyttää koko ajon, jos jokin ei täsmää. Lapsia voi olla useita.
Puhdasta logiikkaa: ei EventKitiä, ei verkkoa.
"""
from __future__ import annotations

CALENDAR_PREFIX = "Wilma"            # kalenterin nimi: "Wilma Kiia"


def first_name(student_name: str) -> str:
    parts = student_name.split()
    return parts[0] if parts else student_name


def calendar_name(student_name: str) -> str:
    """"Kiia Virtanen" -> "Wilma Kiia". Oppilaan nimen ensimmäinen sana."""
    return f"{CALENDAR_PREFIX} {first_name(student_name)}"


def check_unique_calendars(students: list) -> dict[str, str]:
    """oppilasnumero -> kalenterin nimi. Keskeyttää, jos kahden lapsen kalenterin nimi olisi sama (esim. sama etunimi),
    koska silloin tapahtumat voisivat päätyä väärän lapsen kalenteriin."""
    names = {s.number: calendar_name(s.name) for s in students}
    duplicates = sorted({n for n in names.values() if list(names.values()).count(n) > 1})
    if duplicates:
        raise SystemExit(f"KESKEYTETTY: usealla lapsella olisi sama kalenterin nimi ({', '.join(duplicates)}). "
                         "Tapahtumia ei kirjoiteta, ettei niitä sekoiteta.")
    return names


def verify_owners(events: list[dict], students: list) -> None:
    """Jokaisen tapahtuman kalenterin on oltava juuri sen lapsen kalenteri, jonka tiedoista tapahtuma syntyi."""
    names = check_unique_calendars(students)
    for e in events:
        if names.get(e["student"]) != e["calendar"]:
            raise SystemExit(f'KESKEYTETTY: tapahtuma "{e["title"]}" kuuluu oppilaalle, jonka kalenteri on '
                             f'"{names.get(e["student"], "tuntematon")}", mutta se oltaisiin kirjoittamassa kalenteriin '
                             f'"{e["calendar"]}". Mitään ei kirjoitettu.')


def owner_line(student_name: str) -> str:
    """Tapahtuman ensimmäinen rivi: kenen asia on, jotta se näkyy tapahtumasta myös yhdistetyssä kalenterinäkymässä."""
    return f"Oppilas: {first_name(student_name)}"
