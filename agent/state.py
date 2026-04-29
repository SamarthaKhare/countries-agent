"""
AgentState — the single source of truth passed between every LangGraph node.

Design decisions
----------------
* Uses TypedDict so LangGraph can merge partial updates returned by nodes.
* All fields are Optional with explicit defaults so nodes can be tested in
  isolation without constructing a full state object.
* `steps` accumulates a human-readable trace of what each node did; this is
  surfaced to the API caller so the UI can show the reasoning chain.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # ── Input ──────────────────────────────────────────────────────────────
    query: str                         # Raw user question, never mutated

    # ── Identification node output ─────────────────────────────────────────
    country_name: Optional[str]        # Normalised country name for API call
    requested_fields: List[str]        # e.g. ["population", "capital"]

    # ── Fetch node output ──────────────────────────────────────────────────
    api_response: Optional[Dict[str, Any]]   # Raw REST Countries payload

    # ── Synthesis node output ─────────────────────────────────────────────
    answer: Optional[str]              # Final natural-language answer

    # ── Error handling ─────────────────────────────────────────────────────
    error: Optional[str]               # Set by any node on failure

    # ── Observability ─────────────────────────────────────────────────────
    steps: List[str]                   # Ordered log of node actions


def initial_state(query: str) -> AgentState:
    """Return a fully-initialised state dict for a new query."""
    return AgentState(
        query=query,
        country_name=None,
        requested_fields=[],
        api_response=None,
        answer=None,
        error=None,
        steps=[],
    )
