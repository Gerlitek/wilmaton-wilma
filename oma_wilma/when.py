"""Ajankohdan laskenta: mallin päättelemästä ajankohdasta (päivä, viikonpäivä, viikkonumerot, "ensi viikko") päiviksi tai
viikoiksi. Malli ymmärtää kielen, mutta laskee kalenteria huonosti, joten koodi laskee päivät itse. Koodi ei tulkitse viestin
kieltä: onko mallin päättelemä ajankohta viestin mukainen, tarkistaa mallin varmennuskierros (notices.py).

Puhdasta logiikkaa: ei verkkoa, ei tiedostoja.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai"]
WEEKDAYS_ALL = WEEKDAYS + ["lauantai", "sunnuntai"]
RELATIVE = {"tämä viikko": 0, "ensi viikko": 1}                # "ensi viikolla" -> viikkoja nykyisestä

_DATE_IN_QUOTE = re.compile(r"\d{1,2}\s*[./-]\s*\d{1,2}")      # "4.11." tai "4.11.2026" (ei pelkkä viikkonumero)
MAX_AHEAD_DAYS = 90                                # päivä enintään näin kaukana viestin lähetyksestä (vanhempainillat ilmoitetaan ajoissa)
MAX_WEEKS_BACK, MAX_WEEKS_AHEAD = 2, 13            # viikko lähetyksestä laskien


def week_monday(week: int, sent: date) -> date | None:
    """ISO-viikon (Suomen viikkonumerointi) maanantai. Vuosi valitaan niin, että viikko on lähellä lähetyspäivää."""
    candidates = []
    for year in (sent.year - 1, sent.year, sent.year + 1):
        try:
            candidates.append(date.fromisocalendar(year, week, 1))
        except ValueError:                         # vuodella ei ole viikkoa 53
            pass
    return min(candidates, key=lambda monday: abs((monday - sent).days)) if candidates else None


# ---------------------------------------------------------------- ajankohdan laskenta

def resolve_when(proposal: dict, sent: date) -> tuple[list[dict], str | None]:
    """Laskee mallin ehdotuksen kentistä (date, weekday, week/weeks, relative_week) päivät tai viikot.

    Palauttaa ([{"date": päivä} tai {"week": maanantai, "weeknr": n}, ...], ongelma). Ongelma on teksti, jos ajankohta
    ei selviä tai on epäuskottava; muuten None.

    Ensisijaisuus: tarkka päivämäärä, kun mallin lainaus sisältää päivämäärän (esim. 4.11.), tai kun viikonpäivää ei voi laskea > viikonpäivä +
    viikot/suhteellinen viikko (lasketaan koodissa) > pelkkä viikonpäivä (seuraava sellainen) > viikot > suhteellinen viikko."""
    sent_monday = sent - timedelta(days=sent.weekday())
    weekday = WEEKDAYS.index(proposal["weekday"]) if proposal.get("weekday") in WEEKDAYS else None
    raw_weeks = proposal.get("weeks") or ([proposal["week"]] if proposal.get("week") else [])      # `week` (yksi) tai `weeks`
    weeks = [w for w in raw_weeks if isinstance(w, int) and 1 <= w <= 53]
    relative = RELATIVE.get(proposal.get("relative_week") or "")

    exact: date | None = None
    if (proposal.get("date") or "").strip():
        try:
            exact = date.fromisoformat(proposal["date"].strip())
        except ValueError:
            return [], "päiväys ei ole kelvollinen"

    def one_day(day: date):
        near = sent <= day <= sent + timedelta(days=MAX_AHEAD_DAYS)
        return ([{"date": day}], None) if near else ([], "päivä ei ole lähiaikoina")

    def monday_of(week: int) -> date | None:
        monday = week_monday(week, sent)
        near = monday is not None and (sent - timedelta(weeks=MAX_WEEKS_BACK) <= monday
                                       <= sent + timedelta(weeks=MAX_WEEKS_AHEAD))
        return monday if near else None

    # Tarkka päivämäärä voittaa viikonpäivän, kun mallin lainaus viestistä sisältää numeroita (viesti kertoo päivämäärän, jolloin
    # mallin viikonpäivä voi olla väärin). Jos lainaus on sanoja tai viikkonumero (esim. "keskiviikkona"), mallin oma päiväys on todennäköisesti
    # laskettu väärin, ja päivä lasketaan viikonpäivästä ja viikosta.
    quoted_date = bool(_DATE_IN_QUOTE.search(proposal.get("timing_evidence") or ""))
    if exact is not None and (quoted_date or not (weekday is not None and (weeks or relative is not None))):
        if weekday is not None and exact.weekday() != weekday and not quoted_date:
            return [], "päiväys ja viikonpäivä ovat ristiriidassa"
        return one_day(exact)
    if weekday is not None and weeks:
        mondays = [monday_of(n) for n in weeks]
        if None in mondays:
            return [], "viikko ei ole lähiaikoina"
        return [{"date": m + timedelta(days=weekday)} for m in mondays], None
    if weekday is not None and relative is not None:
        return one_day(sent_monday + timedelta(weeks=relative, days=weekday))
    if weekday is not None:
        return one_day(sent + timedelta(days=(weekday - sent.weekday()) % 7))     # seuraava sellainen (tänään mukaan lukien)
    if weeks:
        targets = []
        for n in weeks:
            monday = monday_of(n)
            if monday is None:
                return [], "viikko ei ole lähiaikoina"
            targets.append({"week": monday, "weeknr": n})
        return targets, None
    if relative is not None:
        monday = sent_monday + timedelta(weeks=relative)
        return [{"week": monday, "weeknr": monday.isocalendar().week}], None
    return [], "ajankohta ei selvinnyt"


def describe_when(proposal: dict) -> str:
    """Mallin päättelemä ajankohta tiiviisti (vain --explain): ei viestin tekstiä."""
    parts = [str(proposal.get(k)) for k in ("date", "weekday", "relative_week") if proposal.get(k)]
    weeks = proposal.get("weeks") or ([proposal["week"]] if proposal.get("week") else [])
    if weeks:
        parts.append("vko " + ",".join(str(w) for w in weeks))
    return " ".join(parts) or "ei ajankohtaa"
