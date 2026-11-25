#!/bin/bash
# Lukujärjestykset PDF:ksi kaikille lapsille (käsin ajettava). PDF:t: data/lukujarjestykset/
#   scripts/timetable.sh                                ensi viikon tunneista, teema green
#   scripts/timetable.sh --no-support --meals --pe-emoji --start-emoji --snack wed
#   scripts/timetable.sh --help                          kaikki valinnat
cd "$(dirname "$0")/.." || exit 1
exec .venv/bin/python -m oma_wilma timetable "$@"
