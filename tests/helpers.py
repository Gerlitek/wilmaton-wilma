"""Testien yhteiset apufunktiot ja keksityt esimerkkiviestit (ei oikeita nimiä eikä viestejä)."""
from datetime import date

from oma_wilma import messages
from oma_wilma.models import Student

KIIA = Student("1001", "Kiia Virtanen")

ONNI = Student("1002", "Onni Virtanen")

def info(sent=date(2026, 11, 2), student=KIIA, replies=0, mid=1):
    return messages.MessageInfo(student, mid, "Viikkotiedote", sent, "Opettaja", True, replies)

def msg(text, sent=date(2026, 11, 2), **kw):
    return messages.Message(info(sent, **kw), text)

def answer(*items):
    return lambda prompt, schema: {"items": list(items)}

def item(**kw):
    """Mallin keksitty ehdotus. Tarkan päivän tai viikonpäivän perusteluksi (`timing_evidence`) tulee oletuksena viikonpäivän
    sana, jollei sitä anneta: malli lainaa viestistä sanat, joista tarkka päivä käy ilmi."""
    base = {"category": "liikunta", "title": "luistelu", "short_title": "", "bring": "luistimet ja kypärä",
            "bring_optional": [], "do_not_bring": [], "organized_by_school": True, "organizer": "koulu",
            "date": "", "weekday": "", "weeks": [], "relative_week": "", "timing_evidence": "", "uncertain": ""}
    out = {**base, **kw}
    if (out["weekday"] or out["date"]) and "timing_evidence" not in kw:
        out["timing_evidence"] = out["weekday"] or ""
    return out

SKATING = "Torstaina on ulkoliikuntaa, jolloin luistellaan. Ottakaa mukaan luistimet ja kypärä."

ITEM = item(weekday="torstai")

WEEK_TEXT = "Liikunta vkot 44 ja 45: ensi viikolla on sisäliikuntaa. Ottakaa mukaan sisäkengät ja liikuntavaatteet."

WEEK_ITEM = item(title="sisäliikunta", bring="sisäkengät ja liikuntavaatteet", weeks=[44, 45])

WEEK_ONLY = "Liikunta vkot 44 ja 45: ensi viikolla on sisäliikuntaa. Ottakaa mukaan sisäkengät ja liikuntavaatteet."

TWO_WEEKS = ("Jos saat tämän viestin, lapsesi on viikolla 44 luistelemassa ja viikolla 45 sisäliikunnassa. "
             "Luistelussa tarvitaan luistimet ja kypärä. Sisäliikunnassa riittävät liikuntavaatteet.")

# Opettajan oikea luettelo (yleinen): pakolliset, vaatetus yksityiskohtineen ja valinnainen maila
SKATING_LIST = ("Luisteluun tarvitaan: luistimet, kypärä, luistelemiseen sopiva ulkovaatetus (kevyt takki, ulkohousut, "
                "hanskat, ohut pipo). Halutessaan voi ottaa myös mailan. Luistelu on torstaina.")

SKATING_PROPOSAL = item(
    title="luistelu", weekday="torstai",
    bring=["luistimet", "kypärä", "luistelemiseen sopiva ulkovaatetus (kevyt takki, ulkohousut, hanskat, ohut pipo)"],
    bring_optional=["maila"])
