"""
REST Countries API client.

Responsibilities
----------------
* All HTTP I/O with https://restcountries.com lives here and nowhere else.
* Raises typed exceptions so nodes can branch on specific failure modes.
* Extracts a normalised subset of fields to keep downstream nodes simple.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://restcountries.com/v3.1"

# Fields we actually request from the API (reduces payload size)
_API_FIELDS = (
    "name,capital,population,currencies,languages,region,subregion,"
    "area,flag,flags,timezones,borders,latlng,cca2,cca3"
)


# ── Custom exceptions ────────────────────────────────────────────────────────


class CountryNotFoundError(Exception):
    """Raised when the API returns 404 for a given country name."""


class APIConnectionError(Exception):
    """Raised when the REST Countries service is unreachable."""


class APIResponseError(Exception):
    """Raised for unexpected non-404 HTTP error codes."""


# ── Public interface ─────────────────────────────────────────────────────────


async def fetch_country(country_name: str) -> Dict[str, Any]:
    """
    Fetch and return the *best-match* country record from REST Countries.

    Parameters
    ----------
    country_name:
        Plain-text country name exactly as extracted by the identification node.

    Returns
    -------
    dict
        Normalised country record (see `_normalise`).

    Raises
    ------
    CountryNotFoundError
        When no country matches the given name.
    APIConnectionError
        When the upstream service is unreachable.
    APIResponseError
        For unexpected HTTP errors (5xx, etc.).
    """
    url = f"{_BASE_URL}/name/{country_name}"
    params = {"fields": _API_FIELDS}

    logger.info("Fetching country data | country=%s url=%s", country_name, url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
    except httpx.ConnectError as exc:
        raise APIConnectionError(
            "Cannot reach restcountries.com. Check network connectivity."
        ) from exc
    except httpx.TimeoutException as exc:
        raise APIConnectionError(
            "Request to restcountries.com timed out after 10 s."
        ) from exc

    if response.status_code == 404:
        raise CountryNotFoundError(
            f"No country found matching '{country_name}'."
        )

    if response.status_code != 200:
        raise APIResponseError(
            f"Unexpected status {response.status_code} from REST Countries API."
        )

    payload = response.json()

    if not payload:
        raise CountryNotFoundError(f"Empty result for '{country_name}'.")

    # The API returns a list; take the first (best-match) result.
    raw = payload[0]
    logger.info("Country data fetched | official_name=%s", raw.get("name", {}).get("official"))
    return _normalise(raw)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _normalise(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten and clean the raw API record into a consistent shape.

    This prevents downstream nodes from having to navigate deeply-nested
    structures and shields them from optional-field inconsistencies.
    """
    name_block = raw.get("name", {})
    currencies_raw = raw.get("currencies", {})
    languages_raw = raw.get("languages", {})
    flags_raw = raw.get("flags", {})

    # Currencies → list of {"code": ..., "name": ..., "symbol": ...}
    currencies = [
        {
            "code": code,
            "name": info.get("name", "Unknown"),
            "symbol": info.get("symbol", ""),
        }
        for code, info in currencies_raw.items()
    ]

    # Languages → list of names
    languages = list(languages_raw.values())

    return {
        "common_name": name_block.get("common", "Unknown"),
        "official_name": name_block.get("official", "Unknown"),
        "capital": raw.get("capital", []),          # list; some countries multi-capital
        "population": raw.get("population"),
        "area_km2": raw.get("area"),
        "region": raw.get("region"),
        "subregion": raw.get("subregion"),
        "currencies": currencies,
        "languages": languages,
        "timezones": raw.get("timezones", []),
        "borders": raw.get("borders", []),          # ISO cca3 codes
        "flag_emoji": raw.get("flag", ""),
        "flag_png": flags_raw.get("png", ""),
        "cca2": raw.get("cca2", ""),
        "cca3": raw.get("cca3", ""),
        "latlng": raw.get("latlng", []),
    }
