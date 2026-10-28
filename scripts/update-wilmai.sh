#!/usr/bin/env bash
# Päivittää wilmai:n CLI:n (npm-paketti, julkaistaan GitHub-repon aikarjal/wilmai versioista) ja ajaa testit.
#   scripts/update-wilmai.sh           päivitys package.json:n sallimaan versioon (^2.x)
#   scripts/update-wilmai.sh latest    uusin versio, myös uusi pääversio (tarkista JSON-muodot, SUPPORTED_MAJOR)
set -euo pipefail
cd "$(dirname "$0")/.."
before=$(node -p "require('./node_modules/@wilm-ai/wilma-cli/package.json').version" 2>/dev/null || echo "ei asennettu")
if [ "${1:-}" = "latest" ]; then npm install @wilm-ai/wilma-cli@latest; else npm update @wilm-ai/wilma-cli; fi
after=$(node -p "require('./node_modules/@wilm-ai/wilma-cli/package.json').version")
echo "wilmai: $before -> $after"
[ "$before" != "$after" ] && echo "Muutokset: https://github.com/aikarjal/wilmai/blob/main/CHANGELOG.md"
python3 -m unittest discover -s tests -t .
