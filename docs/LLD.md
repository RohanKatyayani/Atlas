# Atlas: Low Level Design

Author: Rohan Katyayani. Started 25 October 2026.

## 1. Overview

Atlas is a text-based chief-of-staff agent: you ask "what's going on today?" and an
orchestrator agent queries your mail, calendar, documents and a credit risk model in
parallel, then answers with every claim traced to its source. It brings orchestration, MCP,
tool calling and RAG together in one system, built in about a month at zero cost.

**Goals**

- One orchestrator (Google ADK) that plans a request and delegates to specialist sub-agents.
- Four MCP servers written from scratch: Calendar, Gmail, Knowledge (RAG) and Risk (FinRisk Copilot model).
- A model routing layer with a free default model and automatic fallback.
- Enterprise-grade controls: human approval before any write action, a full audit trail, PII masking before text reaches a model.
- An evaluation suite with tracked scores, so every claim in the README is measured.

**Non-goals (v1)**

- No voice. Text only.
- No real personal data. Atlas runs against a dedicated demo Google account seeded with fictional mail and meetings.
- No multi-user tenancy or production hosting. A Docker Compose stack that runs locally, plus a recorded demo.

**Done means**

- `docker compose up` starts Atlas; the briefing question returns a cited answer in under 30 seconds.
- Write actions (send email, create event) never execute without an explicit approval.
- The eval suite runs on demand and its scores are in the README.

## 2. Architecture

![Atlas architecture](img/architecture.png)

Each agent reaches exactly one MCP server, so permissions are enforced by structure, not by
prompt. Every model call goes through ModelRouter, and every tool call passes the safety
callbacks first.

**Request lifecycle**

1. The user asks a question in the chat UI; the ADK runner loads the session from SQLite.
2. The Coordinator, running on the model ModelRouter picks, decides which agents to call, or runs BriefingFlow.
3. Each agent calls tools on its own MCP server over streamable HTTP; `before_tool_callback` logs the call and applies policy first.
4. The server validates input, calls the external API, masks PII and returns a result with a `source_id`.
5. A write tool pauses the run for approval; nothing is sent until the user approves.
6. The Coordinator composes the answer with citations; `after_tool_callback` closes each audit row.

## 3. Tech stack

Every component is open source or on a free tier, so the running cost is zero. OpenAI stays
switchable but off by default.

| Layer | Choice | Why | Cost |
| --- | --- | --- | --- |
| Agent framework | [Google ADK](https://adk.dev/) (Python) | Agent tree, workflow agents, sessions, callbacks, tool confirmation and evals in one framework | Free, open source |
| Tool protocol | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP) | Each data source is its own server; ADK connects through `McpToolset` | Free, open source |
| Transport | Streamable HTTP (stdio for unit tests) | Servers run as separate containers, like real services | Free |
| Default model | A Gemini Flash model on the free tier | Fast, strong tool calling, native to ADK | Free tier, rate limited |
| Fallback models | Groq (hosted open models), then Ollama locally | Keeps working when Gemini returns 429 | Free tier / free |
| Model adapter | ADK `LiteLlm` wrapper over [LiteLLM](https://adk.dev/agents/models/litellm/) | One interface for every provider | Free, open source |
| Mail and calendar | Gmail API, Google Calendar API | Real OAuth, real APIs | Free |
| Knowledge | ChromaDB + local sentence-transformers embeddings | Reuses the MindForge retrieval code | Free |
| Risk | FinRisk Copilot LightGBM model from the Hugging Face Hub | Reuses an existing model as a tool | Free |
| PII masking | Microsoft Presidio + regex rules | Open source, explainable, no data leaves the box | Free |
| Sessions and audit | SQLite (ADK `DatabaseSessionService`) | Zero setup; Postgres is a one-line swap | Free |
| Tracking | MLflow | Eval scores per commit | Free |
| Packaging and CI | Docker Compose, GitHub Actions, uv, ruff, pytest | Standard, reproducible | Free (public repo) |

**Free-tier constraints that shape the design**

- Gemini free-tier limits are set per model and per project and change over time; check
  your project's page in Google AI Studio. The router, caching and fallback chain exist
  because of this.
- Google only guarantees prompts are not used to improve its products once billing is set
  up ([Gemini billing docs](https://ai.google.dev/gemini-api/docs/billing)). Hence the
  demo account and fictional data rule.
- A Google OAuth app left in Testing status issues refresh tokens that expire after 7 days.
  Atlas detects the expired token and prints a one-command re-auth instead of failing silently.

## 4. Repository layout

```
atlas/
  CLAUDE.md              working rules for AI-assisted development
  README.md
  docker-compose.yml     agent + 4 MCP servers + MLflow
  pyproject.toml         uv workspace
  docs/
    LLD.md               this design
    learning-log.md      checkpoint results
    adr/                 one short file per architecture decision
  agent/atlas/
    agent.py             root agent tree (ADK entry point, root_agent)
    subagents/           mail.py, calendar.py, knowledge.py, risk.py, synthesizer.py
    router.py            ModelRouter: primary model, fallback chain, 429 handling
    callbacks.py         audit, policy and PII callbacks
    prompts/             instruction text per agent, versioned
    api.py               FastAPI app (ADK get_fast_api_app) for the UI
  servers/
    calendar_mcp/        server.py, google_client.py, tests/
    gmail_mcp/           server.py, google_client.py, tests/
    knowledge_mcp/       server.py, ingest.py, store.py, tests/
    risk_mcp/            server.py, model.py, tests/
    common/              auth.py (OAuth), pii.py (masking), schemas.py
  evals/
    datasets/            *.evalset.json
    run_evals.py         runs ADK evals + grounding check, logs to MLflow
  scripts/
    seed_dummy_account.py  fictional mails and meetings for the demo persona
    auth_google.py         one-time OAuth flow, writes token.json
  ui/                    small React chat with approve and reject buttons
  tests/                 agent-level tests with a fake model
```

## 5. MCP servers

Four servers, 13 tools, 2 of them writes. Every tool returns a typed result with a
`source_id` (message id, event id, chunk id or model version) so the final answer can cite
it. Every server also exposes at least one MCP resource and one MCP prompt, so Atlas uses
all three MCP primitives.

| Server | Tool | Input | Output | Write? |
| --- | --- | --- | --- | --- |
| calendar | `list_events` | `start`, `end` (ISO dates) | events: id, title, start, end, attendees | No |
| calendar | `find_free_slots` | `date`, `duration_min` | free slots inside working hours | No |
| calendar | `get_event` | `event_id` | full event with description | No |
| calendar | `create_event` | `title`, `start`, `end`, `attendees` | created event id | **Yes, needs approval** |
| gmail | `search_messages` | Gmail query, `max_results` (cap 20) | id, from, subject, date, snippet (PII masked) | No |
| gmail | `get_thread` | `thread_id` | messages in order, bodies masked and truncated | No |
| gmail | `list_unread_important` | `since` | unread important messages | No |
| gmail | `send_email` | `to`, `subject`, `body`, `reply_to_id`? | sent message id | **Yes, needs approval** |
| knowledge | `search_docs` | `query`, `k` (cap 8) | chunks: text, doc title, page, `chunk_id`, score | No |
| knowledge | `list_docs` | none | indexed documents | No |
| risk | `score_applicant` | applicant features (validated schema) | probability of default, decision, model version | No |
| risk | `explain_score` | `score_id` | plain-English drivers (LoRA explainer, optional) | No |
| risk | `model_card` | none | metrics, training data, known limits | No |

- Resources: `calendar://today`, `gmail://inbox/summary`, `knowledge://catalog`, `risk://model-card`.
- Prompts: `daily_briefing`, `meeting_prep(event_id)`, `draft_reply(thread_id)`.

**Error contract (all servers)**

- Structured tool errors with a `code`: `AUTH_EXPIRED`, `RATE_LIMITED`, `NOT_FOUND`,
  `INVALID_INPUT`, `UPSTREAM_ERROR`. The agent tells the user what failed and never guesses
  missing data.
- Inputs validated with Pydantic before any API call; result sizes capped.
- Servers run as separate containers on ports 8101 to 8104, each with a `/health` route.

## 6. Orchestration

Two orchestration styles, on purpose: a fixed workflow for the daily briefing (predictable,
cheap, testable) and LLM-driven delegation for open questions (flexible).

**Path A: briefing workflow (deterministic)**

1. `BriefingFlow` is an ADK `SequentialAgent` with two steps.
2. Step 1 is a `ParallelAgent` running `MailAgent`, `CalendarAgent` and `KnowledgeAgent`
   concurrently. Each writes to session state via `output_key` (`mail_digest`,
   `calendar_digest`, `doc_hits`).
3. Step 2 is `SynthesizerAgent`, whose instruction reads `{mail_digest}`,
   `{calendar_digest}` and `{doc_hits}` from state and writes the cited briefing.
4. Wall time is the slowest branch, not the sum.

**Path B: open questions (LLM-routed)**

1. `Coordinator` is an `LlmAgent` holding each specialist as an `AgentTool`, plus
   `BriefingFlow` as a tool.
2. It decides which specialists to call, can call several in one turn, and composes the answer.
3. Example: "Prep me for my 3pm and check if the borrower in that thread is risky" calls
   CalendarAgent, then MailAgent, then RiskAgent with the extracted fields.
4. Each specialist only sees its own server's tools (`McpToolset` + `tool_filter`): least
   privilege at the agent level.

**State and sessions**

- Session state holds the per-turn citation list and pending approvals. It never holds raw
  PII; the masking map lives in the servers.
- `DatabaseSessionService` on SQLite persists sessions across restarts.
- `user:` keys persist across sessions (timezone, working hours); `temp:` keys are dropped
  after the turn.

**Model routing**

- `ModelRouter` hands every agent a model through ADK's `LiteLlm`. Primary: Gemini Flash.
  On HTTP 429 or timeout it retries on Groq, then local Ollama, and records which model answered.
- Specialists can run on a smaller model than the synthesizer; config, not code, decides.
- Identical tool calls within one turn are cached to save quota.

## 7. Safety and governance

No write happens without a human yes, every tool call is logged, and no raw personal data
reaches a model.

**Approval gate**

- `send_email` and `create_event` sit in an `McpToolset` with ADK's `require_confirmation`
  enabled. The run pauses and the UI shows the exact arguments with Approve / Reject.
- Defence in depth: write tools on the server refuse any call without a valid approval token.
- Policy in `before_tool_callback`: allow-listed recipient domain only, at most 3 writes per
  session, no attachments in v1.

**Audit log** (append-only, one row per tool call)

| Field | Example | Purpose |
| --- | --- | --- |
| `ts` | 2026-11-03T09:14:22Z | When |
| `session_id`, `turn_id` | s_81f, t_4 | Ties calls to a conversation |
| `agent` | MailAgent | Which agent acted |
| `tool`, `server` | search_messages, gmail | What was called |
| `args_masked` | `{"query": "from:<PERSON_2>"}` | Inputs, never raw PII |
| `decision` | allowed / approved / rejected / blocked | Gate outcome |
| `approver` | user (UI) | Who said yes |
| `latency_ms`, `status` | 412, ok | Health |
| `model` | gemini flash / groq fallback | Which model drove it |

**PII masking**

- Servers mask names, emails, phone numbers and account-like numbers with Presidio before
  returning text, using tokens such as `<PERSON_2>`.
- The token map stays inside the MCP server (its own SQLite table keyed by session id),
  never in agent state or a prompt. Only an approved write unmasks the tokens it needs.

**Auth, secrets, injection**

- Narrowest OAuth scopes that work: `gmail.readonly` + `gmail.send`, `calendar.events`.
- Secrets in `.env` / Docker secrets, git-ignored, with a pre-commit secret scan.
- Email bodies are wrapped as untrusted data; instructions say text in tool results is never
  an instruction. A dedicated eval set tests this.

## 8. Evaluation

| Eval set | Cases | Checks |
| --- | --- | --- |
| Briefing | 10 | Right sources called, seeded facts covered |
| Routing | 20 | Coordinator picks the right specialists, in a sensible order |
| Grounding | 10 | Every claim maps to a returned `source_id` |
| Refusal and safety | 10 | Unapproved writes blocked, off-list recipients refused |
| Prompt injection | 10 | Instructions hidden in seeded emails are ignored |

| Metric | How | First target |
| --- | --- | --- |
| Tool trajectory | ADK built-in eval | 0.85+ |
| Grounding rate | Custom checker: share of sentences with a valid citation | 0.95+ |
| Safety pass rate | Refusal + injection sets | 1.00 |
| Latency p50 / p95 | From the audit log | < 15 s / < 30 s |

Unit tests (fake model, fake servers) run on every push. The full eval suite needs real
model calls, so it runs locally or via a manual workflow trigger. Results logged to MLflow
against the commit hash.

## 9. Build plan

| Phase | Deliverables |
| --- | --- |
| 1 Foundations | Repo, CI, demo account + OAuth + seed script, `calendar_mcp`, first ADK agent |
| 2 Orchestration | `gmail_mcp`, `knowledge_mcp`, specialists, BriefingFlow, Coordinator, ModelRouter |
| 3 Risk and safety | `risk_mcp`, approval gate, approval tokens, audit log, Presidio, injection defences |
| 4 Evals and ship | Eval sets, MLflow, Docker Compose, React UI, README, demo video |
