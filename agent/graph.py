"""
LangGraph state graph for the Countries Agent.

Graph topology
--------------

    START
      │
      ▼
  identify_node  ──(error)──► END
      │
      │ (success)
      ▼
  fetch_node     ──(error)──► END
      │
      │ (success)
      ▼
  synthesize_node ──────────► END

Each node returns a partial AgentState dict; LangGraph merges updates.
Conditional edges call `route_after_node` which checks for `state["error"]`.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from .nodes import fetch_node, identify_node, route_after_node, synthesize_node
from .state import AgentState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """
    Assemble and compile the LangGraph StateGraph.

    Returns
    -------
    StateGraph
        A compiled graph ready to be invoked with `.ainvoke(state)`.
    """
    builder = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────
    builder.add_node("identify", identify_node)
    builder.add_node("fetch", fetch_node)
    builder.add_node("synthesize", synthesize_node)

    # ── Entry point ───────────────────────────────────────────────────────
    builder.set_entry_point("identify")

    # ── Conditional edge: identify → (fetch | END) ────────────────────────
    builder.add_conditional_edges(
        "identify",
        route_after_node,
        {
            "continue": "fetch",
            "end": END,
        },
    )

    # ── Conditional edge: fetch → (synthesize | END) ──────────────────────
    builder.add_conditional_edges(
        "fetch",
        route_after_node,
        {
            "continue": "synthesize",
            "end": END,
        },
    )

    # ── Terminal edge: synthesize → END ───────────────────────────────────
    builder.add_edge("synthesize", END)

    graph = builder.compile()
    logger.info("LangGraph compiled successfully | nodes=%s", ["identify", "fetch", "synthesize"])
    return graph


# Module-level singleton — compiled once at import time and reused.
_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    """Return the module-level compiled graph, creating it on first call."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
