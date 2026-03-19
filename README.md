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

### Connect & Load Filters
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

## Business Value

PodQApath centralizes deployment data, ticket status, and PR risk into a single command center — reducing triage time and eliminating the collision risk common in shared QA environments where multiple pods touch the same codebase simultaneously.

QA-7's Manager mode bridges the gap between non-technical stakeholders and complex engineering work. QA-1 engineers can ask plain-English questions about complex tickets and epics — getting clear explanations of what changed, why it matters, and what to focus on when testing, without needing to read code or parse technical jargon.

---

## License

MIT License — free for personal and commercial use. See [LICENSE](LICENSE) for details.
