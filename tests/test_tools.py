"""
Unit tests for agent/tools.py.

Tests use httpx's built-in mock transport so no real HTTP calls are made.
Run with: pytest tests/test_tools.py -v
"""

from __future__ import annotations

import json
import pytest
import httpx

from agent.tools import (
    CountryNotFoundError,
    APIConnectionError,
    APIResponseError,
    fetch_country,
    _normalise,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

GERMANY_RAW = {
    "name": {"common": "Germany", "official": "Federal Republic of Germany"},
    "capital": ["Berlin"],
    "population": 83240525,
    "area": 357114.0,
    "region": "Europe",
    "subregion": "Western Europe",
    "currencies": {"EUR": {"name": "Euro", "symbol": "€"}},
    "languages": {"deu": "German"},
    "timezones": ["UTC+01:00"],
    "borders": ["AUT", "BEL", "CZE", "DNK", "FRA", "LUX", "NLD", "POL", "CHE"],
    "flag": "🇩🇪",
    "flags": {"png": "https://flagcdn.com/w320/de.png"},
    "cca2": "DE",
    "cca3": "DEU",
    "latlng": [51.0, 9.0],
}

GERMANY_RESPONSE = [GERMANY_RAW]


def _make_transport(status: int, body) -> httpx.MockTransport:
    """Build a mock httpx transport that always returns the given status/body."""
    content = json.dumps(body).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content)

    return httpx.MockTransport(handler)


# ── Tests: _normalise ─────────────────────────────────────────────────────────


def test_normalise_basic_fields():
    result = _normalise(GERMANY_RAW)
    assert result["common_name"] == "Germany"
    assert result["official_name"] == "Federal Republic of Germany"
    assert result["population"] == 83240525
    assert result["capital"] == ["Berlin"]
    assert result["region"] == "Europe"
    assert result["cca2"] == "DE"
    assert result["flag_emoji"] == "🇩🇪"


def test_normalise_currencies():
    result = _normalise(GERMANY_RAW)
    assert len(result["currencies"]) == 1
    eur = result["currencies"][0]
    assert eur["code"] == "EUR"
    assert eur["name"] == "Euro"
    assert eur["symbol"] == "€"


def test_normalise_languages():
    result = _normalise(GERMANY_RAW)
    assert "German" in result["languages"]


def test_normalise_missing_optional_fields():
    """Fields not present in raw data should default gracefully."""
    minimal = {"name": {"common": "Testland", "official": "Republic of Testland"}}
    result = _normalise(minimal)
    assert result["common_name"] == "Testland"
    assert result["capital"] == []
    assert result["currencies"] == []
    assert result["languages"] == []
    assert result["population"] is None


# ── Tests: fetch_country (mocked HTTP) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_country_success(monkeypatch):
    """fetch_country should return a normalised dict on 200."""
    import httpx as _httpx

    class MockAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, **kwargs):
            return httpx.Response(200, content=json.dumps(GERMANY_RESPONSE).encode())

    monkeypatch.setattr(_httpx, "AsyncClient", MockAsyncClient)
    result = await fetch_country("germany")
    assert result["common_name"] == "Germany"
    assert result["population"] == 83240525


@pytest.mark.asyncio
async def test_fetch_country_not_found(monkeypatch):
    """fetch_country should raise CountryNotFoundError on 404."""
    import httpx as _httpx

    class MockAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, **kwargs):
            return httpx.Response(404, content=b'{"status":404,"message":"Not Found"}')

    monkeypatch.setattr(_httpx, "AsyncClient", MockAsyncClient)
    with pytest.raises(CountryNotFoundError):
        await fetch_country("notacountry")


@pytest.mark.asyncio
async def test_fetch_country_connection_error(monkeypatch):
    """fetch_country should raise APIConnectionError on network failure."""
    import httpx as _httpx

    class MockAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, **kwargs):
            raise _httpx.ConnectError("connection refused")

    monkeypatch.setattr(_httpx, "AsyncClient", MockAsyncClient)
    with pytest.raises(APIConnectionError):
        await fetch_country("germany")


@pytest.mark.asyncio
async def test_fetch_country_server_error(monkeypatch):
    """fetch_country should raise APIResponseError on 5xx."""
    import httpx as _httpx

    class MockAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, **kwargs):
            return httpx.Response(503, content=b"Service Unavailable")

    monkeypatch.setattr(_httpx, "AsyncClient", MockAsyncClient)
    with pytest.raises(APIResponseError):
        await fetch_country("germany")
