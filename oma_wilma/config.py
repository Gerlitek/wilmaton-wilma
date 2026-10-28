"""Asetukset: oikea ympäristö ensin, sitten .env, salasana ja TOTP-avain lopuksi macOS Keychainista.

Tulos on ympäristömuuttujat wilmai:n CLI:lle (WILMA_TENANT, WILMA_USERNAME, WILMA_PASSWORD, WILMA_TOTP_SECRET).
Jos tenant ja tunnus puuttuvat, CLI:lle ei anneta mitään ja se käyttää `wilma login`:illa tallennettua kirjautumista.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYCHAIN_SERVICE = "wilma"
KEYCHAIN_PASSWORD = "password"
KEYCHAIN_TOTP = "totp-secret"

SecretReader = Callable[[str, str], str | None]


def read_keychain(service: str, account: str) -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    return out or None


def parse_dotenv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def cli_env(
    environ: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
    keychain: SecretReader = read_keychain,
) -> dict[str, str]:
    """Ympäristö, joka annetaan CLI:lle lisättynä. Tyhjä, jos kirjautumista ei ole määritetty täällä."""
    environ = os.environ if environ is None else environ
    path = ROOT / ".env" if dotenv_path is None else dotenv_path
    file_values = parse_dotenv(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def get(key: str) -> str | None:
        return environ.get(key) or file_values.get(key) or None

    tenant, username = get("WILMA_TENANT"), get("WILMA_USERNAME")
    if not tenant or not username:
        return {}
    env = {"WILMA_TENANT": tenant, "WILMA_USERNAME": username}
    password = get("WILMA_PASSWORD") or keychain(KEYCHAIN_SERVICE, KEYCHAIN_PASSWORD)
    if password:
        env["WILMA_PASSWORD"] = password
    totp = get("WILMA_TOTP_SECRET") or keychain(KEYCHAIN_SERVICE, KEYCHAIN_TOTP)
    if totp:
        env["WILMA_TOTP_SECRET"] = totp
    return env


CONFIG = ROOT / "config.toml"


def settings(path: Path | None = None) -> dict:
    """Henkilökohtaiset asetukset tiedostosta config.toml (ei Gitissä; mallipohja config.example.toml). Puuttuva
    tiedosto tarkoittaa oletuksia. Salaisuudet (salasana, TOTP) eivät kuulu tänne vaan Keychainiin tai .env:iin."""
    path = CONFIG if path is None else path
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{path.name} on virheellinen: {e}")
