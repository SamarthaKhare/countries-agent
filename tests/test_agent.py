"""
Integration tests for the LangGraph agent.

The LLM and HTTP calls are mocked so tests run fast with no external deps.
Run with: pytest tests/test_agent.py -v
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.state import initial_state
from agent.nodes import identify_node, fetch_node, synthesize_node


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_llm_response(text: str):
    """Build a minimal OpenAI SDK response object (used by all providers via openai SDK)."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    return response

def _async_llm_response(text: str):
    """Wrap _make_llm_response in an AsyncMock so await works on the patched client."""
    mock = AsyncMock()
    mock.return_value = _make_llm_response(text)
    return mock


GERMANY_DATA = {
    "common_name": "Germany",
    "official_name": "Federal Republic of Germany",
    "capital": ["Berlin"],
    "population": 83240525,
    "area_km2": 357114.0,
    "region": "Europe",
    "subregion": "Western Europe",
    "currencies": [{"code": "EUR", "name": "Euro", "symbol": "€"}],
    "languages": ["German"],
    "timezones": ["UTC+01:00"],
    "borders": ["AUT", "BEL"],
    "flag_emoji": "🇩🇪",
    "flag_png": "https://flagcdn.com/de.png",
    "cca2": "DE",
    "cca3": "DEU",
    "latlng": [51.0, 9.0],
}


# ── identify_node tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_identify_node_success():
    state = initial_state("What is the population of Germany?")
    llm_json = json.dumps({
        "country_name": "Germany",
        "requested_fields": ["population"],
        "is_valid_query": True,
        "rejection_reason": None,
    })

    with patch("agent.nodes._client") as mock_client:
        mock_client.chat.completions.create = _async_llm_response(llm_json)
        result = await identify_node(state)

    assert result["country_name"] == "Germany"
    assert "population" in result["requested_fields"]
    assert result.get("error") is None
    assert len(result["steps"]) == 1


@pytest.mark.asyncio
async def test_identify_node_invalid_query():
    state = initial_state("Write me a poem about dogs.")
    llm_json = json.dumps({
        "country_name": None,
        "requested_fields": [],
        "is_valid_query": False,
        "rejection_reason": "Query is not about a country.",
    })

    with patch("agent.nodes._client") as mock_client:
        mock_client.chat.completions.create = _async_llm_response(llm_json)
        result = await identify_node(state)

    assert result.get("error") is not None
    assert "country" in result["error"].lower() or "query" in result["error"].lower()


@pytest.mark.asyncio
async def test_identify_node_no_country():
    state = initial_state("What is the biggest city in Europe?")
    llm_json = json.dumps({
        "country_name": None,
        "requested_fields": ["capital"],
        "is_valid_query": True,
        "rejection_reason": None,
    })

    with patch("agent.nodes._client") as mock_client:
        mock_client.chat.completions.create = _async_llm_response(llm_json)
        result = await identify_node(state)

    assert result.get("error") is not None


# ── fetch_node tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_node_success():
    state = initial_state("What is the population of Germany?")
    state["country_name"] = "Germany"
    state["steps"] = []

    with patch("agent.nodes.fetch_country", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = GERMANY_DATA
        result = await fetch_node(state)

    assert result["api_response"]["common_name"] == "Germany"
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_fetch_node_country_not_found():
    from agent.tools import CountryNotFoundError

    state = initial_state("What is the capital of Narnia?")
    state["country_name"] = "Narnia"
    state["steps"] = []

    with patch("agent.nodes.fetch_country", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = CountryNotFoundError("No country found matching 'Narnia'.")
        result = await fetch_node(state)

    assert result.get("error") is not None
    assert "narnia" in result["error"].lower() or "not found" in result["error"].lower()


# ── synthesize_node tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_node_success():
    state = initial_state("What is the population of Germany?")
    state["country_name"] = "Germany"
    state["requested_fields"] = ["population"]
    state["api_response"] = GERMANY_DATA
    state["steps"] = []

    expected_answer = "The population of Germany is approximately 83,240,525."

    with patch("agent.nodes._client") as mock_client:
        mock_client.chat.completions.create = _async_llm_response(expected_answer)
        result = await synthesize_node(state)

    assert result["answer"] == expected_answer
    assert result.get("error") is None


# ── Full graph integration test ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_graph_happy_path():
    """End-to-end: LLM + API both mocked, graph should reach synthesize."""
    from agent.graph import build_graph

    identify_json = json.dumps({
        "country_name": "Germany",
        "requested_fields": ["population"],
        "is_valid_query": True,
        "rejection_reason": None,
    })
    final_answer = "Germany has a population of approximately 83,240,525."

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        text = identify_json if call_count == 1 else final_answer
        return _make_llm_response(text)

    graph = build_graph()

    with patch("agent.nodes._client") as mock_client, \
         patch("agent.nodes.fetch_country", new_callable=AsyncMock) as mock_fetch:
        mock_client.chat.completions.create = fake_create
        mock_fetch.return_value = GERMANY_DATA

        result = await graph.ainvoke(initial_state("What is the population of Germany?"))

    assert result["answer"] == final_answer
    assert result["country_name"] == "Germany"
    assert result.get("error") is None
    assert len(result["steps"]) == 3  # one per node
