"""Paikallinen Ollama: ainoa paikka, jonne viestien sisältöä saa lähettää.

Osoite hyväksytään vain, jos se on tämä kone (localhost, 127.0.0.1 tai ::1). Muuten ajo keskeytyy ennen kuin mitään
lähetetään, joten viestien teksti ei voi vahingossa päätyä pilveen väärän asetuksen takia. Malli saa vain tekstin:
ei työkaluja, ei pääsyä kalenteriin tai verkkoon. Asetukset: config.toml, osio [ollama] (url, model).
"""
from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlparse

from . import config

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:12b"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class OllamaError(Exception):
    pass


def settings(cfg: dict | None = None) -> tuple[str, str]:
    o = (config.settings() if cfg is None else cfg).get("ollama", {})
    url = (o.get("url") or DEFAULT_URL).rstrip("/")
    host = urlparse(url).hostname
    if urlparse(url).scheme not in ("http", "https") or host not in LOCAL_HOSTS:
        raise OllamaError(f"Ollama-osoite {url} ei ole tämä kone. Viestejä ei lähetetä minnekään muualle kuin localhostiin.")
    return url, o.get("model") or DEFAULT_MODEL


def status(cfg: dict | None = None) -> str | None:
    """None, jos Ollama vastaa ja malli on ladattu; muuten ihmisluettava syy."""
    try:
        url, model = settings(cfg)
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            names = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except OllamaError as e:
        return str(e)
    except Exception as e:
        return f"Ollama ei vastaa ({type(e).__name__}). Käynnistä: ollama serve"
    if not any(n == model or n.split(":")[0] == model for n in names):
        return f"Mallia {model} ei ole ladattu. Lataa: ollama pull {model}"
    return None


def chat_json(prompt: str, schema: dict, cfg: dict | None = None) -> dict:
    """Kysyy Ollamalta ja palauttaa skeeman mukaisen JSONin. Virheviestiin ei oteta mukaan promptia tai vastausta."""
    url, model = settings(cfg)
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "format": schema,
                       "stream": False, "think": False, "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(url + "/api/chat", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(json.loads(r.read())["message"]["content"])
    except Exception as e:
        raise OllamaError(f"Ollama-kysely epäonnistui ({type(e).__name__})") from None
