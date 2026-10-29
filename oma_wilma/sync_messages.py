"""Viestien synkka: uudet viestit -> paikallinen Ollama -> päivälliset ilmoitukset kalentereihin.

Kulku (`run`):
  1. listaa viestit kaikilta lapsilta ja yhdistä sisarusten yhteiset viestit (`dedupe_shared`)
  2. valitse käsiteltävät: uudet tai vastauksia saaneet, viimeiseltä N päivältä (`pending`)
  3. avaa ja tulkitse ne yksi kerrallaan, kukin sen lapsen nimissä, jonka listalta se tuli (`collect`)
  4. rakenna tapahtumat, tarkista omistajat ja kirjoita kalentereihin
Kokeet haetaan erikseen (`sync-exams`); tämä moduuli ei koske niihin.

data/messages.json muistaa käsitellyt viestit ({"<oppilas>:<viestin id>": {"replies": n}}), joten viestiä ei avata eikä
kysytä mallilta uudestaan, ellei siihen ole tullut uusia vastauksia (opettaja voi muuttaa päivää). Tilaan ei tallenneta
viestin sisältöä. Kuiva-ajo ei avaa viestejä eikä kirjoita mitään, ei myöskään tätä tilaa.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import date, timedelta

from . import messages as msgs
from . import models, ollama
from .config import ROOT, settings
from .notice_events import build_events, expand_weeks
from .notices import Ask, ask_model, drop_overridden, interpret
from .report import format_events

STATE = ROOT / "data" / "messages.json"
DEFAULT_DAYS = 10


# ---------------------------------------------------------------- käsiteltyjen viestien muisti

def load() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SystemExit(f"{STATE} on rikki. Tarkista se käsin, älä poista sitä (viestit avattaisiin uudelleen).")


def save(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, STATE)


def key(info: msgs.MessageInfo) -> str:
    """Viestin avain muistissa. Oppilas mukana: sama viesti voi olla usealla lapsella."""
    return f"{info.student.number}:{info.id}"


# ---------------------------------------------------------------- mitkä viestit käsitellään

def shared_priority() -> list[str]:
    """Lapset tärkein ensin (config.toml: [messages] shared_priority). Vanha asetus older_student toimii yhtenä."""
    m = settings().get("messages", {})
    return [str(x) for x in (m.get("shared_priority") or ([m["older_student"]] if m.get("older_student") else []))]


def dedupe_shared(infos: list[msgs.MessageInfo], priority: list[str] | None) -> list[msgs.MessageInfo]:
    """Koulu lähettää saman viestin usein usealle sisarukselle. Yhteinen viesti käsitellään kerran ja kuuluu listan
    ensimmäiselle lapselle, jolla se on (`priority`: numero tai nimen alku), jotta sama tapahtuma ei tule usean lapsen
    kalenteriin. Sama viesti = sama tunniste, tai (kopio eri tunnisteella) sama lähettäjä, aihe ja täsmällinen aika.
    Jos priority on tyhjä, mitään ei yhdistetä."""
    if not priority:
        return infos
    groups: list[list[msgs.MessageInfo]] = []
    group_of: dict[tuple, int] = {}
    for i in infos:
        ids = [("id", i.id)] + ([("same", i.sender, i.subject, i.sent_at)] if i.sent_at and i.subject else [])
        n = next((group_of[k] for k in ids if k in group_of), None)
        if n is None:
            groups.append([])
            n = len(groups) - 1
        groups[n].append(i)
        for k in ids:
            group_of.setdefault(k, n)

    def rank(i: msgs.MessageInfo) -> int:
        return next((n for n, ref in enumerate(priority) if models.is_student(i.student, ref)), len(priority))

    out = []
    for g in groups:
        best = min(g, key=rank)
        others = tuple(dict.fromkeys(i.student.name for i in g if i.student.number != best.student.number))
        out.append(replace(best, also_for=others) if others else best)
    return out


def pending(infos: list[msgs.MessageInfo], state: dict, days: int, today: date) -> list[msgs.MessageInfo]:
    """Viestit viimeiseltä `days` päivältä, joita ei ole käsitelty (tai joihin on tullut uusia vastauksia)."""
    cutoff = today - timedelta(days=days)
    return [i for i in infos if i.sent >= cutoff and state.get(key(i), {}).get("replies") != i.reply_count]


def stale_uids(state: dict, new_uids: set[str], processed: set[str], today: date) -> list[str]:
    """Aiemmin viesteistä luodut tulevat tapahtumat, joita uusi tulkinta ei enää tuota. Vain jos kaikki tapahtuman
    lähdeviestit käsiteltiin nyt (muuten toinen viesti voi yhä tarvita sitä). Kokeilla ja vanhoilla tapahtumilla ei
    ole lähteitä, joten niihin ei koskaan kosketa. Tiedoksi-merkintöjä (ulkopuolisten tilaisuudet) ei poisteta: tulkinta
    elää, ja kerran näkynyt tilaisuus ei saa kadota pois, vaikka malli ohittaisi sen seuraavalla kerralla."""
    return [u for u, v in state.items() if v.get("sources") and v.get("kind") != "info" and set(v["sources"]) <= processed
            and u not in new_uids and date.fromisoformat(v["date"]) >= today]


# ---------------------------------------------------------------- tulkinta

def collect(infos: list[msgs.MessageInfo], days: int, dry_run: bool, ask: Ask = ask_model,
            read=msgs.read_message, today: date | None = None, again: bool = False,
            explain: bool = False, child_notes=models.recent_note_summaries) -> tuple[list[dict], dict, dict]:
    """Avaa ja tulkitsee käsiteltävät viestit. Palauttaa (asiat, uusi muisti, laskurit). Tulostaa vain syitä ja
    määriä, ei viestin tekstiä. Jos tulkinta epäonnistuu, viestiä ei kirjata käsitellyksi (yritetään uudelleen)."""
    today = today or date.today()
    state = load()
    new_state = dict(state)
    items: list[dict] = []
    count = {"messages": 0, "none": 0, "rejected": 0, "failed": 0, "reasons": {}, "keys": set()}
    notes_cache: dict[str, list[str] | None] = {}
    pins: set = set()                              # (oppilas, viikko, laji), jolle jokin viesti on nimennyt päivän
    todo = pending(infos, {} if again else state, days, today)
    if dry_run:                                   # viestin avaaminen voi merkitä sen luetuksi: kuiva-ajo ei avaa mitään
        count["would_open"] = len(todo)
        return [], new_state, count
    for info in todo:
        who = f"viesti {info.id} ({info.student.name})"
        message = read(info)
        count["messages"] += 1
        trace: list[str] = []
        try:
            if info.student.number not in notes_cache:           # oppilaan omat merkinnät haetaan kerran per ajo
                notes_cache[info.student.number] = child_notes(info.student.number)
            found, notes = interpret(message, ask, today, explain, trace if explain else None,
                                     child_notes=notes_cache[info.student.number], pins=pins)
        except ollama.OllamaError as e:
            count["failed"] += 1
            print(f"  {who}: {e}")
            continue
        for line in trace + (notes if explain else []):
            print(f"  {who}: {line}")
        count["rejected"] += len(notes)
        for n in notes:
            count["reasons"][n] = count["reasons"].get(n, 0) + 1
        count["none"] += 0 if found or notes else 1
        items += found
        new_state[key(info)] = {"replies": info.reply_count}
        count["keys"].add(key(info))
    return drop_overridden(items, pins), new_state, count


# ---------------------------------------------------------------- koko ajo

def run(student: str | None, days: int, dry_run: bool, again: bool = False, explain: bool = False) -> int:
    from .calendar_export import export_events, load_state      # EventKit tarvitaan vasta viennissä

    problem = ollama.status()
    if problem:
        print(f"Ei voida jatkaa: {problem}")
        return 1

    # 1-2. Viestit kaikilta lapsilta (yhteiset tunnistetaan koko listasta), sitten vain pyydetty lapsi
    infos = dedupe_shared(msgs.recent_messages(), shared_priority())
    if student:
        infos = [i for i in infos if models.is_student(i.student, student)]

    # 3. Tulkinta
    items, new_state, count = collect(infos, days, dry_run, again=again, explain=explain)
    if dry_run:
        print(f"KUIVA-AJO: {count['would_open']} uutta viestiä avattaisiin ja tulkittaisiin paikallisella Ollamalla. "
              "Mitään ei avattu eikä kirjoitettu (viestin avaaminen voi merkitä sen luetuksi Wilmassa).")
        return 0

    # 4. Tapahtumat: viikot lukujärjestyksen päiville, saman päivän aiemmat tekstit mukaan
    previous = {u: v for u, v in load_state().items() if v.get("parts")}
    pe_words = tuple(str(w).lower() for w in settings().get("messages", {}).get("pe_subject_words", ["liikunta"]))
    events = build_events(expand_weeks(items, models.week_schedule, pe_words=pe_words), previous=previous,
                          reprocessed=count["keys"])
    print(format_events("VIESTIT", events))
    print(f"Viestejä käsitelty {count['messages']}, ilman ilmoituksia {count['none']}, hylättyjä tulkintoja "
          f"{count['rejected']}, epäonnistui {count['failed']}, tapahtumia {len(events)}.")
    if count["reasons"] and not explain:
        print("Hylkäyssyyt: " + "; ".join(f"{n} x {r}" for r, n in sorted(count["reasons"].items())))

    # 5. Vienti: ensin omistajatarkistus (jokainen tapahtuma oman lapsensa kalenteriin), sitten vanhentuneiden poisto.
    #    Uudelleentulkinta voi muuttaa lajia tai päivää: vanhat samoista viesteistä syntyneet tapahtumat, joita uusi
    #    tulkinta ei enää tuota, poistetaan (vain tulevat).
    stale = stale_uids(load_state(), {e["uid"] for e in events}, count["keys"], date.today())
    if events or stale:
        export_events(events, remove_uids=stale, students=models.students())
        if stale:
            print(f"Poistettu {len(stale)} vanhentunutta tapahtumaa (uusi tulkinta ei enää tuota niitä).")
    save(new_state)
    return 0
