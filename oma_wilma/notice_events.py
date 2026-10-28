"""Tarkistetuista asioista kalenteritapahtumat: viikot lukujärjestyksen päiville ja yksi tapahtuma per oppilas, laji ja päivä.

Tapahtuma on dict: uid, kind, origin ("viesti"), calendar, student, title, date, notes, alarm, extra_alarms, texts, lines,
sources. Puhdasta logiikkaa (lukujärjestys annetaan funktiona), joten testattavissa ilman Wilmaa.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from typing import Callable

from .calendars import calendar_name, owner_line
from .events import MAX_TEXT, alarm_days, make_title, mark_uncertain, reminders
from .gear import as_list, fits, note_lines, title_part
from .messages import MessageInfo

_WEEK_FIELDS = ("week", "weeknr", "span")


def _without_week(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in _WEEK_FIELDS}


def expand_weeks(items: list[dict], lessons_for: Callable[[str, date], list | None], today: date | None = None,
                 pe_words: tuple[str, ...] = ("liikunta",)) -> list[dict]:
    """Viikkoon sidotut asiat -> päiväasioiksi.

    Liikunta sijoitetaan oppilaan lukujärjestyksen liikuntatunneille (kellonaika mukaan, menneet päivät pois).
    Jos lukujärjestystä ei saada tai viikolla ei ole liikuntatuntia, asia tulee viikon maanantaille (tai tälle päivälle,
    jos maanantai on mennyt) otsikon perään merkittynä `(vko N)`. Muut lajit tulevat maanantaille.
    Lukujärjestys haetaan aina asian omalle oppilaalle. `pe_words`: sanat, joista liikuntatunti tunnistetaan aineen nimestä
    (config.toml: [messages] pe_subject_words)."""
    today = today or date.today()
    cache: dict[tuple[str, date], list | None] = {}

    def lessons(item: dict) -> list:
        if item["kind"] != "pe":
            return []
        key = (item["info"].student.number, item["week"])
        if key not in cache:
            try:
                cache[key] = lessons_for(*key)
            except Exception:                      # lukujärjestyksen haku ei saa kaataa viestien käsittelyä
                cache[key] = None
        return [l for l in (cache[key] or []) if any(w in l.subject.lower() for w in pe_words) and l.date >= today.isoformat()]

    out: list[dict] = []
    for item in items:
        if "week" not in item:
            out.append(item)
            continue
        pe_lessons = lessons(item)
        if pe_lessons:
            out += [{**_without_week(item), "date": date.fromisoformat(l.date), "time": l.start, "from_week": True}
                    for l in pe_lessons]
        else:
            out.append({**_without_week(item), "date": max(item["week"], today),
                        "title": f"{item['title']} (vko {item['weeknr']})", "from_week": True})
    return out


def _text(item: dict) -> str:
    """Otsikon teksti, joka mahtuu puhelimen pienelle näytölle: laji ja tärkein varuste (`Luistelu: luistimet`). Koko lista
    varusteista (myös valinnaiset ja kielletyt) on muistiinpanoissa. Ensisijaisesti mallin kirjoittama lyhyt otsikko
    (`short_title`), jos se mahtuu; muuten koodi rakentaa sen."""
    limit = MAX_TEXT
    if item.get("short_title") and fits(item["short_title"], limit):
        text = item["short_title"].strip()
        text = text[:1].upper() + text[1:]
        who = item.get("organizer")
        if who and not text.casefold().startswith(who.casefold()):       # ulkopuolisen tahon tilaisuus: järjestäjä näkyviin
            text = f"{who} – {text}"
        return text
    title = item["title"]
    gear = title_part(as_list(item.get("bring")), as_list(item.get("optional")))
    if item["kind"] == "pe":
        title = title[:1].upper() + title[1:]
        return title + (f": {gear}" if gear else "")
    return title + (f" – {gear}" if gear else "")


def _head(item: dict) -> str:
    """Pelkkä asia ilman varusteita ("Luistelu"): yhdistetyssä otsikossa, kun samalle päivälle tulee useita asioita."""
    title = item["title"].strip()
    return title[:1].upper() + title[1:]


def _lines(item: dict) -> list[str]:
    """Kuvauksen rivit: koko varustelista yksityiskohtineen (pakolliset, valinnaiset, kielletyt) ja kellonaika."""
    when = f" (klo {item['time']})" if item.get("time") else ""
    lines = note_lines(item["title"], as_list(item.get("bring")), as_list(item.get("optional")),
                       as_list(item.get("forbidden")))
    return [l + when if i == 0 else l for i, l in enumerate(lines)] if lines else [f"Asia: {item['title']}{when}"]


def _activity_key(item: dict) -> str:
    """Lajin tunniste yhdistämistä varten: nimen alkukirjaimet ("luistelu" ~ "Luistelua")."""
    return "".join(c for c in item["title"].lower() if c.isalpha())[:5]


def _union(*lists: list[str]) -> list[str]:
    seen, out = set(), []
    for x in (x for xs in lists for x in xs):
        if x.casefold() not in seen:
            seen.add(x.casefold())
            out.append(x)
    return out


def _merge_weekly(group: list[dict]) -> list[dict]:
    """Viikon liikunta: uusin viesti päättää, mikä laji viikolla on (esim. suunnitelma muuttui luistelusta sisäliikuntaan), mutta
    saman lajin vanhempien viestien varusteet yhdistetään. Uudempi vastaus tai muistutus ei saa pudottaa aiemmassa viestissä
    kerrottua (esim. valinnaista mailaa). Eri lajin vanhempi asia jää pois. Koskee kaikkia saman päivän liikuntarivejä, sekä
    viikosta johdettuja että viestissä päivälle nimettyjä."""
    weekly = list(group)
    order = lambda g: (g["info"].sent, g["info"].id)
    newest = max(order(g) for g in weekly)
    wanted = {_activity_key(g) for g in weekly if order(g) == newest}
    merged: dict[str, dict] = {}
    for g in sorted((g for g in weekly if _activity_key(g) in wanted), key=order, reverse=True):     # uusin ensin
        m = merged.get(_activity_key(g))
        if m is None:
            merged[_activity_key(g)] = {**g, "bring": as_list(g.get("bring")), "optional": as_list(g.get("optional")),
                                        "forbidden": as_list(g.get("forbidden")), "also_from": []}
            continue
        m["bring"] = _union(m["bring"], as_list(g.get("bring")))
        m["optional"] = _union(m["optional"], as_list(g.get("optional")))
        m["forbidden"] = _union(m["forbidden"], as_list(g.get("forbidden")))
        m["uncertain"] = m.get("uncertain", "") if g.get("uncertain") else ""      # epävarma vain, jos kaikki ovat epävarmoja
        m["also_from"] += [g["src"]] if g.get("src") else []
    for m in merged.values():
        required = {x.casefold() for x in m["bring"]}
        m["optional"] = [x for x in m["optional"] if x.casefold() not in required]  # pakollinen voittaa valinnaisen
    return list(merged.values())


def _parts_of(group: list[dict]) -> dict[str, dict]:
    """Ryhmän asiat lähdeviestin mukaan: {lähde: {"texts": [...], "lines": [...]}}. Lähde on "<oppilas>:<viestin id>"."""
    parts: dict[str, dict] = {}
    for g in group:
        part = parts.setdefault(g.get("src", ""), {"texts": [], "heads": [], "lines": []})
        part["texts"].append(_text(g))
        part["heads"].append(_head(g))
        part["lines"] += _lines(g)
    return parts


def build_events(items: list[dict], reminder_hour: int | None = None, previous: dict[str, dict] | None = None,
                 reprocessed: set[str] | None = None) -> list[dict]:
    """Yksi tapahtuma per oppilas, laji ja päivä.

    Tunniste ei riipu mallin sanoista, joten uusi viesti samalle päivälle päivittää tapahtumaa eikä tee uutta. Saman lajin
    asiat samalta päivältä yhdistetään otsikkoon ja kuvaukseen, myös aiemmilta ajoilta: tila (`previous`: tunniste -> tilan
    merkintä) tallentaa tekstit lähdeviestin mukaan (`parts`). Viesti, joka käsitellään nyt uudelleen (`reprocessed`), korvaa
    oman vanhan osuutensa eikä yhdisty itseensä; muiden viestien osuudet säilyvät. Oppilas on ryhmittelyn avaimessa ja kalenteri
    johdetaan aina asian omasta oppilaasta, joten eri lasten asiat eivät voi yhdistyä."""
    previous = previous or {}
    reprocessed = reprocessed or set()
    rem = reminders()
    hour = rem["hour"] if reminder_hour is None else reminder_hour
    groups: dict[tuple, list[dict]] = {}
    for item in items:
        groups.setdefault((item["info"].student.number, item["kind"], item["date"]), []).append(item)

    events = []
    for (number, kind, day), group in groups.items():
        weekly = kind == "pe" and any(g.get("from_week") for g in group)      # viikon liikunta: yksi laji per päivä
        if weekly:
            group = _merge_weekly(group)
        uid = hashlib.sha1(f"{number}|{kind}|{day.isoformat()}".encode()).hexdigest()[:16]
        info: MessageInfo = group[0]["info"]
        fresh = _parts_of(group)
        kept = {} if weekly else {src: part for src, part in (previous.get(uid, {}).get("parts") or {}).items()
                                  if src not in fresh and src not in reprocessed}
        parts = {**kept, **fresh}
        texts = list(dict.fromkeys(t for part in parts.values() for t in part["texts"]))
        lines = list(dict.fromkeys(l for part in parts.values() for l in part["lines"]))
        if kind == "info":
            who = next((g["organizer"] for g in group if g.get("organizer")), None)
            lines = ["Tiedoksi: ei koulun oma tilaisuus" + (f" ({who} järjestää)" if who else "")] + lines
        alarms = [datetime.combine(day - timedelta(days=n), time(hour)) for n in alarm_days(kind, rem)]
        unsure = list(dict.fromkeys(g["uncertain"] for g in group if g.get("uncertain")))
        heads = list(dict.fromkeys(h for part in parts.values() for h in part.get("heads", [])))
        # yksi asia: asia ja tärkein varuste; useita asioita samalle päivälle: vain asioiden nimet (otsikon pitää mahtua näytölle)
        title = make_title(kind, "; ".join(heads) if len(texts) > 1 and len(heads) == len(texts) else "; ".join(texts))
        if unsure:                                   # malli sanoi, että jokin on epäselvää: tarkistusmerkintä ja syy
            title = mark_uncertain(title, kind)
            lines = [f"⚠️ TARKISTA: {'; '.join(unsure)}"] + lines
        events.append({
            "uid": uid, "kind": kind, "origin": "viesti", "student": number, "calendar": calendar_name(info.student.name),
            "title": title, "date": day,
            "notes": owner_line(info.student.name) + "\n" + "\n".join(lines)
                     + f"\n\nOpettajan viesti: {info.subject}" + (f" ({info.sender})" if info.sender else "")
                     + f", lähetetty {info.sent:%d.%m.%Y}",
            "alarm": alarms[0] if alarms else None, "extra_alarms": alarms[1:],
            "parts": parts, "sources": sorted({s for s in parts if s} | {s for g in group for s in g.get("also_from", [])}),
        })
    return sorted(events, key=lambda e: (e["date"], e["calendar"], e["kind"]))
