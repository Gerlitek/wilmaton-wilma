"""Tarkistaa, ettei Gitiin menevissä tiedostoissa ole yksityisiä tietoja (repo voi myöhemmin muuttua julkiseksi).

Etsii seurattavista ja vielä lisäämättömistä (ei .gitignoressa olevista) tiedostoista:
  - .env:n arvoja (koulun osoitteen nimi, käyttäjätunnus) ja config.toml:n henkilökohtaisia arvoja (vanhempi lapsi, ulkopuoliset järjestäjät)
  - omia sanoja tiedostosta .private-terms.txt (yksi per rivi, ei Gitissä): lasten nimet, oppilasnumerot, paikkakunta ym.
Aja: python3 scripts/privacy_check.py [--history]   (--history tarkistaa myös kaikki commitit)
Palauttaa 1, jos jokin löytyy. Voi asentaa pre-commit-koukuksi (.git/hooks/pre-commit).
"""
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from oma_wilma.config import parse_dotenv  # noqa: E402

MIN_LEN = 4
SAFE = {"wilma", "http", "https", "koulu", "tenant"}   # yleisiä sanoja, joita ei tarkisteta


def terms() -> set[str]:
    out: set[str] = set()
    env = ROOT / ".env"
    if env.is_file():
        v = parse_dotenv(env.read_text(encoding="utf-8"))
        host = urlparse(v.get("WILMA_TENANT", "")).hostname or ""
        out |= {host.split(".")[0], v.get("WILMA_USERNAME", "")}
    cfg = ROOT / "config.toml"
    if cfg.is_file():
        m = tomllib.loads(cfg.read_text(encoding="utf-8")).get("messages", {})
        out |= {str(x) for x in m.get("shared_priority", [])} | {str(w) for w in m.get("external_organizers", [])}
    extra = ROOT / ".private-terms.txt"
    if extra.is_file():
        out |= {l.strip() for l in extra.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    return {t for t in out if t and len(t) >= MIN_LEN and t.lower() not in SAFE}


def main() -> int:
    ts = terms()
    if not ts:
        print("Ei tarkistettavia sanoja. Lisää omat sanat tiedostoon .private-terms.txt (yksi per rivi).")
        return 0
    files = [f for f in subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.split("\n") if f]
    bad = []
    for term in sorted(ts):
        r = subprocess.run(["git", "grep", "--untracked", "-n", "-i", "-F", "-e", term, "--", *files], cwd=ROOT,
                           capture_output=True, text=True)
        bad += [f"{term!r}: {line[:100]}" for line in r.stdout.splitlines()]
        if "--history" in sys.argv:
            revs = subprocess.run(["git", "rev-list", "--all"], cwd=ROOT, capture_output=True, text=True).stdout.split()
            if revs:
                h = subprocess.run(["git", "grep", "-l", "-i", "-F", "-e", term, *revs], cwd=ROOT, capture_output=True, text=True)
                bad += [f"{term!r} HISTORIASSA: {line[:100]}" for line in h.stdout.splitlines()[:3]]
    for b in bad:
        print("LÖYTYI", b)
    print(f"{len(bad)} osumaa, {len(ts)} sanaa tarkistettu." if bad else f"Puhdas: {len(ts)} sanaa tarkistettu eikä osumia.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
