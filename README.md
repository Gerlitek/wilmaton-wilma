# Wilmaton Wilma

> **Wilma without Wilma:** a small macOS tool for parents that reads Wilma (the Finnish school messaging system). It
> **(1)** puts exams and the dates in teachers' messages into your iCloud calendar, and **(2)** prints each child's weekly
> timetable as a colouring page. Messages are interpreted locally and never leave your machine. Unofficial; not affiliated
> with Visma. The rest of the docs are in Finnish.

Oleelliset Wilmasta kalenteriin ja jääkaapin oveen, niin Wilmaa tarvitsee avata vähemmän. Kaksi toisistaan riippumatonta
toimintoa, joista voit käyttää vain toista.

## 1. Kokeet ja viestit kalenteriin

"Ensi viikolla luistelu, ota luistimet" hukkuu helposti muiden viestien joukkoon. Wilmaton Wilma poimii kokeet ja
opettajien viesteissä kerrotut päivät iCloud-kalenteriin, yksi kalenteri lasta kohden.

| Kalenterissa näkyy | Muistutus |
|---|---|
| `📝Koe: Matematiikka – Murtoluvut` | 2 pv ennen |
| `🎽Luistelu: luistimet` | edellisenä iltana |
| `📸Kuvaus`, `🚌 Retki`, `📌 Tapahtuma` | edellisenä iltana |
| `👪Vanhempainilta` | 3 pv ja 1 pv ennen |
| `ℹ️Tiedoksi: ulkopuolisen järjestäjän tilaisuus` | ei |

- Pelkkä "ensi viikolla" liikunnasta sijoitetaan lapsen lukujärjestyksen liikuntapäiville.
- Usealle sisarukselle tullut sama viesti käsitellään vain kerran.
- Viestit tulkitsee omalla koneellasi pyörivä tekoäly ([Ollama](https://ollama.com)). Viestin teksti ei lähde koneelta.
- Tekoäly erehtyy joskus (`⚠️` = epäselvä), joten tarkista tärkeät asiat alkuperäisestä viestistä.

## 2. Tulostettava lukujärjestys

Jokaiselle lapselle oma A4: nimi isolla ja mustavalkoinen kuva väritettäväksi (teemat `green`: palikkamaailma, `heart`:
sydämet ja yksisarviset). Halutessasi mukaan 🎽 liikuntatunnit, 🍎 välipalapäivät, ☀️/🌙 aikainen vai myöhäinen aamu ja
ruokailu.

## Asennus

Tarvitset macOS:n, [Node.js](https://nodejs.org):n (20.18.1+) ja Pythonin (3.11+).

```
git clone https://github.com/Gerlitek/wilmaton-wilma.git && cd wilmaton-wilma
npm install
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                # täytä WILMA_TENANT ja WILMA_USERNAME
cp config.example.toml config.toml  # omat asetukset
security add-generic-password -s wilma -a password -w          # salasana Keychainiin (kysyy arvon)
security add-generic-password -s wilma -a totp-secret -w       # vain kaksivaiheisella; avain, ei 6 numeron koodi
.venv/bin/python -m oma_wilma check                            # toimiiko kirjautuminen
```

### Kalenteri

1. Asenna [Ollama](https://ollama.com) ja lataa malli: `ollama pull gemma4:12b` (7,7 Gt; testattu 16 Gt:n muistilla).
2. Luo Kalenterit-sovelluksessa (iCloud) jokaiselle lapselle kalenteri `Wilma <etunimi>`.
3. Kokeile ja ota käyttöön:

```
scripts/run.sh --dry-run      näyttää mitä tapahtuisi, ei kirjoita
scripts/run.sh                vie kokeet ja viestien asiat kalenteriin
scripts/schedule.sh on        ajo automaattisesti joka päivä klo 16 (off: pois)
```

Ajastuksen toiminta, loki ja kellonajan vaihto: [docs/tekninen.md](docs/tekninen.md#ajastus).

Wilmaa vain luetaan, mutta **viestin avaaminen voi merkitä sen luetuksi**.

### Lukujärjestys

Asenna Google Chrome (PDF tehdään sillä). Aseta `config.toml`:iin koulun ruokatauko, esim. `[timetable] lunch = "11:00-11:30"`.

```
scripts/timetable.sh                                                              pelkät tunnit
scripts/timetable.sh --theme heart --meals --pe-emoji --start-emoji --snack wed   merkkien kanssa
```

PDF:t tulevat kansioon `data/lukujarjestykset/`. Kaikki valinnat: **[docs/lukujarjestys.md](docs/lukujarjestys.md)**.

## Hyvä tietää

**Epävirallinen työkalu**, ei liity Vismaan. Wilman käyttöehtoja ei ole varmistettu tälle käytölle: käytä omalla
vastuullasi, omilla tunnuksillasi ja vain omien lasten tietoihin.

Komennot, asetukset, toimintaperiaate ja kehitys: **[docs/tekninen.md](docs/tekninen.md)**.

## Lisenssi

[MIT](LICENSE). Wilma-haun tekee [wilmai](https://github.com/aikarjal/wilmai) (`@wilm-ai/wilma-cli`, MIT, © Wilm.ai), joka asennetaan
npm-riippuvuutena eikä sisälly tähän repoon.
