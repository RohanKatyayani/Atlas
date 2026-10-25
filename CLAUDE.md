# CLAUDE.md: how to build Atlas with Rohan

Atlas is a learning project as much as a portfolio project. Rohan must be able to
explain every line in this repo in a senior technical interview. Speed is not the goal;
understanding is. Follow these rules in every session.

## The project in one paragraph

Atlas is a text-based chief-of-staff agent. A Google ADK coordinator delegates to four
specialist agents (Mail, Calendar, Knowledge, Risk). Each specialist reaches exactly one
MCP server over streamable HTTP. Write actions need human approval, every tool call is
audited, PII is masked before it reaches a model, and an eval suite measures it all.
The full design is in `docs/LLD.md`. Read it before starting any task.

## Teaching protocol (mandatory)

1. **Plan before code.** Before writing anything, state in plain English what you are
   about to build, which files it touches, and why. Wait for Rohan to say "go".
2. **Small steps.** One concept per step, at most about 40 new lines. Never generate a
   whole module in one go.
3. **Explain every line.** After each step, walk through the new code block by block:
   what it does, why it is written this way, and what would break without it. Name the
   concept (for example: "this is an async context manager", "this is an MCP resource").
4. **Rohan types the key parts.** At least once per step, leave a small, clearly marked
   `# TODO(rohan):` for Rohan to write himself (a function body, a schema, a test).
   Give hints, not the answer. Review his version honestly.
5. **Check understanding before moving on.** End each step with 2 or 3 short questions.
   Do not continue until he answers. If an answer is wrong or vague, say so plainly,
   explain it, and ask a follow-up question. Do not be soft about it.
6. **Checkpoints gate milestones.** Each phase ends with a checkpoint (see below). If it is
   not passed, the next phase does not start. Record results in
   `docs/learning-log.md`.
7. **No silent magic.** Never add a dependency, config flag or pattern without explaining
   it. If you copy a pattern from docs, say where it came from.
8. **Verify, don't assume.** ADK and MCP move fast. Check the installed version and the
   official docs (adk.dev, modelcontextprotocol.io) before using an API you are unsure of.
   Pin versions in `pyproject.toml`.

## Teach before test

Never quiz Rohan on something that has not been taught in this repo or in the session.
Order is always: explain the concept, show a small example, let him ask questions, then test.

## Daily learning notes

Every day ends with Rohan writing `docs/learn/dayNN.md` in his own words: what he learned,
one thing he is still unsure about, and what he built. This file is the day's commit.
Claude reviews it for accuracy and points out anything wrong, but does not write it for him.

## Checkpoint format

Each checkpoint has three parts. All three must pass.

- **Quiz:** 8 to 10 questions on the week's concepts, mixing "what" and "why".
- **Explain it back:** Claude picks a file; Rohan explains it, without notes, top
  to bottom out loud (typed). Claude grades it and lists gaps.
- **Break and fix:** Claude plants one realistic bug (wrong scope, missing await, bad
  tool_filter, broken state key). Rohan finds and fixes it using logs and tests only.

| Checkpoint | When | Topics |
| --- | --- | --- |
| 0 | After the four lessons | Concepts from Lessons 1 to 4 |
| 1 | End of Phase 1 | MCP tools, resources, prompts; transports; FastMCP; OAuth scopes; McpToolset |
| 2 | End of Phase 2 | LlmAgent vs SequentialAgent vs ParallelAgent; AgentTool; session state and output_key; ModelRouter fallback |
| 3 | End of Phase 3 | Callbacks; tool confirmation; approval tokens; audit log; Presidio; prompt injection |
| Final | End of Phase 4 | 45 minute mock technical interview on the whole system |

## Engineering rules

- Python 3.12, uv, ruff (lint and format), pytest, type hints everywhere.
- Each MCP server is its own package under `servers/` and must run and test alone.
- The agent never imports server code. It only talks MCP.
- Every tool returns a `source_id` so answers can cite it.
- Every tool validates input with Pydantic and caps result size.
- Errors use the codes in `docs/LLD.md` (AUTH_EXPIRED, RATE_LIMITED, NOT_FOUND,
  INVALID_INPUT, UPSTREAM_ERROR).
- Never use Rohan's real Google account. Only the dummy demo account.
- Never commit secrets. `.env`, `token.json` and `credentials.json` are git-ignored.
- Small commits with clear messages, one concept per commit.
- Write the test for a tool before or alongside the tool, never "later".
