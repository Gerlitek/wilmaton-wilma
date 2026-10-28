"""Ulkopuolisen tahon tilaisuudet (esim. hyvinvointialueen tapahtuma) ovat lähinnä tiedoksi eivätkä koulun vanhempainilta.

Päätös on mallin: kehote kysyy suoraan "järjestääkö koulu tai opettaja tämän itse?" (`organized_by_school`) ja pyytää järjestäjän
nimen. Pieni malli vastaa kyllä/ei-kysymykseen luotettavammin kuin valitsee seitsemästä luokasta. Koodi ei arvaa järjestäjää
sanalistoilla: jos malli sanoo, ettei koulu järjestä tapahtumaa, vanhempainilta, tapahtuma tai muu asia muuttuu lajiksi
"tiedoksi". Asetuksen [messages] external_organizers nimet annetaan mallille vihjeenä kehotteessa, joten repoon ei tule
paikkakuntaa paljastavia sanoja. Tilaisuus ei häviä: se näkyy kalenterissa tiedoksi ilman muistutusta.
"""
from __future__ import annotations

import re

MAX_ORGANIZER = 24                                  # otsikkoon mahtuva järjestäjän nimi
SCHOOL_KINDS = {"parents", "event", "notice"}       # lajit, jotka ovat tiedoksi, jos järjestäjä ei ole koulu


def organizer_hints(extra: list[str] | None = None) -> list[str]:
    """Käyttäjän antamat ulkopuolisten järjestäjien nimet vihjeeksi mallille (config.toml: [messages] external_organizers)."""
    if extra is None:
        from .config import settings
        extra = settings().get("messages", {}).get("external_organizers", [])
    return [str(w).strip() for w in extra if str(w).strip()]


def classify(kind: str, organized_by_school: bool | None, organizer: str = "") -> tuple[str, str | None]:
    """Palauttaa (laji, ulkopuolinen järjestäjä tai None).

    Laji tulee mallilta. Se muuttuu tiedoksi (`info`) vain, jos malli itse sanoi lajin olevan "tiedoksi" tai sanoi, ettei koulu
    järjestä tätä (`organized_by_school` on false). Jos malli ei vastannut kysymykseen (None), lajia ei muuteta. Ulkopuolisen
    järjestäjän nimi näytetään otsikossa, jottei tilaisuus näytä koulun omalta."""
    outside = kind == "info" or (organized_by_school is False and kind in SCHOOL_KINDS)
    if not outside:
        return kind, None
    name = " ".join(re.split(r"[,;/]| ja ", organizer, maxsplit=1)[0].split())[:MAX_ORGANIZER].strip()   # useasta vain ensimmäinen
    return "info", (name[:1].upper() + name[1:]) or None
