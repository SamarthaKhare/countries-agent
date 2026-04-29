"""
LangGraph node functions.

Provider support
----------------
Set LLM_PROVIDER env var:

  Provider    | Free tier              | Env var          | Sign-up
  ------------|------------------------|------------------|---------------------
  groq        | 14,400 req/day FREE    | GROQ_API_KEY     | console.groq.com
  gemini      | 1,500 req/day FREE     | GEMINI_API_KEY   | aistudio.google.com
  anthropic   | Paid only              | ANTHROPIC_API_KEY| console.anthropic.com

Groq and Gemini both expose an OpenAI-compatible endpoint, so we use the
openai SDK for all three — just swapping base_url and model per provider.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from openai import AsyncOpenAI, APIError

from .prompts import (
    IDENTIFY_SYSTEM,
    IDENTIFY_USER,
    SYNTHESIZE_SYSTEM,
    SYNTHESIZE_USER,
)
from .state import AgentState
from .tools import (
    APIConnectionError,
    APIResponseError,
    CountryNotFoundError,
    fetch_country,
)

logger = logging.getLogger(__name__)

# ── Provider configuration ────────────────────────────────────────────────────

_PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-2.0-flash",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-sonnet-4-5",
    },
}

_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

if _PROVIDER not in _PROVIDERS:
    raise ValueError(
        f"Unknown LLM_PROVIDER='{_PROVIDER}'. "
        f"Valid options: {', '.join(_PROVIDERS)}"
    )

_cfg = _PROVIDERS[_PROVIDER]
_api_key = os.getenv(_cfg["api_key_env"], "missing")
_MODEL = _cfg["model"]

_client = AsyncOpenAI(api_key=_api_key, base_url=_cfg["base_url"])

logger.info("LLM provider=%s  model=%s", _PROVIDER, _MODEL)


# ── Shared LLM call helper ────────────────────────────────────────────────────

async def _chat(system: str, user: str, max_tokens: int = 512) -> str:
    """Async chat completion — frees the event loop while waiting for the LLM."""
    response = await _client.chat.completions.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


# ── Node 1 — Intent / Field Identification ───────────────────────────────────

async def identify_node(state: AgentState) -> Dict[str, Any]:
    """Extract country name and requested fields from the user query."""
    query = state["query"]
    logger.info("[identify_node] Parsing query: %r", query)

    try:
        raw_text = await _chat(
            system=IDENTIFY_SYSTEM,
            user=IDENTIFY_USER.format(query=query),
            max_tokens=256,
        )
    except APIError as exc:
        logger.error("[identify_node] LLM error: %s", exc)
        return {
            "error": f"LLM unavailable: {exc}",
            "steps": state.get("steps", []) + ["identify_node: LLM error"],
        }

    logger.debug("[identify_node] Raw output: %s", raw_text)

    try:
        parsed = _parse_json(raw_text)
    except ValueError as exc:
        logger.error("[identify_node] JSON parse failed: %s | raw=%r", exc, raw_text)
        return {
            "error": "Failed to parse intent. Please rephrase your question.",
            "steps": state.get("steps", []) + ["identify_node: JSON parse error"],
        }

    if not parsed.get("is_valid_query", True):
        reason = parsed.get("rejection_reason") or "Query is not about country information."
        return {
            "error": reason,
            "steps": state.get("steps", []) + [f"identify_node: rejected — {reason}"],
        }

    country = parsed.get("country_name")
    fields: List[str] = parsed.get("requested_fields", [])

    if not country:
        return {
            "error": "I couldn't identify a country. Please name a specific country.",
            "steps": state.get("steps", []) + ["identify_node: no country found"],
        }

    step_msg = f"identify_node: country='{country}', fields={fields}"
    logger.info("[identify_node] %s", step_msg)

    return {
        "country_name": country,
        "requested_fields": fields or ["common_name"],
        "steps": state.get("steps", []) + [step_msg],
    }


# ── Node 2 — Tool / API Invocation ───────────────────────────────────────────

async def fetch_node(state: AgentState) -> Dict[str, Any]:
    """Call the REST Countries API and return normalised data."""
    country = state.get("country_name", "")
    logger.info("[fetch_node] Fetching: %r", country)

    try:
        data = await fetch_country(country)
    except CountryNotFoundError as exc:
        msg = f"Country not found: {exc}"
        logger.warning("[fetch_node] %s", msg)
        return {"error": msg, "steps": state.get("steps", []) + [f"fetch_node: {msg}"]}
    except APIConnectionError as exc:
        msg = f"API connection error: {exc}"
        logger.error("[fetch_node] %s", msg)
        return {"error": msg, "steps": state.get("steps", []) + [f"fetch_node: {msg}"]}
    except APIResponseError as exc:
        msg = f"Unexpected API error: {exc}"
        logger.error("[fetch_node] %s", msg)
        return {"error": msg, "steps": state.get("steps", []) + [f"fetch_node: {msg}"]}

    step_msg = f"fetch_node: retrieved data for '{data.get('official_name', country)}'"
    logger.info("[fetch_node] %s", step_msg)
    return {"api_response": data, "steps": state.get("steps", []) + [step_msg]}


# ── Node 3 — Answer Synthesis ────────────────────────────────────────────────

async def synthesize_node(state: AgentState) -> Dict[str, Any]:
    """Generate a grounded natural-language answer from the API payload."""
    query = state["query"]
    fields = state.get("requested_fields", [])
    api_data = state.get("api_response", {})

    logger.info("[synthesize_node] Synthesising | fields=%s", fields)

    try:
        answer = await _chat(
            system=SYNTHESIZE_SYSTEM,
            user=SYNTHESIZE_USER.format(
                query=query,
                fields=", ".join(fields) if fields else "general information",
                country_data=json.dumps(api_data, indent=2, ensure_ascii=False),
            ),
            max_tokens=512,
        )
    except APIError as exc:
        logger.error("[synthesize_node] LLM error: %s", exc)
        return {
            "error": f"LLM unavailable during synthesis: {exc}",
            "steps": state.get("steps", []) + ["synthesize_node: LLM error"],
        }

    step_msg = "synthesize_node: answer generated"
    logger.info("[synthesize_node] %s", step_msg)
    return {"answer": answer, "steps": state.get("steps", []) + [step_msg]}


# ── Routing helper ────────────────────────────────────────────────────────────

def route_after_node(state: AgentState) -> str:
    return "end" if state.get("error") else "continue"


# ── Private helpers ───────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    if text.startswith("```"):
        text = "\n".join(
            l for l in text.splitlines() if not l.strip().startswith("```")
        ).strip()
    return json.loads(text)