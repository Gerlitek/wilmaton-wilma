# Lukujärjestys tulostettavaksi

Tekee jokaiselle lapselle oman lukujärjestyksen A4-paperille (vaaka) Wilman tunneista. Lapsen nimi on ylhäällä isoilla
palikkakirjaimilla, ja sivun reunoilla on mustavalkoinen kuva, jonka lapsi voi värittää. Lukujärjestykseen voi lisätä
merkkejä, jotka auttavat lasta muistamaan: 🎽 liikuntavaatteet mukaan, 🍎 välipala mukaan, ☀️/🌙 alkaako koulu aamulla vai
vasta ruokailun jälkeen.

```
scripts/timetable.sh
```

Komento hakee Wilmasta **ensi viikon** tunnit ja tekee PDF:t kansioon `data/lukujarjestykset/`, esim.
`lukujarjestys-kiia-green-2026-11-30.pdf`. Tulosta ne tavallisesti (Esikatselu, A4, vaaka). Kansio ei mene Gitiin, koska
tiedostoissa on lasten nimet.

Tarvitset saman asennuksen kuin muuhun työkaluun (ks. [README](../README.md#asennus)) sekä **Google Chromen**: PDF tehdään
Chromella taustalla, ikkunaa ei avata. Ollamaa ja kalentereita ei tarvita.

## Esimerkkejä

```
scripts/timetable.sh                                    pelkät tunnit
scripts/timetable.sh --no-support --meals --pe-emoji     ilman tukiopetusta, ruokailu ja liikunta näkyvissä
scripts/timetable.sh --start-emoji --snack wed           aamu/ilta-merkit ja välipala keskiviikkona kaikille
scripts/timetable.sh --snack Kiia=tue --snack Onni=thu   välipala eri päivinä eri lapsille
scripts/timetable.sh --theme heart                       sydänteema
scripts/timetable.sh --student Kiia --week 2026-12-07    vain yksi lapsi, tietty viikko
```

Valintoja voi yhdistellä vapaasti. Kaikki valinnat: `scripts/timetable.sh --help`.

## Valinnat

### Mitä tunteja näytetään

| Valinta | Mitä tekee |
|---|---|
| `--no-support` | Jättää tukiopetuksen pois (esim. "Tukiopetus (varaus)", "Ryhmäkohtainen tuki"). Ilman tätä tukiopetus näkyy, ja tavallisen tunnin aikana oleva tuki näkyy pienellä tunnin alla. |
| `--worldview religion` | Katsomusaine: `religion` = Uskonto (oletus), `ethics` = ET tai `both` = "Uskonto / ET". |
| `--week next` | Miltä viikolta tunnit haetaan: `next` (ensi viikko, oletus), `this` (tämä viikko) tai päivämäärä, esim. `2026-12-07` (sen päivän viikko). Valitse toinen viikko, jos ensi viikolla on loma: komento kertoo, jos jokin päivä on tyhjä. |
| `--student Kiia` | Vain yksi lapsi (etunimen alku tai oppilasnumero). Ilman tätä tehdään kaikille. |

### Välitunnit ja ruokailu

Wilma ei kerro, mikä välitunneista on ruokailu, joten ruokatauon aika annetaan kerran asetuksissa (`config.toml`):

```toml
[timetable]
lunch = "11:00-11:30"
```

tai komennolla `--lunch 11:00-11:30`. Muoto `11.00-11.30` käy myös.

| Valinta | Mitä tekee |
|---|---|
| `--meals` | Näyttää ruokailun (harmaalla) tuntien välissä, muita välitunteja ei. Selkein vaihtoehto. |
| `--breaks` | Näyttää kaikki välitunnit ja ruokailun. |

Välitunti näkyy vain päivinä, joina lapsi on silloin koulussa. Jos koulu alkaa vasta ruokailun jälkeen, ruokailu näkyy
silti: lapsi tulee kouluun syömään.

### Muistutusmerkit lapselle

| Valinta | Mitä tekee |
|---|---|
| `--pe-emoji` | 🎽 liikuntatunnin eteen: liikuntavaatteet mukaan. Liikuntatunti tunnistetaan aineen nimestä (`config.toml`: `[messages] pe_subject_words`, oletus "liikunta"). |
| `--snack wed` | 🍎 välipala päivän otsikkoon. Päivät annetaan itse: `mon tue wed thu fri` (tai `1`–`5`), useampi pilkulla: `tue,thu`. Vain yhdelle lapselle: `--snack Kiia=tue`. Valinnan voi antaa monta kertaa. |
| `--start-emoji` | Päivän nimen viereen ☀️, jos koulu alkaa aamulla (ennen ruokailua), tai 🌙, jos vasta ruokailusta tai myöhemmin. Tarvitsee ruokatauon ajan. |

### Ulkoasu ja tiedostot

| Valinta | Mitä tekee |
|---|---|
| `--theme green` | Taustakuvan teema: `green` (oletus): palikkamaailma, jossa soturi, lintu, laiva, lammas, puu ja palikat. `heart`: sydämiä, tähtiä, sateenkaari ja yksisarviset, nimi isoin ääriviivakirjaimin. |
| `--out KANSIO` | Mihin PDF:t tehdään (oletus `data/lukujarjestykset/`). |
| `--html` | Tekee HTML-sivun PDF:n sijaan (ei tarvitse Chromea). Avaa selaimessa ja tulosta sieltä. |

Valinnat ja niiden arvot ovat englanniksi (`green`, `heart`, `this`, `mon`–`fri`, `religion`), joten ne sopivat skripteihin.
Suomenkieliset arvot käyvät myös: `vihrea`, `sydan`, `tama`, `ma`–`pe`, `uskonto`, `et`, `molemmat`.

## Asetukset (`config.toml`)

```toml
[timetable]
lunch = "11:00-11:30"                                  # ruokatauko
support_words = ["tukiopetus", "ryhmäkohtainen tuki"]   # näistä sanoista tunnistetaan tukiopetus (--no-support)

[timetable.names]                                      # aineen nimi lapselle: Wilman nimi = näytettävä nimi
"Suomen kieli ja kirjallisuus" = "Suomi"
```

Aineiden nimet lyhennetään valmiiksi: "Kuvataide yhteinen a" → Kuvataide, "Englanti, A1" → Englanti, "Suomen kieli ja
kirjallisuus" → Äidinkieli.

## Oma teema

Teemat ovat tiedostossa `oma_wilma/timetable/themes.py`. Teema on funktio, joka palauttaa koko sivun kuvan (SVG, millimetreinä) ja
piirtää lapsen nimen. Taulukko tulee kuvan päälle alueelle `TABLE_BOX`, joten kuva tehdään sen ympärille. Lisää funktio
`THEMES`-listaan nimen ja ääkkösettömän lisänimen kanssa.
