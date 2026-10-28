"""Vie Wilma-tapahtumat iCloud-kalentereihin "Wilma <etunimi>" EventKitillä (macOS, pyobjc).

Kalenterit luodaan käsin Kalenterit-sovelluksessa (iCloud), eikä työkalu luo niitä itse. Jos jokin tarvittava kalenteri
puuttuu tai niitä on kaksi samannimistä, ajo keskeytyy ennen kuin mitään kirjoitetaan.

Aiemmin luodut tapahtumat tunnistetaan tiedoston data/state.json avulla (uid -> eventIdentifier), eikä kalenterin
tapahtumia lueta. Älä poista state.json:ia, muuten seuraava ajo luo tapahtumat uudelleen. Jokaisen tapahtuman
muistiinpanoissa on tunniste [wilma:<uid>] käsin siivousta varten.

TURVARAJA: kirjoitus, päivitys ja poisto kohdistuvat vain "Wilma ..."-kalentereihin, ja ennen jokaista tallennusta tai
poistoa tarkistetaan (guard_in_calendar), että tapahtuma kuuluu odotettuun kalenteriin.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, time

from .calendars import CALENDAR_PREFIX, verify_owners
from .config import ROOT
from .events import plan_removals

STATE = ROOT / "data" / "state.json"


def load_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SystemExit(f"{STATE} on rikki. Tarkista se käsin, älä poista sitä (syntyisi tuplia).")


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE)   # atominen: ei puolikasta tiedostoa


def guard_in_calendar(ev, cal) -> None:
    """Keskeyttää, jos tapahtuma ei ole juuri siinä kalenterissa, johon sen pitäisi kuulua. Kutsutaan ennen jokaista
    tallennusta ja poistoa."""
    c = ev.calendar()
    if c is None or c.calendarIdentifier() != cal.calendarIdentifier():
        where = c.title() if c is not None else "tuntematon"
        raise SystemExit(f'KESKEYTETTY: tapahtuma "{ev.title()}" on kalenterissa "{where}", ei kalenterissa '
                         f'"{cal.title()}". Mitään ei muutettu. Tarkista {STATE}.')


def _nsdate(dt: datetime):
    from Foundation import NSDate
    return NSDate.dateWithTimeIntervalSince1970_(dt.astimezone().timestamp())


def _open_calendars(names: set[str]):
    """Pyytää käyttöoikeuden ja palauttaa (store, {nimi: kalenteri}). Keskeyttää, ellei jokainen nimi ole yksiselitteinen."""
    from EventKit import EKEntityTypeEvent, EKEventStore

    store = EKEventStore.alloc().init()
    done, granted = threading.Event(), []

    def cb(ok, err):
        granted.append(ok)
        done.set()

    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(cb)
    else:
        store.requestAccessToEntityType_completion_(EKEntityTypeEvent, cb)
    done.wait(60)
    if not granted or not granted[0]:
        raise SystemExit("Kalenterin käyttöoikeutta ei annettu (Järjestelmäasetukset > Tietosuoja > Kalenterit).")

    found: dict[str, object] = {}
    for name in sorted(names):
        if not name.startswith(CALENDAR_PREFIX + " "):
            raise SystemExit(f'Kalenterin nimi "{name}" ei ala "{CALENDAR_PREFIX} ", kirjoitusta ei sallita.')
        cals = [c for c in store.calendarsForEntityType_(EKEntityTypeEvent)
                if c.title() == name and c.allowsContentModifications()]
        if not cals:
            raise SystemExit(f'Kalenteria "{name}" ei löydy. Luo se Kalenterit-sovelluksessa (iCloud). Mitään ei kirjoitettu.')
        if len(cals) > 1:
            raise SystemExit(f'Kalentereita nimeltä "{name}" on {len(cals)}. Nimeä ylimääräiset uudelleen.')
        found[name] = cals[0]
    return store, found


def _save_event(store, cal, state: dict, e: dict) -> None:
    """Luo tai päivittää yhden tapahtuman ja kirjaa sen tilaan heti (keskeytys ei jätä orpoja). Jos tunniste on aiemmin
    kirjattu toiselle kalenterille tai oppilaalle, ajo keskeytyy: tapahtumaa ei siirretä hiljaa lapselta toiselle."""
    from EventKit import EKAlarm, EKEvent

    old = state.get(e["uid"])
    if old and (old.get("calendar") != e["calendar"] or old.get("student", e["student"]) != e["student"]):
        raise SystemExit(f'KESKEYTETTY: tapahtuma {e["uid"]} on aiemmin kirjattu toiselle kalenterille/oppilaalle '
                         f'("{old.get("calendar")}"), ei kirjoiteta kalenteriin "{e["calendar"]}". Mitään ei muutettu.')
    ev = store.eventWithIdentifier_(old["id"]) if old else None
    if ev is None:
        ev = EKEvent.eventWithEventStore_(store)
        ev.setCalendar_(cal)
    guard_in_calendar(ev, cal)
    ev.setTitle_(e["title"])
    ev.setNotes_(f"{e['notes']}\n\n[wilma:{e['uid']}]")
    ev.setAllDay_(True)
    start = datetime.combine(e["date"], time(0))
    ev.setStartDate_(_nsdate(start))
    ev.setEndDate_(_nsdate(start))
    for al in list(ev.alarms() or []):
        ev.removeAlarm_(al)
    for a in ([e["alarm"]] if e["alarm"] else []) + list(e.get("extra_alarms") or []):
        ev.addAlarm_(EKAlarm.alarmWithAbsoluteDate_(_nsdate(a)))
    ok, err = store.saveEvent_span_commit_error_(ev, 0, True, None)
    if not ok:
        raise SystemExit(f"Tallennus epäonnistui: {err}")
    state[e["uid"]] = {"id": ev.eventIdentifier(), "kind": e["kind"], "origin": e.get("origin", ""), "calendar": e["calendar"],
                       "student": e["student"], "date": e["date"].isoformat(),
                       **({"parts": e["parts"], "sources": e.get("sources", [])} if e.get("parts") else {})}
    save_state(state)


def _remove_event(store, cals: dict, state: dict, uid: str) -> None:
    """Poistaa yhden tapahtuman kalenterista (jos se on yhä siellä) ja tilasta. Kalenteri tarkistetaan ennen poistoa."""
    entry = state[uid]
    ev = store.eventWithIdentifier_(entry["id"])
    if ev is not None:
        guard_in_calendar(ev, cals[entry["calendar"]])
        store.removeEvent_span_commit_error_(ev, 0, True, None)
    del state[uid]
    save_state(state)


def export_events(events: list[dict], remove_missing: bool = False, today: date | None = None,
                  remove_uids: list[str] = (), students: list | None = None) -> dict[str, int]:
    """Luo ja päivittää tapahtumat. remove_missing=True poistaa lisäksi tulevat koetapahtumat, joita Wilmassa ei enää
    ole (vain kun haku oli täydellinen). Palauttaa määrät."""
    if students is not None:                 # jokainen tapahtuma oikean lapsen kalenteriin, tai ei mitään
        verify_owners(events, students)
    state = load_state()
    removals = plan_removals(state, {e["uid"] for e in events}, today or date.today()) if remove_missing else []
    removals += [u for u in remove_uids if u in state and u not in removals]
    names = {e["calendar"] for e in events} | {state[u]["calendar"] for u in removals}
    if not names:
        return {"saved": 0, "removed": 0}
    store, cals = _open_calendars(names)
    for e in events:
        _save_event(store, cals[e["calendar"]], state, e)
    for uid in removals:
        _remove_event(store, cals, state, uid)
    return {"saved": len(events), "removed": len(removals)}


def remove_events(uids: list[str]) -> dict[str, int]:
    """Poistaa tämän työkalun luomat tapahtumat tunnisteella (esim. kaksoiskappale). Vain tilassa olevat, vain
    "Wilma "-kalentereista, ja kukin tarkistetaan (guard_in_calendar). Tuntemattomat tunnisteet ohitetaan."""
    state = load_state()
    known = [u for u in uids if u in state]
    if not known:
        return {"removed": 0, "unknown": len(uids)}
    store, cals = _open_calendars({state[u]["calendar"] for u in known})
    for uid in known:
        _remove_event(store, cals, state, uid)
    return {"removed": len(known), "unknown": len(uids) - len(known)}
