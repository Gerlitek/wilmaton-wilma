#!/bin/bash
# Ajaa päivittäisen putken: ensin kokeet, sitten opettajien viestit. Käsin: scripts/run.sh   Ajastus: scripts/schedule.sh on
#   scripts/run.sh --dry-run   näyttää mitä kalentereihin tulisi (ei kirjoita, ei avaa viestejä)
#   scripts/run.sh --if-due    ajastettu ajo: ajetaan vain, jos tänään ei ole vielä onnistuttu
# Kokeet (sync-exams) ja viestit (sync-messages) ovat erillisiä hakuja, ja kumpikin tulostaa oman osionsa lokiin.
cd "$(dirname "$0")/.." || exit 1
mkdir -p data

# --if-due (ajastus): kone sammutetaan päivittäin, joten ajo yritetään kirjautuessa ja kello 16. Tämä rajaa sen kerran
# päivässä: jos viimeisin onnistunut ajo on tältä päivältä, ei tehdä mitään.
DUE=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--if-due" ]; then DUE=1; else ARGS+=("$a"); fi
done
if [ $DUE -eq 1 ]; then
  if [ -f data/last-ok ] && [ "$(date -r data/last-ok +%F)" = "$(date +%F)" ]; then exit 0; fi
  sleep 45   # annetaan kirjautumisen ja Wi-Fin rauhoittua
fi

# Viestit tulkitaan paikallisella Ollamalla. Ajastetussa ajossa se ei välttämättä ole käynnissä: käynnistetään tarvittaessa.
if ! /usr/bin/curl -fs -m 3 http://localhost:11434 >/dev/null; then
  echo "$(date '+%F %H:%M') Ollama ei vastaa, käynnistetään"
  ollama serve >> data/ollama.log 2>&1 &
  for _ in $(seq 30); do /usr/bin/curl -fs -m 2 http://localhost:11434 >/dev/null && break; sleep 1; done
fi

# Herätessä verkko ei ole heti valmis: odotetaan Wilman tavoitettavuutta enintään 2 minuuttia (jos osoite on .env:ssä).
url=$(grep -m1 '^WILMA_TENANT=' .env 2>/dev/null | sed 's/^WILMA_TENANT=//; s/["'"'"']//g')
if [ -n "$url" ]; then
  for _ in $(seq 60); do /usr/bin/curl -s -m 3 -o /dev/null "$url" && break; sleep 2; done
fi

echo "=== $(date '+%F %H:%M') Wilma-ajo ==="
rc=0
.venv/bin/python -m oma_wilma sync-exams "${ARGS[@]}" || rc=1
.venv/bin/python -m oma_wilma sync-messages "${ARGS[@]}" || rc=1
if [ $rc -eq 0 ] && [ $DUE -eq 1 ]; then touch data/last-ok; fi
exit $rc
