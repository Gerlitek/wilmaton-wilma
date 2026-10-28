"""Mallin kehote ja vastauksen muoto viestin tulkintaan.

Kehotteen tehtävä on auttaa mallia päättelemään, ei sanella sitä: se kertoo luokat, kentät ja pari yleistä periaatetta
(jokainen viikko oma asiansa, älä keksi) ja pyytää mallia kertomaan itse, jos jokin on epäselvää (`uncertain`). Koodi hoitaa vain
hallinnan: oikea lapsi ja kalenteri, päivien laskenta ja järkevä aikaväli (notices.py, when.py).
Uusi laji: lisää se `events.KINDS`-tauluun ja tässä CATEGORY-kuvaukseen sekä kehotteen luokkalistaan.
"""
from __future__ import annotations

from datetime import date

from .when import RELATIVE, WEEKDAYS, WEEKDAYS_ALL

# mallin luokka -> laji (events.KINDS)
CATEGORY = {"liikunta": "pe", "kuvaus": "photo", "retki": "trip", "tapahtuma": "event", "vanhempainilta": "parents",
            "tiedoksi": "info"}

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CATEGORY)},
        "title": {"type": "string"},
        "short_title": {"type": "string"},
        "bring": {"type": "array", "items": {"type": "string"}},
        "bring_optional": {"type": "array", "items": {"type": "string"}},
        "do_not_bring": {"type": "array", "items": {"type": "string"}},
        "organized_by_school": {"type": "boolean"},
        "organizer": {"type": "string"},
        "timing_evidence": {"type": "string"},
        "date": {"type": "string"},
        "weekday": {"type": "string", "enum": [""] + WEEKDAYS},
        "week": {"type": "integer"},
        "relative_week": {"type": "string", "enum": [""] + list(RELATIVE)},
        "uncertain": {"type": "string"},
    },
    "required": ["category", "title", "short_title", "bring", "bring_optional", "do_not_bring", "organized_by_school", "organizer",
                 "date", "weekday", "week", "relative_week", "timing_evidence", "uncertain"]}}},
    "required": ["items"]}

_PROMPT = """Olet apuri, joka lukee koulun opettajan viestiä vanhemman puolesta.
Viesti on lähetetty {sent_weekday} {sent:%d.%m.%Y} (viikko {sent_week}).
Tehtävä: päättele viestistä asiat, jotka koskevat tiettyä päivää tai viikkoa ja jotka vanhemman tai lapsen pitää tietää
tai joihin pitää valmistautua. Opettaja voi ilmaista ajankohdan monella tavalla (viikonpäivä, päiväys, "ensi viikolla",
"vko 44 ja 45", "huomenna", "ensi tiistaina"); päättele itse, mihin päivään tai viikkoon asia viittaa. Luokat:
- liikunta: liikuntatunti tai liikuntajakso, johon pitää valmistautua (sisäliikunta, ulkoliikunta, uinti, luistelu,
  hiihto ym.). Otsikoksi laji; varusteet kerrotaan listoissa bring, bring_optional ja do_not_bring (ks. alla).
- kuvaus: valokuvauspäivä tai muu kuvaus
- retki: retki tai vierailu
- vanhempainilta: koulun tai opettajan järjestämä vanhempainilta tai vanhempainvartti, johon vanhempien odotetaan osallistuvan
- tiedoksi: ulkopuolisen tahon (esim. hyvinvointialue, seurakunta, kaupunki, yhdistys) järjestämä tilaisuus tai tapahtuma,
  joka on lähinnä tiedoksi ja johon ei yleensä osallistuta, vaikka se olisi vanhemmille suunnattu. Älä luokittele sitä vanhempainiltaksi.{outsiders}
- tapahtuma: koulun oma juhla, näytös, koulutuspäivä, poikkeava aikataulu, määräaika (jolloin jotain pitää tuoda tai palauttaa) tai muu
  merkittävä päivä, jossa vanhemman tai lapsen pitää tehdä jotain tiettynä päivänä.
Älä poimi ehdollisia tai vain joillekin oppilaille kuuluvia asioita (esim. poissaolleiden tehtävät, "jos olet ollut poissa", tietyn
ryhmän asiat), ellei viesti selvästi kerro niiden koskevan kaikkia. Läksyt ja tavallinen opetus eivät ole kalenterimerkintöjä.
Jokainen viikko on oma asiansa: tee jokaisesta asiasta ja viikosta oma rivi, jonka week-kentässä on yksi viikkonumero. Jos sama
asia koskee kahta viikkoa, tee kaksi riviä. Jos viesti kertoo eri viikoille eri asian, anna jokaiselle viikolle vain sen oma
asia. Älä liitä asiaa viikolle, jota viesti ei kerro siitä. Viikon liikunta on yksi: jos viikolla on luistelua, siellä ei ole
muuta liikuntaa, ja jokaisella viikolla vain sen oma ohje.
Jos viesti kertoo, minä päivänä asia on, tee jokaisesta nimetystä päivästä oma rivi weekday-kentällä (esim. "tiistaina ja
keskiviikkona" -> kaksi riviä). Jos viesti sanoo, että asia on kaikilla viikon tunneilla ("molempina päivinä", "kaikilla tunneilla")
tai ei kerro päivää, jätä weekday tyhjäksi: silloin asia koskee viikon kaikkia liikuntatunteja.
Esimerkki: viesti "viikolla 44 luistelua ja viikolla 45 sisäliikuntaa, luistelussa tarvitaan luistimet" tuottaa kaksi
riviä: luistelu (bring: ["luistimet"], week: 44) ja sisäliikunta (week: 45). Luistimet kuuluvat vain luistelulle.
Viestit ovat opettajien vapaamuotoisia, käsin kirjoitettuja viestejä: ne voivat olla pitkiä, epäsiistejä ja sisältää monta asiaa
sekaisin, eikä niissä ole kiinteää muotoa. Päättele merkitys kokonaisuudesta. Älä poimi tavallista opetusta, läksyjä tai koetta
(kokeet haetaan toisaalla). Poimi vain, jos viestissä on ajankohta, jonka voit päätellä. Jos viestissä ei ole tällaista asiaa, palauta tyhjä lista. Älä keksi mitään.
Jokaisesta asiasta kerro:
- category: yksi luokista
- title: lyhyt nimi asialle suomeksi, enintään 5 sanaa, viestin omilla sanoilla (esim. "sisäliikunta", "kuvauspäivä")
- short_title: kalenterimerkinnän otsikko, enintään 30 merkkiä, jotta se näkyy puhelimen pieneltä näytöltä kokonaan: asia ja
  korkeintaan yksi tärkein varuste. Muut varusteet (myös valinnaiset kuten maila) kuuluvat listoihin bring, bring_optional ja
  do_not_bring, eivät otsikkoon. Älä toista lajia äläkä päivämäärää (kalenteri näyttää sen); kellonaika saa olla.
  Esim. "Luistelu: luistimet" tai "Retki: eväät"
- organized_by_school: true, jos koulu tai opettaja järjestää tämän itse (oma luokka, oma koulu). false, jos järjestäjä on joku
  muu (esim. hyvinvointialue, seurakunta, kaupunki, yhdistys), vaikka tilaisuus olisi suunnattu koulun vanhemmille.
- organizer: järjestäjän nimi viestin sanoin (esim. "koulu" tai ulkopuolisen tahon nimi). Tyhjä, jos asia ei ole tapahtuma.
- bring: lista asioista, jotka pitää ottaa mukaan tai pukea. Kirjoita kaikki viestin luettelemat varusteet, älä pudota
  mitään. Käytä viestin omia sanoja; kokoa vaatteet yhdeksi kohdaksi ja kirjoita yksityiskohdat sulkuihin, esim.
  ["luistimet", "kypärä", "ulkovaatetus (kevyt takki, ulkohousut, hanskat, ohut pipo)"]. Tyhjä lista, jos ei mitään.
- bring_optional: asiat, jotka saa tai voi ottaa mukaan, mutta jotka eivät ole pakollisia, esim. ["maila"]. Viesti voi sanoa tämän
  millä tahansa tavalla ("halutessaan voi ottaa myös", "saa ottaa", "vapaaehtoisesti", "mahdollisesti" ...): käy läpi kaikki viestin
  varustelauseet ja kirjaa jokainen tällainen asia tähän, älä jätä niitä pois. Älä laita tähän pakollisia asioita. Tyhjä lista,
  jos ei mitään.
- do_not_bring: asiat, joita viesti kieltää ottamasta mukaan (esim. "maila", jos viestissä sanotaan, ettei mailaa saa
  ottaa tähän vuoroon). Tyhjä lista, jos ei kiellettyjä.
- date: päivä muodossa VVVV-KK-PP, vain jos viesti kertoo tarkan päivämäärän (tai "huomenna" ym.). Muuten tyhjä.
- weekday: viikonpäivä, vain jos viesti mainitsee viikonpäivän. Jos asia koskee koko viikkoa, jätä tyhjäksi. Älä arvaa.
- timing_evidence: jos annoit date- tai weekday-kentän, kopioi viestistä täsmälleen ne sanat, joista tarkka päivä tai viikonpäivä
  käy ilmi (esim. "keskiviikkona" tai "4.11."). Jos viesti puhuu vain viikosta tai ei kerro päivää, jätä date ja weekday tyhjiksi ja
  tämä kenttä tyhjäksi.
- week: viikkonumero, jos viesti puhuu viikosta numerolla (esim. "vkot 44 ja 45" -> kaksi riviä, week 44 ja week 45). Muuten 0.
- relative_week: "tämä viikko" tai "ensi viikko", jos viesti viittaa viikkoon näin ("ensi viikolla"). Muuten tyhjä.
- uncertain: lyhyt huomautus suomeksi (ilman lainauksia viestistä), jos itse asia tai sen viikko on epäselvä tai viesti on tästä
  ristiriitainen. Älä huomauta siitä, ettei viikonpäivää kerrota, jos viikko on selvä. Tyhjä, jos kaikki on selvää.
{child}Viesti:
{body}
"""

_CHILD = """Tämän oppilaan omat viimeaikaiset merkinnät Wilmassa (poissaolot, myöhästymiset ym.): {notes}.
Käytä niitä vain ratkaistaksesi, koskeeko ehdollinen tai vain joillekin kuuluva viesti (esim. poissaolleiden tehtävät, "jos olet
ollut poissa") juuri tätä oppilasta. Jos viesti koskee vain poissaolleita ja merkintöjä ei ole, älä poimi sitä.
"""


def make_prompt(body: str, sent: date, outsiders: list[str] | None = None, child_notes: list[str] | None = None) -> str:
    """`outsiders`: käyttäjän tuntemat ulkopuoliset järjestäjät vihjeeksi mallille (ei sääntönä). `child_notes`: oppilaan omat
    viimeaikaiset merkinnät (None = tietoa ei ole; tyhjä lista = ei merkintöjä)."""
    hint = f" Tunnettuja ulkopuolisia järjestäjiä: {', '.join(outsiders)}." if outsiders else ""
    child = "" if child_notes is None else _CHILD.format(notes="; ".join(child_notes[:15]) if child_notes else "ei yhtään merkintää")
    return _PROMPT.format(body=body, sent=sent, sent_week=sent.isocalendar().week,
                          sent_weekday=WEEKDAYS_ALL[sent.weekday()], outsiders=hint, child=child)

