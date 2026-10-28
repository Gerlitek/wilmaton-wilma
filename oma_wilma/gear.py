"""Mukaan otettavat varusteet: lista pakollisista, valinnaisista ja kielletyistä asioista.

Opettajan viesti voi luetella varusteita pitkästi ("luistimet, kypärä, ulkovaatetus (kevyt takki, ulkohousut, hanskat,
ohut pipo), halutessaan maila"). Kalenteritapahtuman otsikossa pitää näkyä lyhyesti kaikki tärkeä, myös se, että mailan
saa ottaa mukaan, ja kuvaukseen tulee koko lista yksityiskohtineen. Puhdasta logiikkaa.
"""
from __future__ import annotations

import re


def as_list(value) -> list[str]:
    """Siistii mallin vastauksen listaksi: hyväksyy listan tai yksittäisen tekstin, poistaa tyhjät ja toistot."""
    if not value:
        return []
    values = [value] if isinstance(value, str) else list(value)
    return list(dict.fromkeys(" ".join(str(v).split()) for v in values if str(v).strip()))


def short(item: str) -> str:
    """Lyhyt nimi otsikkoon: "ulkovaatetus (kevyt takki, hanskat)" -> "ulkovaatetus"."""
    return re.split(r"\s*[(:]", item, maxsplit=1)[0].strip() or item


def title_part(required: list[str], optional: list[str] | None = None, limit: int = 0) -> str:
    """Otsikkoon vain tärkein (ensimmäinen pakollinen) varuste lyhyesti: "luistimet". Otsikon pitää mahtua puhelimen pienelle
    näytölle, joten koko lista (muut pakolliset, valinnaiset kuten maila ja kielletyt) on kalenterin muistiinpanoissa
    (`note_lines`). Valinnaiset otsikkoon vain, jos pakollisia ei ole ("maila halutessa")."""
    if required:
        return short(required[0])
    return (", ".join(short(x) for x in optional) + " halutessa") if optional else ""


def note_lines(label: str, required: list[str], optional: list[str], forbidden: list[str]) -> list[str]:
    """Kuvauksen rivit: koko lista yksityiskohtineen. label on asia, jota varusteet koskevat (esim. "Luistelu")."""
    lines = []
    if required:
        lines.append(f"Ota mukaan ({label}): " + "; ".join(required))
    if optional:
        lines.append(f"Halutessaan voi ottaa ({label}): " + "; ".join(optional))
    if forbidden:
        lines.append(f"Ei mukaan ({label}): " + "; ".join(forbidden))
    return lines


def fits(title: str, limit: int) -> bool:
    """Onko mallin kirjoittama lyhyt otsikko kelvollinen (ei tyhjä, mahtuu puhelimen näytölle)?"""
    return bool(title.strip()) and len(title.strip()) <= limit
