# PodQApath

**An Agentic Release Auditor for Pod-Based QA Teams.**

PodQApath uses the **Model Context Protocol (MCP)** to map Jira custom fields to specific QA pods, providing 1:1 traceability between requirements and auto-deployed environments.

---

## Key Features

- **Pod-Aware Traceability** — Automatically maps Jira custom fields to specific Pods and assigned QA members.
- **Environment Auditing** — Correlates merged Pull Requests with Jira tickets to verify what is actually deployed in the QA environment.
- **Agentic Analytics** — An integrated AI Assistant (powered by Claude 3.5) that analyzes code churn and requirement gaps in real-time.
- **Hybrid Data Sourcing** — Switch between Live API mode and Local CSV Audit mode for restricted corporate environments.

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (Python) |
| AI Protocol | Model Context Protocol (MCP) |
| Logic | Python 3.11+ |
| AI SDK | Anthropic SDK |
| Integrations | Jira Software, GitHub (via MCP) |

---

## Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/teddyski/podqapath.git
cd podqapath
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required keys:
- `ANTHROPIC_API_KEY` — Your Anthropic API key
- `JIRA_BASE_URL` — Your Jira instance URL
- `JIRA_EMAIL` — Your Jira account email
- `JIRA_API_TOKEN` — Your Jira API token
- `GITHUB_TOKEN` — Your GitHub personal access token

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Launch the HUD

```bash
streamlit run app.py
```

---

## Business Value

By centralizing deployment data and ticket status into a single command center, PodQApath reduces triage time by up to 40% and eliminates the "Collision Risk" common in shared QA environments.

---

## License

MIT License — free for personal and commercial use. See [LICENSE](LICENSE) for details.
