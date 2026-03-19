# PodQApath

**An Agentic Release Auditor for Pod-Based QA Teams.**

PodQApath is a React dashboard backed by a FastAPI server that connects Jira and GitHub through the **Model Context Protocol (MCP)**, scores ticket risk in real time, surfaces PR diffs for any linked pull request, and gives your team an AI-powered QA analyst (QA-7) to drive release readiness decisions.

---

## Demo

> Drag the demo video into a GitHub Issue to get a CDN link, then embed it here.

---

## Key Features

| Feature | What it does |
|---|---|
| **Release-Aware Risk Scoring** | Every ticket is scored 0–100 and bands into 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low. Dominant signal: release proximity — ≤2 days +70, ≤7 days +35, ≤14 days +20, ≤21 days +5 |
| **Smart Filters** | Sidebar lets you filter by Tags, Statuses, and Sprint before fetching — preventing massive ticket loads from hitting the API |
| **PR Diff Viewer** | Click any ticket to pull its linked GitHub PR: title, status, author, files changed, additions/deletions, and raw diff |
| **QA-7 AI Analyst** | Claude-powered chatbot with two modes: **Technical** (full QA lead analysis) and **Manager** (plain-language summaries). Automatically receives full context of loaded tickets, selected ticket, and PR diff |
| **Live Jira + GitHub** | Pulls real Jira tickets and GitHub PR diffs via REST API and MCP — no local CSV needed |
| **Demo Mode** | One-click offline mode with realistic sample data — all four risk bands, a PR collision scenario, and a not-yet-deployed scenario. No credentials required |
| **Playwright E2E Tests** | Full end-to-end test suite covering all core user flows, running entirely against the demo data layer |
| **Repo Test Runner** | Run any external repo's Playwright suite from inside PodQApath — test names stream in real time (⬜ → ✅/❌), failed tests show error output inline, and results feed directly into QA-7 context |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5 |
| Backend | FastAPI (Python 3.11+) |
| AI | Anthropic SDK — claude-sonnet-4-6 |
| Protocol | Model Context Protocol (MCP) via `mcp-atlassian` |
| Integrations | Jira Software, GitHub |
| Data Bridge | `mcp_bridge.py` — all data fetching and risk scoring logic |

---

## Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/teddyski/podqapath.git
cd podqapath
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Your Anthropic API key (for QA-7 chatbot) |
| `JIRA_BASE_URL` | ✅ | Your Jira instance URL, e.g. `https://your-org.atlassian.net` |
| `JIRA_EMAIL` | ✅ | Your Jira account email |
| `JIRA_API_TOKEN` | ✅ | Jira API token — generate at [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `GITHUB_TOKEN` | ✅ | GitHub personal access token with `repo` (read) scope |
| `GITHUB_REPO` | Optional | Target repo in `org/repo-name` format |
| `ANTHROPIC_MODEL` | Optional | Override model (default: `claude-sonnet-4-6`) |
| `VITE_PROJECT_KEY` | Optional | Default Jira project key pre-filled in the UI |
| `DEMO_MODE` | Optional | Set to `true` to force all endpoints to return sample data — useful for CI or demos without live credentials |

### 6. Start the Backend

```bash
uvicorn main:app --reload --port 8000
```

### 7. Start the Frontend

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Using the Dashboard

### Demo Mode (no credentials needed)

Click **🧪 Load Demo Data** in the sidebar to instantly populate the dashboard with realistic sample tickets — no Jira or GitHub credentials required. The demo includes:

- All four risk bands (🔴🟠🟡🟢)
- A PR collision scenario — two tickets touching the same auth file
- A not-yet-deployed scenario — ticket marked "Ready for QA" with an open PR
- Full fake PR diffs for most tickets

### Connect & Load Filters (live mode)
1. Enter your Jira **Project Key** in the sidebar (e.g. `SCRUM`)
2. Click **Connect & Load Filters** to populate Tags, Statuses, and Sprint dropdowns from your live Jira project
3. Apply any filters you want, then click **☁️ Fetch Live Data**

### View Ticket Risk
- Each ticket shows its **Risk Band** (🔴🟠🟡🟢), score, and risk reasons
- Click any ticket to load its linked PR diff in the center column

### QA-7 Chatbot
- Ask anything about your release: risk summaries, what changed in a PR, whether a ticket is ready to ship
- Toggle **Manager mode** for plain-language output suited for non-technical stakeholders — switching modes clears chat history
- QA-7 automatically receives full context: all loaded tickets, the selected ticket's details, and the PR diff

---

## Risk Scoring

Scores are 0–100 and clipped. Dominant factor is release proximity:

| Signal | Points |
|---|---|
| Release ≤ 2 days | +70 |
| Release ≤ 7 days | +35 |
| Release ≤ 14 days | +20 |
| Release ≤ 21 days | +5 |
| Critical priority | +30 |
| High priority | +20 |
| Medium priority | +10 |
| Open > 14 days | +10 |
| No linked PR | +10 |
| Bug / Incident type | +5 |

| Band | Score |
|---|---|
| 🔴 Critical | ≥ 75 |
| 🟠 High | ≥ 50 |
| 🟡 Medium | ≥ 25 |
| 🟢 Low | < 25 |

---

## Repo Test Runner

The **🧪 Repo Test Runner** panel in the sidebar lets you run any project's Playwright test suite without leaving PodQApath.

1. Click **🧪 Repo Test Runner** in the sidebar to expand the panel
2. Enter either an **absolute local path** to the repo or a **GitHub URL** (it will be cloned automatically)
3. Set the **Base URL** of the QA environment you want to test against (passed as `BASE_URL` env var)
4. Click **▶ Run Tests**

PodQApath will:
- Discover all tests upfront and display them as ⬜ pending
- Stream results in real time — each test updates to ✅ or ❌ as it completes
- Show error output inline below the test list for any failures
- Feed the full results into QA-7 so you can ask questions like *"which tests failed and why?"*

> Works with any repo that has a standard `playwright.config.js` / `.ts` / `.mjs` in its root.

---

## Running E2E Tests

The Playwright test suite runs entirely against the demo data layer — no live credentials needed.

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

The config (`playwright.config.js`) automatically starts both the FastAPI backend (with `DEMO_MODE=true`) and the Vite dev server before running tests. Tests cover:

- Loading demo data and populating the ticket list
- Filter enable state after demo load
- Ticket selection and PR diff view
- No-PR state handling
- Raw diff expand/collapse
- Chat input (button, Enter, Shift+Enter)
- Manager mode toggle

To run with the interactive Playwright UI:

```bash
npm run test:e2e:ui
```

---

## Business Value

PodQApath centralizes deployment data, ticket status, and PR risk into a single command center — reducing triage time and eliminating the collision risk common in shared QA environments where multiple pods touch the same codebase simultaneously.

QA-7's Manager mode bridges the gap between non-technical stakeholders and complex engineering work. QA-1 engineers can ask plain-English questions about complex tickets and epics — getting clear explanations of what changed, why it matters, and what to focus on when testing, without needing to read code or parse technical jargon.

---

## License

MIT License — free for personal and commercial use. See [LICENSE](LICENSE) for details.
