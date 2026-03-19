"""
main.py — PodQApath FastAPI backend (SCRUM-19)
Exposes mcp_bridge.py as a REST API for the React frontend.
Run: uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import json
import os
import re
import shutil
import tempfile
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

class RunTestsRequest(BaseModel):
    repo_path: str = ""
    repo_url: str = ""
    base_url: str = "http://localhost:3000"


# ---------------------------------------------------------------------------
# Playwright output parsers
# ---------------------------------------------------------------------------
def _parse_list_line(text: str) -> str | None:
    """Parse a test title from 'npx playwright test --list' output."""
    stripped = text.lstrip()
    if not stripped.startswith('['):
        return None
    parts = stripped.split(' › ')
    if len(parts) < 3:
        return None
    return ' › '.join(parts[2:]).strip()


def _parse_result_line(text: str) -> tuple[str | None, str | None, str | None]:
    """Parse status, title, duration from a playwright --reporter=list line."""
    stripped = text.lstrip()
    if stripped[:1] in ('✓', '·'):
        status = 'pass'
    elif stripped[:1] in ('✗', '×', '✘'):
        status = 'fail'
    else:
        return None, None, None
    rest = re.sub(r'^[✓·✗×✘]\s+\d+\s+', '', stripped)
    parts = rest.split(' › ')
    if len(parts) < 3:
        return None, None, None
    title_dur = ' › '.join(parts[2:])
    m = re.match(r'(.+?)\s+\(([\d.]+s)\)\s*$', title_dur)
    if m:
        return status, m.group(1).strip(), m.group(2)
    return status, title_dur.strip(), ''

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

@app.post("/api/run-tests")
async def run_tests(req: RunTestsRequest):
    async def _stream():
        work_dir = req.repo_path.strip()
        tmp_dir = None

        # Clone GitHub repo if a URL was provided instead of a local path
        if req.repo_url.strip() and not work_dir:
            tmp_dir = tempfile.mkdtemp()
            clone = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth=1", req.repo_url.strip(), tmp_dir,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await clone.communicate()
            if clone.returncode != 0:
                msg = stderr.decode("utf-8", errors="replace")[:300]
                yield f"data: {json.dumps({'type': 'error', 'message': f'git clone failed: {msg}'})}\n\n"
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return
            work_dir = tmp_dir

        if not work_dir:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Provide a repo path or GitHub URL.'})}\n\n"
            return
        if not Path(work_dir).exists():
            yield f"data: {json.dumps({'type': 'error', 'message': f'Path not found: {work_dir}'})}\n\n"
            return

        # Locate Playwright config — search root then up to 2 levels deep
        config_names = ["playwright.config.js", "playwright.config.ts", "playwright.config.mjs"]
        config_path: Path | None = None
        for p in [Path(work_dir)] + sorted(Path(work_dir).rglob("playwright.config.*"))[:20]:
            if p.is_file() and p.name in config_names:
                config_path = p
                break
            if p.is_dir():
                for name in config_names:
                    candidate = p / name
                    if candidate.exists():
                        config_path = candidate
                        break
            if config_path:
                break

        if not config_path:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No Playwright config found in repo.'})}\n\n"
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        config_cwd = str(config_path.parent)
        yield f"data: {json.dumps({'type': 'start', 'config': str(config_path.relative_to(work_dir))})}\n\n"

        env = {**os.environ, "PLAYWRIGHT_FORCE_TTY": "0", "CI": "1"}

        # Install dependencies if node_modules is missing (e.g. fresh clone)
        if not (Path(config_cwd) / "node_modules").exists():
            yield f"data: {json.dumps({'type': 'output', 'text': '📦 Installing dependencies…'})}\n\n"
            install_proc = await asyncio.create_subprocess_exec(
                "npm", "install", "--prefer-offline",
                cwd=config_cwd, env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            try:
                await asyncio.wait_for(install_proc.wait(), timeout=120)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'npm install timed out after 120s.'})}\n\n"
                if tmp_dir:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                return
            if install_proc.returncode != 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'npm install failed.'})}\n\n"
                if tmp_dir:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                return
            # Install Playwright browsers if needed
            browser_proc = await asyncio.create_subprocess_exec(
                str(Path(config_cwd) / "node_modules" / ".bin" / "playwright"),
                "install", "--with-deps",
                cwd=config_cwd, env=env,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await browser_proc.wait()

        if req.base_url.strip():
            env["BASE_URL"] = req.base_url.strip()

        # Always use the local playwright binary and explicit config to avoid version mismatches
        pw_bin = str(Path(config_cwd) / "node_modules" / ".bin" / "playwright")
        pw_config = str(config_path)

        # Phase 1 — discover tests so the frontend can show ⬜ pending states
        try:
            list_proc = await asyncio.create_subprocess_exec(
                pw_bin, "test", "--config", pw_config, "--list",
                cwd=config_cwd, env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            list_out, _ = await asyncio.wait_for(list_proc.communicate(), timeout=30)
            for raw in list_out.decode("utf-8", errors="replace").splitlines():
                title = _parse_list_line(raw)
                if title:
                    yield f"data: {json.dumps({'type': 'discovered', 'title': title})}\n\n"
        except (asyncio.TimeoutError, Exception):
            pass  # discovery failure is non-fatal; still run the tests

        # Phase 2 — run the suite and stream results
        proc = await asyncio.create_subprocess_exec(
            pw_bin, "test", "--config", pw_config, "--reporter=list",
            cwd=config_cwd, env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        summary_re = re.compile(r'(\d+)\s+passed(?:[^\d]+(\d+)\s+failed)?')
        passed = failed = 0

        async for raw_line in proc.stdout:
            text = raw_line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue
            status, title, duration = _parse_result_line(text)
            if status:
                if status == 'pass':
                    passed += 1
                else:
                    failed += 1
                yield f"data: {json.dumps({'type': 'result', 'title': title, 'status': status, 'duration': duration})}\n\n"
            else:
                sm = summary_re.search(text)
                if sm and 'passed' in text:
                    p = int(sm.group(1))
                    f_ = int(sm.group(2)) if sm.group(2) else 0
                    yield f"data: {json.dumps({'type': 'summary', 'passed': p, 'failed': f_})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'output', 'text': text})}\n\n"

        await proc.wait()
        yield f"data: {json.dumps({'type': 'done', 'exit_code': proc.returncode, 'passed': passed, 'failed': failed})}\n\n"

        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve built React frontend in production
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
