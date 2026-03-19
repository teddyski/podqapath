# PodQApath

**An Agentic Release Auditor for Pod-Based QA Teams.**

PodQApath is a Streamlit command center that connects Jira and GitHub through the **Model Context Protocol (MCP)**, scores ticket risk in real time, detects PR collisions across pods, and gives your team an AI-powered QA analyst (QA-7) to drive release readiness decisions.

---

## Demo

<video src="https://raw.githubusercontent.com/teddyski/podqapath/main/assets/demo.mp4" controls width="100%"></video>

---

## Key Features

| Feature | What it does |
|---|---|
| **Risk Scoring** | Every ticket gets a scored risk band — 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low — based on priority, days open, PR linkage, and issue type |
| **QA Payload Audit** | Scans merged PRs from the last N hours and maps them to Jira tickets to show exactly what's deployed in your QA environment |
| **Collision Detection** | Flags file-level and module-level conflicts across PRs so you know where to focus regression testing |
| **Not-Yet-Deployed Tracker** | Identifies tickets marked *Ready for QA* whose PRs haven't merged yet — so you don't test code that isn't there |
| **PR Traceability** | One-click check to verify whether a Jira ticket has a linked pull request |
| **PR Diff Viewer** | Pulls the full GitHub diff (files changed, additions, deletions) for any selected ticket's PR |
| **Pod-Aware Filters** | Sidebar filters by pod, status, sprint, and label — with assigned QA member displayed per pod |
| **QA-7 AI Analyst** | Claude-powered chatbot with two modes: **Technical** (full QA lead analysis) and **Manager** (plain-language summaries). Upgrades to agentic tool-use when MCP is active |
| **Dual Data Modes** | Switch between **Live MCP/API** (real Jira + GitHub) and **Local CSV Audit** (offline / restricted environments) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (Python 3.11+) |
| AI | Anthropic SDK — Claude claude-sonnet-4-6 |
| Protocol | Model Context Protocol (MCP) via `mcp-atlassian` |
| Integrations | Jira Software, GitHub |
| Bridge | `mcp_bridge.py` — all data fetching logic |

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

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
| `JIRA_PROJECT_KEY` | ✅ | Your Jira project key, e.g. `PROJ` |
| `GITHUB_TOKEN` | ✅ | GitHub personal access token with `repo` (read) scope |
| `GITHUB_REPO` | ✅ | Target repo in `org/repo-name` format |
| `POD_FIELD_ID` | Optional | Jira custom field ID for pod mapping (default: `customfield_10020`) |
| `POD_QA_MAP` | Optional | JSON map of pod names to QA owners (see `.env.example`) |
| `JIRA_MAX_RESULTS` | Optional | Max tickets to fetch per query (default: `100`) |
| `GIT_REPO_PATH` | Optional | Local path to your git repo (enables Git MCP server) |

### 5. Launch the App

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Using the Dashboard

### Local CSV Mode (no credentials needed)
1. Select **📂 Local CSV Audit** in the sidebar
2. Upload a Jira export CSV and optionally a Git branch CSV — or click **Load Sample Data** to explore with demo data

### Live Mode (Jira + GitHub)
1. Select **☁️ Live MCP / Cloud API** in the sidebar
2. Click **Connect & Load Filters** to populate the sprint, tag, and status dropdowns
3. Apply filters and click **Fetch Live Data**
4. Click **🚀 Load QA Payload** to scan recent merged PRs

### QA-7 Chatbot
- Ask anything about your release: risk summaries, collision explanations, deployment status
- Toggle **Manager mode** for plain-language output suited for non-technical stakeholders
- When MCP is active, QA-7 can call Jira and GitHub tools directly (agentic mode)

---

## Business Value

PodQApath centralizes deployment data, ticket status, and PR risk into a single command center — reducing triage time and eliminating the "collision risk" common in shared QA environments where multiple pods touch the same codebase simultaneously.

---

## License

MIT License — free for personal and commercial use. See [LICENSE](LICENSE) for details.
