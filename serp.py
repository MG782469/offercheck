"""Thin SerpApi client with an on-disk cache.

Every query is cached by its parameters (never by the API key), so re-running an
investigation costs no credits and the bundled demo cache lets anyone try the app
without a key.
"""
import hashlib
import json
import os
import pathlib

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
CACHE_DIR = pathlib.Path(os.getenv("OFFERCHECK_CACHE_DIR", pathlib.Path(__file__).parent / "cache"))

# SerpApi reports "no results" as an error string; for us that is just an empty result.
_EMPTY_RESULT_HINTS = ("hasn't returned any results", "no results")


class SerpApiError(Exception):
    pass


def _cache_path(params: dict) -> pathlib.Path:
    stable = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{params.get('engine', 'google')}_{digest}.json"


def search(params: dict) -> tuple[dict, bool]:
    """Run a SerpApi search. Returns (data, from_cache)."""
    params = {k: v for k, v in params.items() if v not in (None, "")}
    path = _cache_path(params)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), True

    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise SerpApiError("SERPAPI_API_KEY is not set and this query is not in the cache.")

    data, last_exc = None, None
    for _attempt in range(2):  # SerpApi occasionally takes long on a cold query; retry once
        try:
            resp = requests.get(SERPAPI_URL, params={**params, "api_key": api_key}, timeout=75)
            data = resp.json()
            break
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
    if data is None:
        raise SerpApiError(f"SerpApi request failed: {last_exc}")

    error = data.get("error")
    if error:
        if any(hint in error.lower() for hint in _EMPTY_RESULT_HINTS):
            data = {"_empty": True}
        else:
            raise SerpApiError(error)

    # search_metadata contains request URLs; drop it so nothing account-specific is cached.
    data.pop("search_metadata", None)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data, False
