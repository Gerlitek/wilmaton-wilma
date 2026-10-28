"""Rajapinta wilmai:n `wilma`-CLI:hin. Ainoa paikka, jossa CLI:tä kutsutaan.

CLI:n JSON on sen dokumentoitu rajapinta (`wilma help <komento>`). Tämä moduuli ajaa komennon, jäsentää JSONin
ja muuttaa CLI:n virheet poikkeuksiksi. Kaikki muu koodi käyttää tätä, ei subprocessia suoraan.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import ROOT, cli_env

PACKAGE = "@wilm-ai/wilma-cli"
SUPPORTED_MAJOR = 2  # JSON-muodot on tarkistettu tälle pääversiolle


class WilmaError(Exception):
    """wilmai:n CLI palautti virheen (`{"status":"error","code":...}`)."""

    def __init__(self, code: str, message: str, exit_code: int = 1):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.exit_code = exit_code


class NotLoggedIn(WilmaError):
    pass


def wilma_bin() -> Path:
    override = os.environ.get("WILMA_BIN")
    return Path(override) if override else ROOT / "node_modules" / ".bin" / "wilma"


def installed_version() -> str | None:
    pkg = ROOT / "node_modules" / PACKAGE / "package.json"
    try:
        return json.loads(pkg.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def version_warning(version: str | None) -> str | None:
    if version is None:
        return f"{PACKAGE} ei ole asennettu: aja `npm install`."
    try:
        major = int(version.split(".")[0])
    except ValueError:
        return f"Tuntematon wilmai-versio: {version}"
    if major != SUPPORTED_MAJOR:
        return f"wilmai {version}: tämä koodi on tarkistettu pääversiolle {SUPPORTED_MAJOR}; tarkista JSON-muodot ja päivitä SUPPORTED_MAJOR."
    return None


def _error_from(text: str, exit_code: int) -> WilmaError | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("status") != "error":
        return None
    code, message = str(data.get("code", "error")), str(data.get("message", ""))
    cls = NotLoggedIn if code == "not_logged_in" else WilmaError
    return cls(code, message, exit_code)


def run(args: Sequence[str], *, env: Mapping[str, str] | None = None, json_output: bool = True, timeout: int = 180) -> Any:
    """Ajaa `wilma <args> [--json]`. Palauttaa jäsennetyn JSONin (tai raakatekstin, jos json_output=False)."""
    binary = wilma_bin()
    if not binary.exists():
        raise WilmaError("not_installed", f"{binary} puuttuu: aja `npm install`.")
    full_env = {**os.environ, "WILMA_NO_UPDATE_CHECK": "1", **cli_env(), **(env or {})}
    cmd = [str(binary), *args, *(["--json"] if json_output else [])]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=full_env, timeout=timeout, cwd=ROOT)
    except subprocess.TimeoutExpired as exc:
        raise WilmaError("timeout", f"wilma ei vastannut {timeout} sekunnissa") from exc
    if proc.returncode != 0:
        for stream in (proc.stderr, proc.stdout):
            err = _error_from(stream, proc.returncode)
            if err:
                raise err
        raise WilmaError("cli_failed", (proc.stderr or proc.stdout).strip()[:500], proc.returncode)
    if not json_output:
        return proc.stdout
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise WilmaError("bad_json", f"CLI ei palauttanut JSONia: {proc.stdout[:200]!r}") from exc
