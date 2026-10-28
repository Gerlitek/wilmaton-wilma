"""Mainitseeko viesti tämän päivän tai viikonpäivän? Ainoa paikka, jossa on suomen kielen päivä- ja kuukausinimiä.

Pieni malli keksii helposti tarkan päivän tai viikonpäivän, vaikka vapaamuotoinen viesti puhuu vain viikosta. Tämä tarkistus
estää vain keksityn tarkkuuden: päivä hyväksytään, jos viesti mainitsee sen missä tahansa muodossa (4.11., 4. marraskuuta,
ke 4.11., huomenna), ja viikonpäivä, jos viestissä on sen nimi taivutettuna. Mitään tiettyä muotoa ei vaadita.
"""
from __future__ import annotations

import re
from datetime import date

WEEKDAY_STEMS = ["maanan", "tiista", "keskiv", "torsta", "perjan"]       # taivutukset: maanantaina, keskiviikon, torstaisin ...
ABBREVIATIONS = ["ma", "ti", "ke", "to", "pe"]
MONTHS = ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]
RELATIVE_DAYS = {"huomenna": 1, "ylihuomenna": 2, "tänään": 0}


def weekday_in_text(index: int, text: str) -> bool:
    """Onko viikonpäivä (0 = maanantai ... 4 = perjantai) viestissä nimellä tai lyhenteellä päiväyksen edessä (ke 4.11.)?"""
    low = text.lower()
    return WEEKDAY_STEMS[index] in low or bool(re.search(rf"(?<![a-zåäö]){ABBREVIATIONS[index]}\.?\s*\d", low))


def date_in_text(day: date, text: str, sent: date) -> bool:
    """Onko päivä viestissä: ISO-muodossa, päivän numerona ja kuukautena (numerona tai nimenä, myös välein "5.-6.11."), tai
    sanalla huomenna/ylihuomenna/tänään lähetyspäivästä laskettuna?"""
    low = text.lower()
    if day.isoformat() in low:
        return True
    has_day = re.search(rf"(?<!\d){day.day}(?!\d)", low)
    has_month = re.search(rf"\.\s?{day.month}(?!\d)", low) or f"{MONTHS[day.month - 1]}kuu" in low
    if has_day and has_month:
        return True
    return any(word in low and (day - sent).days == offset for word, offset in RELATIVE_DAYS.items())
