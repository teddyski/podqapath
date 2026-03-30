# PodQApath — Claude Code Project Instructions

## Project Overview
PodQApath is an agentic QA release auditing dashboard built with Streamlit and Python.
It connects Jira and GitHub data, scores ticket risk, detects PR collisions, and provides
an AI-powered QA analyst chatbot (QA-7) for release readiness assessment.

## Stack
- UI: Streamlit
- AI: Anthropic SDK (Claude)
- Protocol: MCP (Model Context Protocol)
- Integrations: Jira Software, GitHub
- Language: Python 3.11+

---

## Session Logging (ai_log.txt)

At the start of every session, append a new session block to `ai_log.txt`.
At the end of every session, append a summary of what was done.

Use this format:
```
=======================================================
SESSION: [YYYY-MM-DD] [HH:MM]
=======================================================
Model        : claude-sonnet-4-6
Working Dir  : [current directory]

-------------------------------------------------------
ACTIONS PERFORMED
-------------------------------------------------------
[timestamp] [action title]
  - [what was done]
  - [files created or modified]

-------------------------------------------------------
NOTES
-------------------------------------------------------
- [anything relevant for next session]

=======================================================
END OF SESSION
=======================================================
```

Rules:
- Always append, never overwrite
- Log every file created or modified
- Log any errors encountered and how they were resolved
- Note anything the next session should be aware of

---

## Decision Logging (DECISIONS.md)

Whenever you make a significant architectural or technical decision, append it to `DECISIONS.md`.

Use this format:
```
[YYYY-MM-DD] Decision: [short title]
Context: [what problem were we solving]
Options Considered: [what alternatives existed]
Chosen: [what was picked]
Reason: [why this over the alternatives]
Tradeoffs: [what we gave up]
---
```

Significant decisions include:
- Language or framework choices
- Library selections
- Data model design
- API design choices
- Infrastructure decisions
- Major refactors

Do not log minor decisions like variable names or small styling choices.
Always append, never overwrite existing entries.

---

## Code Style
### Elixir/Phoenix Backend
- Follow Elixir naming conventions (snake_case, descriptive module names)
- Keep JiraClient and GitClient as separate modules — do not merge into controllers
- Controllers handle HTTP concerns only, clients handle external API calls
- Use Port.open for any streaming/SSE endpoints, not System.cmd
- Pattern match on error tuples {:ok, result} / {:error, reason}

### Frontend (if applicable)
- [whatever your React/Vite conventions are]

### General
- Prefer explicit over clever
- Keep modules small and single-purpose

## End of Session

When the user says "log session" or "wrap up", append the completed session
block to `ai_log.txt` and notify the user it's ready to compress with `/compact`.

---

## QA-7 Persona
The AI chatbot persona is defined in QA_AGENT.md. Do not modify the tone or
scoring logic without noting it as a decision in DECISIONS.md.

---

## Karen Scenarios (Nurse System)

Gherkin scenarios for the Karen / Nurse System philosophy live in `scenarios/`.

| File | Purpose |
|------|---------|
| `scenarios/karen.feature` | Tier 2 acceptance criteria — front door access under realistic conditions |
| `scenarios/karen_edge_cases.feature` | Full command chain failure modes (broker, controller, job queue) |

**Rules:**
- When adding scenarios, think: "what does Karen actually experience?" not "what does the API return?"
- New Tier 2 behaviors must have a corresponding scenario before they can be released.
- Scenario files are read by QA-7 to understand coverage — treat them as living documentation, not one-offs.
- Do not add cosmetic or Tier 0 scenarios to these files. They belong in a separate feature file.
