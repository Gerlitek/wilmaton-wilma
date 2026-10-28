"""Viestin tulkinta: opettajan viestistä päivälliset ilmoitukset (liikunnan varusteet, kuvauspäivä, retki, tapahtuma ...).

Työnjako: paikallinen Ollama ymmärtää kielen ja päättelee itse kaiken merkityksen (prompt.py): luokan, varusteet
(pakolliset, valinnaiset, kielletyt), järjestäjän, lyhyen otsikon ja ajankohdan. Jos jokin on epäselvää, malli sanoo sen
(`uncertain`), ja merkintä tulee kalenteriin tarkistusmerkinnällä. Koodi ei tulkitse viestin kieltä sanalistoilla: se vain
laskee päivät kalenterista (when.py), hylkää mahdottoman (ajankohtaa ei selviä, mennyt, liian kaukana) ja rakentaa
tapahtumat oikean lapsen kalenteriin (notice_events.py). Hylkäyksen syy kirjataan huomautukseksi; viestin sisältöä ei
kirjata mihinkään.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Callable

from . import ollama
from .gear import as_list
from .mentions import date_in_text, weekday_in_text
from .messages import Message
from .notice_events import build_events, expand_weeks      # noqa: F401  (julkinen rajapinta: tulkinta -> tapahtumat)
from .organizers import classify, organizer_hints
from .prompt import CATEGORY, SCHEMA, make_prompt
from .when import WEEKDAYS, describe_when, resolve_when

Ask = Callable[[str, dict], dict]


def ask_model(prompt: str, schema: dict) -> dict:
    return ollama.chat_json(prompt, schema)


def prefer_specific(items: list[dict]) -> list[dict]:
    """Viikon liikunta on yksi: jos samalle viikolle tulee useampi liikuntaasia, tarkimmin rajattu voittaa (asia, joka
    koskee vain tätä viikkoa, ohittaa asian, joka koskee useaa viikkoa). Rakenteellinen ristiriidan ratkaisu, ei kielen
    tulkintaa: laukeaa vain, jos mallin oma vastaus on ristiriitainen. Samalla tarkkuudella molemmat säilyvät, ja
    päiväkohtaisiin asioihin ei kosketa."""
    def weekly_pe(it: dict) -> bool:
        return "week" in it and it["kind"] == "pe"

    narrowest: dict[tuple, int] = {}
    for it in filter(weekly_pe, items):
        k = (it["info"].student.number, it["week"])
        narrowest[k] = min(narrowest.get(k, it["span"]), it["span"])
    return [it for it in items
            if not weekly_pe(it) or it["span"] == narrowest[(it["info"].student.number, it["week"])]]


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", str(text).replace("\u00a0", " ").lower())


def _quoted_from(evidence: str, text: str) -> bool:
    """Onko lainaus peräisin viestistä? Vapaamuotoisen viestin lainaus voi olla sanoiltaan ja välimerkeiltään hieman erilainen,
    joten verrataan sanoja eikä merkkijonoa: jokainen lainauksen sana (numerot täsmälleen, muut alun 5 kirjaimella taivutus
    huomioiden) löytyy viestistä."""
    wanted, have = _words(evidence), set(_words(text))
    if not wanted:
        return False

    def found(w: str) -> bool:
        if w in have:
            return True
        return len(w) >= 5 and not w.isdigit() and any(h.startswith(w[:5]) or w.startswith(h[:5]) for h in have if len(h) >= 5)

    return all(found(w) for w in wanted)


def _without_unfounded_day(proposal: dict, text: str, sent: date) -> dict:
    """Pieni malli keksii helposti tarkan päivän tai viikonpäivän, vaikka viesti puhuu vain viikosta. Tarkka päivä ja viikonpäivä
    hyväksytään vain, jos malli perustelee ne lainauksella viestistä (`timing_evidence`) tai viesti mainitsee ne itse missä
    tahansa muodossa (mentions.py). Muuten tarkkaa päivää ei käytetä, vaan asia jää viikkotasolle (liikunta sijoitetaan
    lukujärjestyksen liikuntatunneille). Mitään tiettyä sanaa tai muotoa ei vaadita."""
    day, weekday = proposal.get("date") or "", proposal.get("weekday") or ""
    if not (day or weekday):
        return proposal
    quoted = _quoted_from(proposal.get("timing_evidence") or "", text)
    if day:
        try:
            ok = quoted or date_in_text(date.fromisoformat(day.strip()), text, sent)
        except ValueError:
            ok = False
        day = day if ok else ""
    if weekday:
        weekday = weekday if weekday in WEEKDAYS and (quoted or weekday_in_text(WEEKDAYS.index(weekday), text)) else ""
    evidence = proposal.get("timing_evidence") if (day or weekday) else ""
    return {**proposal, "date": day, "weekday": weekday, "timing_evidence": evidence}


def _accept(proposal: dict, message: Message, today: date, explain: bool) -> tuple[list[dict], list[str]]:
    """Hyväksyy yhden mallin ehdotuksen kalenteriasioiksi. Palauttaa (asiat, hylkäysten syyt). Hylätään vain mahdoton:
    ei luokkaa tai nimeä, ajankohta ei selviä, mennyt tai liian kaukana."""
    category, title = (str(proposal.get(k) or "").strip() for k in ("category", "title"))
    if not title or category not in CATEGORY:
        return [], []
    proposal = _without_unfounded_day(proposal, message.text, message.info.sent)

    shown = f" [{describe_when(proposal)}]" if explain else ""
    targets, problem = resolve_when(proposal, message.info.sent)
    if problem:
        return [], [problem + shown]

    school = proposal.get("organized_by_school")
    kind, external = classify(CATEGORY[category], school if isinstance(school, bool) else None,
                              str(proposal.get("organizer") or ""))
    if external:
        title = f"{external} – {title}"            # ulkopuolisen tahon tilaisuus: järjestäjä näkyy otsikossa
    span = sum("week" in t for t in targets)       # montako viikkoa tämä asia koskee (tarkkuus, ks. prefer_specific)
    common = {
        "info": message.info, "kind": kind, "title": title, "span": span, "organizer": external,
        "short_title": str(proposal.get("short_title") or "").strip(),
        "bring": as_list(proposal.get("bring")), "optional": as_list(proposal.get("bring_optional")),
        "forbidden": as_list(proposal.get("do_not_bring")),
        "uncertain": " ".join(str(proposal.get("uncertain") or "").split()),
        "src": f"{message.info.student.number}:{message.info.id}",
    }
    items, notes = [], []
    for target in targets:
        if "date" in target and target["date"] < today:
            notes.append("päivä on jo mennyt" + shown)
        elif "week" in target and target["week"] + timedelta(days=6) < today:
            notes.append("viikko on jo mennyt" + shown)
        else:
            items.append({**common, **target})
    return items, notes


def interpret(message: Message, ask: Ask = ask_model, today: date | None = None, explain: bool = False,
              trace: list[str] | None = None, child_notes: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Palauttaa (asiat, huomautukset). Asia: info, kind, title, short_title, bring, optional, forbidden, uncertain ja
    joko date tai week+weeknr.

    Huomautukset kertovat vain syyn, eivät viestin sisältöä. explain=True lisää niihin mallin päättelemän ajankohdan
    (esim. "vko 44,45"). trace: jos annettu, jokaisesta mallin ehdottamasta asiasta lisätään rivi ja lopuksi tieto
    kalenteriin jääneiden määrästä. child_notes: oppilaan omat viimeaikaiset merkinnät (poissaolot ym.), joiden avulla malli
    ratkaisee, koskeeko ehdollinen viesti juuri tätä oppilasta."""
    today = today or date.today()
    proposals = ask(make_prompt(message.text, message.info.sent, organizer_hints(), child_notes), SCHEMA).get("items", [])
    items: list[dict] = []
    notes: list[str] = []
    for proposal in proposals:
        if trace is not None:
            gear = as_list(proposal.get("bring")) + [f"(halutessa) {x}" for x in as_list(proposal.get("bring_optional"))] \
                + [f"(ei) {x}" for x in as_list(proposal.get("do_not_bring"))]
            parts = [str(proposal.get(k) or "").strip() or "?" for k in ("category", "title")]
            unsure = str(proposal.get("uncertain") or "").strip()
            trace.append("malli ehdotti: " + " | ".join(parts + ([", ".join(gear)] if gear else []))
                         + f" [{describe_when(proposal)}]" + (f" EPÄVARMA: {unsure}" if unsure else ""))
        accepted, rejected = _accept(proposal, message, today, explain)
        items += accepted
        notes += rejected
    kept = prefer_specific(items)
    if trace is not None:
        trace.append(f"kalenteriin {len(kept)} asiaa")
    return kept, notes
