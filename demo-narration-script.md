# Countries Agent — Video Demo Narration Script

> **Recording tips:** Aim for ~8–10 minutes total. Open the PPTX in presenter view so you can read
> notes while the audience sees the slide. Run `python main.py` in a terminal before recording so
> the server is live and ready for the live demo segment.

---

## Slide 1 — Title  (~30 s)

"Hi everyone — today I'm walking you through the Countries Agent, a production-grade AI agent I
built using LangGraph and Groq. It takes any natural-language question about a country and returns
a grounded, accurate answer by combining a large language model with live data from the REST
Countries API. Let's jump in."

---

## Slide 2 — Architecture Overview  (~90 s)

"The system is built as a LangGraph StateGraph — three nodes wired together with conditional edges,
all wrapped inside a FastAPI server.

The first node, IDENTIFY, sends the user's query to Groq's LLaMA 3.3 70B model and gets back a
structured JSON telling us which country was mentioned and what the user is asking about.

The second node, FETCH, makes an HTTP call to the REST Countries API and normalises the raw,
inconsistently-structured payload into a clean Python dict.

The third node, SYNTHESIZE, sends that clean data back to the LLM and asks it to produce a
natural-language answer grounded purely in what the API returned.

The dashed red arrows show the error path — if any node sets an error field, LangGraph's
conditional edge skips all remaining nodes and routes straight to END. No exception bubbling,
no try/except chains across the graph.

At the bottom, FastAPI exposes this as a REST API with a POST endpoint, a health check, and a
full Swagger UI."

---

## Slide 3 — The Three-Node Pipeline  (~60 s)

"Let me zoom into each node.

IDENTIFY is the only node that knows about the user's intent. It calls Groq, parses the JSON
response, validates that the query is actually about a country, and hands off a clean
country_name and list of requested fields. If the query is something like 'write me a poem about
dogs', it rejects it here before anything else runs.

FETCH has no LLM at all. It's a pure I/O node — call the API, handle errors, normalise the
schema. Keeping the LLM out of this node means it's fast, deterministic, and easy to test with
mocked HTTP.

SYNTHESIZE receives the API data and the original query and produces the final answer. Crucially,
the prompt instructs it to only use the data it was given — so the answer is always grounded in
real API data, not the model's training knowledge."

---

## Slide 4 — Example Flow: Germany Population  (~75 s)

"Let's trace a real query end to end — 'What is the population of Germany?'

IDENTIFY parses this and returns country_name: Germany, requested_fields: population,
is_valid_query: true. Clean, structured output.

FETCH calls restcountries.com, gets the raw response, normalises it into our AgentState dict.
We get common_name Germany, population 83,240,525, plus all the other fields.

SYNTHESIZE takes that dict and the original query and produces: 'The population of Germany is
approximately 83,240,525.' Accurate, grounded, no hallucination possible because the number came
directly from the API.

The full round-trip — including two LLM calls — typically takes under two seconds."

---

## Slide 5 — Example Flow: Error Handling  (~60 s)

"Now let's see what happens with a query the system can't answer — 'What is the capital of Narnia?'

IDENTIFY actually passes this — Narnia looks syntactically like a country name, and the query
structure is valid. is_valid_query is true.

FETCH calls the API and gets a 404. The tools layer catches this and raises CountryNotFoundError,
sets the error field on the state, and returns.

The conditional edge fires. It sees error is set and routes directly to END — SYNTHESIZE is never
called. The API response contains the error message and success: false.

This is the key benefit of explicit error routing in LangGraph — every failure mode is a
first-class graph path, not an exception you hope gets caught somewhere."

---

## Slide 6 — Production Behaviour  (~60 s)

"A few things that make this production-ready rather than a prototype.

The Dockerfile uses a two-stage build — dependencies are compiled in a builder stage, then only
the runtime artifacts are copied into the final python:3.12-slim image. The app runs as a
non-root user.

FastAPI gives us auto-generated Swagger docs at /docs, request validation via Pydantic, and a
health check endpoint the container orchestrator can poll.

Every error type has its own exception class — CountryNotFoundError, APIConnectionError,
APIResponseError — so error messages are user-friendly rather than raw stack traces.

The response includes a steps list, duration_ms, and logs the LLM provider at startup, so
you can see exactly what the agent did on each request."

---

## Slide 7 — Limitations & Trade-offs  (~75 s)

"Let me be upfront about the limitations.

The biggest one is that the agent is stateless — each query is independent, there's no
conversation memory. If you ask 'What's its capital?' as a follow-up, the agent has no context
from the previous turn.

Country disambiguation is delegated to the REST API's fuzzy search, which means ambiguous names
like 'Congo' just return the first match without asking for clarification.

And the IDENTIFY node is synchronous — it blocks the async event loop while waiting for the LLM
response. For a high-traffic production service you'd want to make that call properly async.

On the trade-off side — LangGraph was the right call here because each concern is isolated.
Each node is unit-tested independently with mocked I/O, and you can swap any node without
touching the others.

Using the OpenAI SDK for all three providers keeps the dependency surface minimal. You switch
from Groq to Gemini or Anthropic with a single environment variable change."

---

## Slide 8 — Try It Locally  (~60 s)

"Running it locally takes about thirty seconds.

Install the dependencies, add your Groq API key to the .env file, and run python main.py.
The server starts on port 8000.

[Switch to browser — open http://localhost:8000]

You can see the chat UI right here. Let me try a query — 'What languages are spoken in Switzerland?'

[Type query, show response]

You can also hit the Swagger UI at /docs and POST directly to /api/query to see the full JSON
response including the steps trace and duration.

The repo is public at github.com/SamarthaKhare/countries-agent — all the code, tests, and docs
are there.

Thanks for watching."

---

*Total estimated runtime: ~8–9 minutes*
