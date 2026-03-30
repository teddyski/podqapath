# PodQApath

**An Agentic Release Auditor for QA Teams Who Know What Actually Breaks.**

PodQApath started as a proof of concept — a fast, AI-assisted prototype built to demonstrate a simple idea: QA tooling should be connected to what the system *actually does*, not just what the ticket says it does.

It is not production-ready. It is the skeleton of something I intend to build properly.

---

## The Nurse System

This project is built on a QA philosophy I call **the Nurse System**, developed over six years of QA engineering in IoT property automation — the kind of systems that control whether someone can get through their front door.

The core idea:

> Meet Karen. She's an ICU nurse. She just worked a 13-hour shift. Her phone is at 13%. She's standing at her front door. She doesn't care what changed in your sprint. She cares that her door opens.

In IoT, a failed test isn't a red badge on a dashboard. It's a person standing outside their apartment at 8:30am with nothing left. Traditional QA tooling validates the API response. Karen lives at the device layer — the last step in a chain that can fail silently at every point between.

The Nurse System uses a three-tier risk model:

| Tier | Domain | Example |
|------|--------|---------|
| Tier 0 | UI / cosmetic | A label displays incorrectly |
| Tier 1 | Non-safety device behavior | Lights don't respond, parking sensor glitch |
| Tier 2 | Resident safety systems | **Door locks. HVAC. Access control.** |

Tier 2 requires human sign-off before release. Always.

**Why HVAC is Tier 2 — not Tier 1:**

During the Moscow heatwave of 2010, an estimated 11,000 people died in the city in a single month — many of them elderly residents in apartments without functioning cooling. The same risk exists in reverse: heating failure in winter is a hypothermia event for vulnerable residents. An IoT thermostat is not a convenience feature. It is a life-safety system with a quiet failure mode. When a software change touches temperature control, the question is not "did the API return 200?" — it is "will Karen's apartment stay habitable?" Those are not the same question, and only one of them matters.

**The Nurse System says:** the job of QA is not to generate test cases faster. The job is to know Karen well enough that when something changes in her world, you catch it before she gets home.

---

## What PodQApath Does Today

This is a **proof of concept** built with Python, Streamlit, and the Anthropic API. In its current state it demonstrates:

- **Pod-Aware Traceability** — Maps Jira custom fields to QA pods for 1:1 requirement-to-environment tracing.
- **Environment Auditing** — Correlates merged PRs with Jira tickets to surface what's actually deployed vs. what the ticket claims.
- **QA-7 Analyst Agent** — An AI persona (powered by Claude) that analyzes code churn, flags risk based on release proximity, and detects PR collisions.
- **Hybrid Data Sourcing** — Live API mode or local CSV audit mode for restricted corporate environments.

It works. Barely. It was built fast and AI-assisted to prove the concept, not to ship. Think of it as the napkin sketch before the architecture.

---

## Where It's Going

PodQApath is evolving toward the Nurse System vision:

- **Karen scenarios in Gherkin** — Structured, human-first test scenarios stored in version-controlled markdown. The AI reads these to understand *who* it's protecting, not just *what* to test.
- **Risk tiering** — Tier 0 (UI), Tier 1 (non-safety device behavior), Tier 2 (locks, access control, HVAC, resident safety). Karen gets loud at Tier 2. Human sign-off required.
- **System-connected intelligence** — Moving beyond ticket-derived test generation toward AI that understands service ownership, job queues, device telemetry, and the full command chain from tap to deadbolt.
- **Elixir/Phoenix backend** — A migration is in progress on a feature branch. The Python/Streamlit prototype will remain as the reference implementation.
- **Localization** — Japanese language support is in progress (`QA_AGENT.ja.md`), because this work doesn't stop at one company or one country.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit (Python) |
| AI | Anthropic SDK (Claude) |
| Protocol | Model Context Protocol (MCP) |
| Logic | Python 3.11+ |
| Integrations | Jira Software, GitHub |
| Future Backend | Elixir / Phoenix (in progress) |

---

## Setup

```bash
git clone https://github.com/teddyski/podqapath.git
cd podqapath
cp .env.example .env
pip install -r requirements.txt
streamlit run app.py
```

Required environment variables in `.env`:

- `ANTHROPIC_API_KEY`
- `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- `GITHUB_TOKEN`

---

## Why This Exists

I spent six years in QA at an IoT company that puts smart locks on apartment doors. I sat in on support calls with elderly residents who couldn't get into their homes. I watched the system grow from a simple control platform into a distributed architecture spanning multiple applications, message brokers, job systems, and device layers — while the QA tooling stayed pointed at the API surface.

The industry is adopting AI fast. Most of it is shallow: test cases generated from ticket descriptions, documentation assistants, workflow automation. That's fine for a lot of software. It is not fine when your system controls whether someone can get through their front door.

PodQApath is my attempt to build the thing that should exist: QA tooling that knows who Karen is, knows when her world was touched, and says something about it before she gets home.

---

## License

MIT — free for personal and commercial use. See [LICENSE](LICENSE).

---

*Built by [Thaddeus Skorzewski](https://github.com/teddyski) — QA engineer, flow artist, and someone who still thinks about the person on the other side of the door.*
