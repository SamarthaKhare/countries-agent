# Countries Agent

A production-grade AI agent built with **LangGraph** and **Python** that answers natural-language questions about any country using live data from the [REST Countries API](https://restcountries.com).

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                  LangGraph StateGraph                │
│                                                     │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────┐ │
│  │  IDENTIFY   │──▶│    FETCH     │──▶│SYNTHESIZE│ │
│  │   (Groq)    │   │(REST API)    │   │  (Groq)  │ │
│  └─────────────┘   └──────────────┘   └──────────┘ │
│        │                  │                         │
│     (error)            (error)                      │
│        └──────────────────┴──────────────► END      │
└─────────────────────────────────────────────────────┘
    │
    ▼
FastAPI → JSON Response
```

### Node Responsibilities

| Node | Purpose | LLM? | External I/O? |
|------|---------|------|---------------|
| **identify** | Parse query → extract `country_name` + `requested_fields` | ✅ Groq (LLaMA) | ❌ |
| **fetch** | Call REST Countries API, normalise payload | ❌ | ✅ restcountries.com |
| **synthesize** | Ground answer from API data | ✅ Groq (LLaMA) | ❌ |

### State Shape

```python
class AgentState(TypedDict):
    query: str                    # Raw user input
    country_name: Optional[str]  # Extracted by identify node
    requested_fields: List[str]  # e.g. ["population", "capital"]
    api_response: Optional[dict] # Normalised REST Countries payload
    answer: Optional[str]        # Final natural-language answer
    error: Optional[str]         # Set on failure; triggers early exit
    steps: List[str]             # Human-readable workflow trace
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com/) — free tier includes 14,400 requests/day

### Local Setup

```bash
# 1. Clone
git clone https://github.com/your-org/countries-agent.git
cd countries-agent

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 5. Run
export GROQ_API_KEY=gsk_...
python main.py
```

Open http://localhost:8000 in your browser.

### Docker

```bash
docker compose up --build
```

---

## API Reference

### `POST /api/query`

Run the agent for a given question.

**Request**
```json
{ "query": "What currency does Japan use?" }
```

**Response**
```json
{
  "query": "What currency does Japan use?",
  "answer": "Japan's official currency is the Japanese Yen (¥), currency code JPY.",
  "country_name": "Japan",
  "requested_fields": ["currencies"],
  "steps": [
    "identify_node: country='Japan', fields=['currencies']",
    "fetch_node: retrieved data for 'Japan'",
    "synthesize_node: answer generated"
  ],
  "error": null,
  "duration_ms": 1832.4,
  "success": true
}
```

### `GET /api/health`

Returns `{"status": "ok", "version": "1.0.0"}`.

### `GET /docs`

Interactive Swagger UI for the API.

---

## Example Queries

| Query | Fields resolved |
|-------|----------------|
| What is the population of Germany? | `population` |
| What currency does Japan use? | `currencies` |
| What is the capital and area of Brazil? | `capital`, `area_km2` |
| What languages are spoken in Switzerland? | `languages` |
| Which region is Kenya in? | `region`, `subregion` |
| What are France's neighbouring countries? | `borders` |

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Fake / misspelled country | REST API returns 404 → `CountryNotFoundError` → user-friendly message |
| Network unreachable | `APIConnectionError` → user-friendly message |
| Ambiguous intent | LLM returns `is_valid_query: false` → rejection message |
| Missing API field | LLM notes the absence in the answer ("The API did not return X") |
| LLM outage | `openai.APIError` caught → error propagated cleanly |

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## LLM Provider

The agent uses Groq by default (`LLM_PROVIDER=groq`), running **LLaMA 3.3 70B**. Two other providers are supported by setting the `LLM_PROVIDER` environment variable:

| Provider | Env var | Free tier | Model |
|----------|---------|-----------|-------|
| `groq` (default) | `GROQ_API_KEY` | 14,400 req/day | `llama-3.3-70b-versatile` |
| `gemini` | `GEMINI_API_KEY` | 1,500 req/day | `gemini-2.0-flash` |
| `anthropic` | `ANTHROPIC_API_KEY` | Paid only | `claude-sonnet-4-5` |

All providers use the OpenAI-compatible endpoint via the `openai` SDK — only the `base_url`, `api_key`, and `model` change per provider.

---

## Design Decisions & Trade-offs

**Why LangGraph over a single prompt?**
Each step has a distinct concern: parsing, I/O, and synthesis. Separating them means each can be tested, monitored, and swapped independently. The graph also makes error routing explicit via conditional edges.

**Why the OpenAI SDK for all providers?**
Groq and Gemini both expose an OpenAI-compatible REST endpoint, so a single `openai.OpenAI(base_url=..., api_key=...)` client works for all three providers. This keeps the dependency surface small and avoids provider-specific SDKs.

**Why normalise the API payload?**
The raw REST Countries schema is deeply nested and inconsistent (e.g. optional fields vary by country). Normalising once in `tools.py` shields all downstream code from these inconsistencies.

**Limitations**
- No conversation history — each query is stateless.
- Country disambiguation is handled by the REST API's fuzzy search; very ambiguous names (e.g. "Congo") return the first match.
- Rate limits are determined by your Groq plan (14,400 req/day on the free tier).

---

## Project Structure

```
countries-agent/
├── agent/
│   ├── __init__.py       # Public API
│   ├── state.py          # AgentState TypedDict + initial_state()
│   ├── tools.py          # REST Countries API client + custom exceptions
│   ├── prompts.py        # All LLM prompt templates
│   ├── nodes.py          # identify_node, fetch_node, synthesize_node
│   └── graph.py          # LangGraph StateGraph assembly
├── api/
│   ├── __init__.py
│   └── server.py         # FastAPI application
├── static/
│   └── index.html        # Frontend UI
├── tests/
│   ├── test_tools.py     # Unit tests (mocked HTTP)
│   └── test_agent.py     # Integration tests (mocked LLM + HTTP)
├── main.py               # Entry point + env validation
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```
