"""
main.py — PodQApath FastAPI backend (SCRUM-19)
Exposes mcp_bridge.py as a REST API for the React frontend.
Run: uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
import os
import mcp_bridge as bridge

load_dotenv()

app = FastAPI(title="PodQApath API")

DEMO_MODE = os.getenv("DEMO_MODE", "").lower() == "true"

def _is_demo(req_demo_mode: bool) -> bool:
    return DEMO_MODE or req_demo_mode

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Credentials from .env
# ---------------------------------------------------------------------------
JIRA_URL     = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL   = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN   = os.getenv("JIRA_API_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

def _require_jira():
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_TOKEN]):
        raise HTTPException(status_code=503, detail="Jira credentials not configured in .env")

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class FiltersRequest(BaseModel):
    project_key: str
    demo_mode: bool = False

class TicketsRequest(BaseModel):
    project_key: str
    tags: list[str] = []
    statuses: list[str] = []
    sprint_ids: list[int] = []
    demo_mode: bool = False

class PRDiffRequest(BaseModel):
    ticket_key: str
    demo_mode: bool = False

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    manager_mode: bool = False
    context: str = ""

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "jira_configured": bool(JIRA_URL and JIRA_TOKEN)}

@app.post("/api/filters")
def load_filters(req: FiltersRequest):
    if _is_demo(req.demo_mode):
        return bridge.generate_sample_filters()
    _require_jira()
    if not req.project_key.strip():
        raise HTTPException(status_code=400, detail="project_key is required")
    try:
        labels   = bridge.fetch_jira_labels(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, req.project_key)
        statuses = bridge.fetch_jira_statuses(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, req.project_key)
        sprints  = bridge.fetch_jira_sprints(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, req.project_key)
        return {"labels": labels, "statuses": statuses, "sprints": sprints}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tickets")
def fetch_tickets(req: TicketsRequest):
    if _is_demo(req.demo_mode):
        df = bridge.generate_sample_jira_df()
        df_scored = bridge.compute_risk_scores(df)
        df_scored = df_scored.fillna("")
        return df_scored.to_dict(orient="records")
    _require_jira()
    try:
        project_key = req.project_key
        jql_parts = [f"project = {project_key}"]
        if req.tags:
            tags_jql = ", ".join(f'"{t}"' for t in req.tags)
            jql_parts.append(f"labels in ({tags_jql})")
        if req.statuses:
            statuses_jql = ", ".join(f'"{s}"' for s in req.statuses)
            jql_parts.append(f"status in ({statuses_jql})")
        if req.sprint_ids:
            sprint_jql = ", ".join(str(s) for s in req.sprint_ids)
            jql_parts.append(f"sprint in ({sprint_jql})")
        jql_parts.append("ORDER BY created DESC")
        jql = " AND ".join(jql_parts[:-1]) + " " + jql_parts[-1]

        df = bridge.fetch_live_jira(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, project_key, jql_override=jql)
        df_scored = bridge.compute_risk_scores(df)
        df_scored = df_scored.fillna("")
        return df_scored.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pr-diff")
def fetch_pr_diff(req: PRDiffRequest):
    if _is_demo(req.demo_mode):
        return bridge.generate_sample_pr_data(req.ticket_key)
    _require_jira()
    try:
        dev = bridge.fetch_dev_status(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, req.ticket_key)
        if not dev.get("prs"):
            return {"prs": [], "diff": None, "description": dev.get("description", "")}
        pr = dev["prs"][0]
        diff = None
        if "github.com" in pr.get("url", "") and GITHUB_TOKEN:
            diff = bridge.fetch_github_pr_diff(pr["url"], GITHUB_TOKEN)
        return {"prs": dev["prs"], "diff": diff, "description": dev.get("description", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def chat(req: ChatRequest):
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set in .env")
    try:
        import anthropic as sdk
        persona_file = "QA_MANAGER.md" if req.manager_mode else "QA_AGENT.md"
        persona_path = Path(persona_file)
        system = persona_path.read_text() if persona_path.exists() else "You are a QA assistant."
        if req.context:
            system += f"\n\n---\n\n# LIVE DASHBOARD DATA\n\n{req.context}"

        messages = list(req.history) + [{"role": "user", "content": req.message}]
        client = sdk.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return {"reply": response.content[0].text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve built React frontend in production
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
