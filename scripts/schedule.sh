#!/bin/bash
# Ajastus: scripts/schedule.sh on | off | status | test
# on      asentaa launchd-työn: joka päivä klo 16.00 ja kirjautuessa, mutta vain kerran päivässä
# off     poistaa ajastuksen
# status  näyttää tilan ja viimeisen ajon lokin lopun
# test    ajaa työn heti launchdin kautta (sama ympäristö kuin ajastetussa ajossa) ja seuraa lokia
set -e
cd "$(dirname "$0")/.."
LABEL=fi.wilma.daily
PLIST=~/Library/LaunchAgents/$LABEL.plist
DOMAIN="gui/$(id -u)"
case "$1" in
  on)
    chmod +x scripts/run.sh
    mkdir -p ~/Library/LaunchAgents data
    # mallipohjan @DIR@ -> tämän kansion todellinen polku (ei kovakoodattua polkua repossa)
    sed "s#@DIR@#$PWD#g" launchd/$LABEL.plist.template > "$PLIST"
    plutil -lint "$PLIST"
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Ajastus päällä: joka päivä klo 16.00 ja kirjautuessa (kerran päivässä). Kokeile heti: scripts/schedule.sh test"
    ;;
  off)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Ajastus pois."
    ;;
  status)
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      echo "Ajastus: PÄÄLLÄ"
      launchctl print "$DOMAIN/$LABEL" | grep -E "state|runs|last exit code" || true
    else
      echo "Ajastus: POIS"
    fi
    [ -f data/last-ok ] && echo "Viimeinen onnistunut ajastettu ajo: $(date -r data/last-ok '+%F %H:%M')" || echo "Ei vielä onnistunutta ajastettua ajoa"
    echo "--- data/run.log (loppu) ---"
    tail -n 25 data/run.log 2>/dev/null || echo "(ei lokia)"
    ;;
  test)
    launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || { echo "Ota ensin käyttöön: scripts/schedule.sh on"; exit 1; }
    : >> data/run.log
    rm -f data/last-ok   # pakottaa ajon, vaikka tänään on jo onnistuttu
    launchctl kickstart -k "$DOMAIN/$LABEL"
    echo "Ajo käynnistetty. Seurataan lokia (Ctrl-C lopettaa; ajo jatkuu)."
    tail -n 0 -f data/run.log
    ;;
  *)
    echo "Käyttö: scripts/schedule.sh on|off|status|test"; exit 1
    ;;
esac
