"""
mcp_bridge.py — Data layer: Local CSV, REST API, and MCP client.
"""

import asyncio
import concurrent.futures
import json
import os
import re
from io import StringIO
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Path to the mcp-atlassian binary installed in the project venv
_VENV_BIN = Path(__file__).parent / ".venv" / "bin"
MCP_ATLASSIAN_BIN = str(_VENV_BIN / "mcp-atlassian")


# ---------------------------------------------------------------------------
# Async / event-loop helpers
# ---------------------------------------------------------------------------

def _run_async(coro):
    """
    Run an async coroutine safely from Streamlit's sync context.
    Uses a dedicated thread to avoid conflicts with any existing event loop.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result(timeout=60)


# ---------------------------------------------------------------------------
# MCP Server Parameter Factories
# ---------------------------------------------------------------------------

def atlassian_server_params(jira_url: str, email: str, token: str):
    from mcp import StdioServerParameters
    env = {
        **os.environ,
        "JIRA_URL": jira_url,
        "JIRA_USERNAME": email,
        "JIRA_API_TOKEN": token,
    }
    return StdioServerParameters(command=MCP_ATLASSIAN_BIN, args=[], env=env)


def git_server_params(repo_path: str):
    from mcp import StdioServerParameters
    return StdioServerParameters(
        command=str(_VENV_BIN / "mcp-server-git"),
        args=["--repository", repo_path],
        env=dict(os.environ),
    )


# ---------------------------------------------------------------------------
# MCP: List Tools
# ---------------------------------------------------------------------------

async def _async_list_tools(server_params) -> list:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


def list_mcp_tools(server_params) -> list:
    """Return list of MCP Tool objects from a server."""
    return _run_async(_async_list_tools(server_params))


def mcp_tools_to_anthropic(tools: list) -> list[dict]:
    """Convert MCP Tool objects to Anthropic tool_use format."""
    out = []
    for t in tools:
        schema = t.inputSchema if hasattr(t, "inputSchema") else {}
        if hasattr(schema, "model_dump"):
            schema = schema.model_dump()
        out.append({
            "name": t.name,
            "description": t.description or "",
            "input_schema": schema or {"type": "object", "properties": {}},
        })
    return out


# ---------------------------------------------------------------------------
# MCP: Single Tool Call
# ---------------------------------------------------------------------------

async def _async_call_tool(server_params, tool_name: str, tool_args: dict):
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, tool_args)


def call_mcp_tool(server_params, tool_name: str, tool_args: dict):
    """Call a single MCP tool and return the raw result."""
    return _run_async(_async_call_tool(server_params, tool_name, tool_args))


def _extract_text(result) -> str:
    """Pull text from MCP tool result content blocks."""
    parts = []
    for item in result.content:
        if hasattr(item, "text"):
            parts.append(item.text)
        else:
            parts.append(str(item))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# MCP: Fetch Jira Issues
# ---------------------------------------------------------------------------

def fetch_jira_via_mcp(jira_url: str, email: str, token: str,
                        project_key: str, max_results: int = 50,
                        jql_override: str | None = None) -> pd.DataFrame:
    """
    Fetch Jira issues via the mcp-atlassian MCP server.
    Pass jql_override to use a custom JQL string (e.g. pod-filtered queries).
    """
    params = atlassian_server_params(jira_url, email, token)

    # Discover available tools
    tools = list_mcp_tools(params)
    tool_names = {t.name for t in tools}

    # Find the search tool (mcp-atlassian uses 'jira_search' or 'jira_search_issues')
    search_tool = next(
        (n for n in ["jira_search", "jira_search_issues", "search_issues"] if n in tool_names),
        None,
    )
    if search_tool is None:
        raise RuntimeError(
            f"No Jira search tool found. Available tools: {sorted(tool_names)}"
        )

    jql = jql_override if jql_override else f"project = {project_key} ORDER BY created DESC"
    result = call_mcp_tool(params, search_tool, {"jql": jql})
    raw = _extract_text(result)

    # mcp-atlassian returns markdown or JSON — try JSON first
    import logging
    rows = []
    try:
        data = json.loads(raw)
        issues = data if isinstance(data, list) else data.get("issues", [])
        for issue in issues:
            key = issue.get("key", "")
            if not key:
                logging.warning("fetch_jira_via_mcp: skipping issue with missing key: %s", issue)
                continue
            f = issue.get("fields", issue)
            rows.append({
                "Issue Key": key,
                "Summary": f.get("summary", ""),
                "Priority": (f.get("priority") or {}).get("name", "Unknown"),
                "Status": (f.get("status") or {}).get("name", "Unknown"),
                "Assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                "Issue Type": (f.get("issuetype") or {}).get("name", "Unknown"),
                "Component": ", ".join(c["name"] for c in (f.get("components") or [])) or "None",
                "Days Open": _days_since(f.get("created", "")),
                "FixVersionDate": _nearest_fix_version_date(f.get("fixVersions", [])),
                "SprintEndDate":  _parse_sprint_end_date(f.get("customfield_10020")),
            })
    except (json.JSONDecodeError, KeyError) as e:
        logging.warning("fetch_jira_via_mcp: could not parse MCP response as JSON (%s). Raw: %s", e, raw[:200])

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return _normalize_jira_df(df)


# ---------------------------------------------------------------------------
# MCP: Fetch Git Status
# ---------------------------------------------------------------------------

def fetch_git_status_via_mcp(repo_path: str) -> pd.DataFrame:
    """
    Fetch current branch info from a local Git repo via the MCP git server.
    Returns a DataFrame of recent commits / branch status.
    """
    params = git_server_params(repo_path)

    tools = list_mcp_tools(params)
    tool_names = {t.name for t in tools}

    rows = []

    # git_log for recent commits
    if "git_log" in tool_names:
        result = call_mcp_tool(params, "git_log", {"repo_path": repo_path, "max_count": 20})
        raw = _extract_text(result)
        # Parse "hash | author | date | message" style log lines
        for line in raw.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                rows.append({
                    "Branch": parts[0][:10],
                    "Author": parts[1],
                    "Last Commit": parts[2],
                    "Merged": False,
                    "Files Changed": "",
                })

    # git_status for current state
    status_text = ""
    if "git_status" in tool_names:
        result = call_mcp_tool(params, "git_status", {"repo_path": repo_path})
        status_text = _extract_text(result)

    if not rows:
        rows = [{"Branch": "status", "Author": "—", "Last Commit": "—",
                 "Merged": False, "Files Changed": status_text[:200]}]

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Agentic Tool-Call Loop
# ---------------------------------------------------------------------------

async def _async_agentic_loop(
    messages: list,
    system: str,
    anthropic_key: str,
    model: str,
    server_params_list: list,
    status_callback=None,
) -> tuple[str, list]:
    """
    Full agentic loop:
      1. Collect tools from all MCP servers
      2. Send to Claude with tool definitions
      3. On tool_use: call the MCP tool, return result
      4. Repeat until end_turn
    """
    import anthropic as anthropic_sdk
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    client = anthropic_sdk.Anthropic(api_key=anthropic_key)

    # Collect tools from all servers
    all_tools_raw = []
    tool_server_map: dict = {}  # tool_name -> server_params

    for params in server_params_list:
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    for t in result.tools:
                        schema = t.inputSchema if hasattr(t, "inputSchema") else {}
                        if hasattr(schema, "model_dump"):
                            schema = schema.model_dump()
                        all_tools_raw.append({
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": schema or {"type": "object", "properties": {}},
                        })
                        tool_server_map[t.name] = params
        except Exception:
            pass  # Server unavailable — skip, don't crash

    current_messages = list(messages)
    max_iterations = 10

    for _ in range(max_iterations):
        kwargs: dict = {
            "model": model,
            "max_tokens": 2048,
            "system": system,
            "messages": current_messages,
        }
        if all_tools_raw:
            kwargs["tools"] = all_tools_raw

        response = client.messages.create(**kwargs)

        # No tool calls — we're done
        if response.stop_reason == "end_turn" or not any(
            hasattr(b, "type") and b.type == "tool_use" for b in response.content
        ):
            text = " ".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            return text, current_messages

        # Append assistant turn (serialize content blocks)
        current_messages.append({
            "role": "assistant",
            "content": [
                b.model_dump() if hasattr(b, "model_dump") else b
                for b in response.content
            ],
        })

        # Execute each tool_use block
        tool_results = []
        for block in response.content:
            if not (hasattr(block, "type") and block.type == "tool_use"):
                continue

            if status_callback:
                status_callback(f"Calling tool: `{block.name}`...")

            server_params = tool_server_map.get(block.name)
            if server_params is None:
                content = f"Tool `{block.name}` is not available."
            else:
                try:
                    async with stdio_client(server_params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(block.name, block.input)
                            content = "\n".join(
                                c.text if hasattr(c, "text") else str(c)
                                for c in result.content
                            )
                except Exception as e:
                    content = f"Tool error: {e}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        current_messages.append({"role": "user", "content": tool_results})

    return "Max tool iterations reached.", current_messages


def run_agentic_loop(
    messages: list,
    system: str,
    anthropic_key: str,
    model: str,
    server_params_list: list,
    status_callback=None,
) -> tuple[str, list]:
    """Sync wrapper for the agentic loop."""
    return _run_async(
        _async_agentic_loop(messages, system, anthropic_key, model, server_params_list, status_callback)
    )


# ---------------------------------------------------------------------------
# Local CSV Mode
# ---------------------------------------------------------------------------

def load_jira_csv(uploaded_file) -> pd.DataFrame:
    content = uploaded_file.read().decode("utf-8")
    df = pd.read_csv(StringIO(content))
    df.columns = [c.strip() for c in df.columns]
    return _normalize_jira_df(df)


def load_git_csv(uploaded_file) -> pd.DataFrame:
    content = uploaded_file.read().decode("utf-8")
    df = pd.read_csv(StringIO(content))
    df.columns = [c.strip() for c in df.columns]
    return df


def generate_sample_jira_df() -> pd.DataFrame:
    data = {
        "Issue Key": ["PROJ-101", "PROJ-102", "PROJ-103", "PROJ-104", "PROJ-105"],
        "Summary": [
            "Login page crashes on mobile",
            "Add dark mode toggle",
            "API rate limit not enforced",
            "Update onboarding copy",
            "Memory leak in data pipeline",
        ],
        "Priority": ["Critical", "Low", "High", "Medium", "Critical"],
        "Status": ["In Progress", "To Do", "In Progress", "Done", "Open"],
        "Assignee": ["alice", "bob", "Unassigned", "carol", "Unassigned"],
        "Issue Type": ["Bug", "Story", "Bug", "Task", "Bug"],
        "Component": ["core", "ui", "api", "docs", "core"],
        "Days Open": [3, 21, 7, 1, 30],
        "FixVersionDate": ["2026-03-20", "", "2026-03-25", "", ""],
        "SprintEndDate":  ["", "2026-04-08", "", "", "2026-04-15"],
    }
    return _normalize_jira_df(pd.DataFrame(data))


def generate_sample_git_df() -> pd.DataFrame:
    data = {
        "Branch": [
            "feature/PROJ-102", "bugfix/PROJ-101", "hotfix/PROJ-999",
            "main", "feature/no-ticket", "bugfix/PROJ-103",
        ],
        "Author": ["bob", "alice", "dave", "ci-bot", "eve", "mallory"],
        "Last Commit": [
            "2026-03-15", "2026-03-16", "2026-03-10",
            "2026-03-17", "2026-03-01", "2026-03-14",
        ],
        "Merged": [False, False, True, False, False, False],
        "Files Changed": [
            "ui/darkmode.js, ui/theme.css",
            "auth.py, login.py, src/utils.py",
            "billing.py, stripe.py, test_billing.py",
            "",
            "legacy_exporter.py, old_pipeline.py",
            "api/rate_limiter.py, config.py, migrations/0042_add_index.py",
        ],
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Dev-Status API  (Jira Software — linked PRs per ticket)
# ---------------------------------------------------------------------------

def fetch_dev_status(base_url: str, email: str, token: str, issue_key: str) -> dict:
    """
    Retrieve PR links for a Jira ticket via the dev-status REST API.
    Always returns a dict with keys: has_pr (bool), prs (list), description (str).
    Never raises — returns the safe fallback on any error.
    """
    _fallback: dict = {"has_pr": False, "prs": [], "description": ""}

    try:
        import requests
        from requests.auth import HTTPBasicAuth

        auth = HTTPBasicAuth(email, token)
        headers = {"Accept": "application/json"}
        base = base_url.rstrip("/")

        # Step 1 — get numeric issue ID + description
        issue_resp = requests.get(
            f"{base}/rest/api/3/issue/{issue_key}",
            params={"fields": "id,summary,description"},
            headers=headers, auth=auth, timeout=10,
        )
        issue_resp.raise_for_status()
        issue_data = issue_resp.json()
        issue_id = issue_data["id"]
        description = _extract_adf(issue_data.get("fields", {}).get("description"))

        # Step 2 — dev-status summary (check PR count)
        summary_resp = requests.get(
            f"{base}/rest/dev-status/1.0/issue/summary",
            params={"issueId": issue_id},
            headers=headers, auth=auth, timeout=10,
        )
        if summary_resp.status_code != 200:
            return {"has_pr": False, "prs": [], "description": description}

        pr_count = (
            summary_resp.json()
            .get("summary", {})
            .get("pullrequest", {})
            .get("overall", {})
            .get("count", 0)
        )
        if pr_count == 0:
            return {"has_pr": False, "prs": [], "description": description}

        # Step 3 — get PR details, try known application types
        prs = []
        for app_type in ["GitHub", "GitHub Enterprise", "Bitbucket", "GitLab", "Bitbucket Server"]:
            detail_resp = requests.get(
                f"{base}/rest/dev-status/1.0/issue/detail",
                params={"issueId": issue_id, "applicationType": app_type, "dataType": "pullrequest"},
                headers=headers, auth=auth, timeout=10,
            )
            if detail_resp.status_code != 200:
                continue
            for repo in detail_resp.json().get("detail", []):
                for pr in repo.get("pullRequests", []):
                    src = (pr.get("source") or {}).get("branch", "")
                    dst = (pr.get("destination") or {}).get("branch", "")
                    prs.append({
                        "title":              pr.get("name", ""),
                        "url":                pr.get("url", ""),
                        "status":             pr.get("status", "UNKNOWN"),
                        "author":             (pr.get("author") or {}).get("name", ""),
                        "source_branch":      src if isinstance(src, str) else src.get("name", ""),
                        "destination_branch": dst if isinstance(dst, str) else dst.get("name", ""),
                        "app_type":           app_type,
                    })

        return {"has_pr": bool(prs), "prs": prs, "description": description}

    except Exception:
        return _fallback


def _extract_adf(adf) -> str:
    """Flatten Atlassian Document Format (ADF) to plain text."""
    if adf is None:
        return ""
    if isinstance(adf, str):
        return adf
    parts: list[str] = []

    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf)
    return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# GitHub PR Diff
# ---------------------------------------------------------------------------

def fetch_github_pr_diff(pr_url: str, github_token: str = "") -> dict:
    """
    Fetch file-level diff summary for a GitHub PR.
    pr_url: https://github.com/owner/repo/pull/123
    Returns:
        {
          "title": str, "body": str, "state": str,
          "changed_files": int, "additions": int, "deletions": int,
          "files": [{"filename", "status", "additions", "deletions"}, ...],
          "diff_summary": str,   # truncated patch text for agent context
          "error": str | None,
        }
    """
    import re, requests

    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        return {"error": f"Cannot parse GitHub URL: {pr_url}", "diff_summary": ""}

    owner, repo, pr_number = match.groups()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    try:
        pr_resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=headers, timeout=10,
        )
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        files_resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers=headers, timeout=10,
        )
        files_resp.raise_for_status()
        files_data = files_resp.json()

        files = []
        additions = deletions = 0
        diff_parts = []
        for f in files_data[:25]:
            files.append({
                "filename":  f.get("filename", ""),
                "status":    f.get("status", ""),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
            })
            additions += f.get("additions", 0)
            deletions += f.get("deletions", 0)
            patch = f.get("patch", "")
            if patch:
                diff_parts.append(f"### {f['filename']}\n```diff\n{patch[:600]}\n```")

        return {
            "title":         pr_data.get("title", ""),
            "body":          (pr_data.get("body") or "")[:1000],
            "state":         pr_data.get("state", ""),
            "changed_files": pr_data.get("changed_files", 0),
            "additions":     additions,
            "deletions":     deletions,
            "files":         files,
            "diff_summary":  "\n\n".join(diff_parts[:6]),
            "error":         None,
        }
    except Exception as e:
        return {"error": str(e), "diff_summary": "", "files": [],
                "additions": 0, "deletions": 0, "changed_files": 0}


# ---------------------------------------------------------------------------
# Release Audit: QA Environment Payload
# ---------------------------------------------------------------------------

def fetch_qa_payload(
    base_url: str, email: str, token: str,
    project_key: str, github_token: str = "", hours: int = 24,
) -> list[dict]:
    """
    Fetch all PRs that have been Merged or Deployed in the last N hours.
    Returns a list of payload items, one per merged PR:
        {ticket_key, ticket_summary, ticket_status, pr_url, pr_title,
         pr_status, pr_author, source_branch, files: [str]}
    """
    import requests
    from requests.auth import HTTPBasicAuth

    auth    = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json"}
    base    = base_url.rstrip("/")

    # Query recently updated tickets
    jql = (f'project = {project_key} AND updated >= "-{hours}h" '
           f'ORDER BY updated DESC')
    resp = requests.post(
        f"{base}/rest/api/3/search/jql",
        json={"jql": jql, "maxResults": 40,
              "fields": ["id", "summary", "status"]},
        headers={**headers, "Content-Type": "application/json"},
        auth=auth, timeout=15,
    )
    resp.raise_for_status()

    payload: list[dict] = []
    for issue in resp.json().get("issues", []):
        issue_id      = issue["id"]
        issue_key     = issue["key"]
        issue_summary = issue["fields"]["summary"]
        issue_status  = issue["fields"]["status"]["name"]

        try:
            # Check if any PRs exist
            sum_resp = requests.get(
                f"{base}/rest/dev-status/1.0/issue/summary",
                params={"issueId": issue_id},
                headers=headers, auth=auth, timeout=5,
            )
            if sum_resp.status_code != 200:
                continue
            if (sum_resp.json().get("summary", {})
                    .get("pullrequest", {}).get("overall", {}).get("count", 0) == 0):
                continue

            # Pull PR details
            for app_type in ["GitHub", "GitHub Enterprise", "Bitbucket", "GitLab"]:
                det_resp = requests.get(
                    f"{base}/rest/dev-status/1.0/issue/detail",
                    params={"issueId": issue_id, "applicationType": app_type,
                            "dataType": "pullrequest"},
                    headers=headers, auth=auth, timeout=5,
                )
                if det_resp.status_code != 200:
                    continue
                for repo in det_resp.json().get("detail", []):
                    for pr in repo.get("pullRequests", []):
                        pr_status = pr.get("status", "").upper()
                        if pr_status not in ("MERGED", "DEPLOYED"):
                            continue

                        item: dict = {
                            "ticket_key":     issue_key,
                            "ticket_summary": issue_summary,
                            "ticket_status":  issue_status,
                            "pr_url":         pr.get("url", ""),
                            "pr_title":       pr.get("name", ""),
                            "pr_status":      pr_status,
                            "pr_author":      (pr.get("author") or {}).get("name", ""),
                            "source_branch":  (pr.get("source") or {}).get("branch", {}).get("name", ""),
                            "files":          [],
                        }

                        # Enrich with file list if GitHub token provided
                        if github_token and "github.com" in item["pr_url"]:
                            diff = fetch_github_pr_diff(item["pr_url"], github_token)
                            item["files"] = [f["filename"] for f in diff.get("files", [])]

                        payload.append(item)
        except Exception:
            continue

    return payload


def detect_collisions(payload: list[dict]) -> list[dict]:
    """
    Identify files and modules touched by multiple tickets in the payload.
    Returns a list of collision dicts:
        {"type": "FILE"|"MODULE", "location": str,
         "tickets": [str], "authors": [str]}
    """
    from collections import defaultdict

    file_map:   dict = defaultdict(list)
    module_map: dict = defaultdict(list)

    for item in payload:
        for filepath in item.get("files", []):
            entry = {"ticket": item["ticket_key"], "author": item["pr_author"],
                     "pr_url": item["pr_url"]}
            file_map[filepath].append(entry)

            # Derive module from path (skip generic top-level dirs)
            parts = [p for p in filepath.split("/") if p]
            skip  = {"src", "app", "lib", "pkg", "internal", "cmd"}
            module = next((p for p in parts if p not in skip), parts[0] if parts else "root")
            module_map[module].append({**entry, "file": filepath})

    collisions: list[dict] = []
    seen_files: set = set()

    # File-level (highest precision)
    for filepath, touches in file_map.items():
        tickets = list(dict.fromkeys(t["ticket"] for t in touches))
        authors = list(dict.fromkeys(t["author"] for t in touches))
        if len(tickets) > 1:
            collisions.append({"type": "FILE", "location": filepath,
                                "tickets": tickets, "authors": authors})
            seen_files.add(filepath)

    # Module-level (broader — only if not already captured at file level)
    for module, touches in module_map.items():
        tickets = list(dict.fromkeys(t["ticket"] for t in touches))
        authors = list(dict.fromkeys(t["author"] for t in touches))
        module_files = {t["file"] for t in touches}
        if len(tickets) > 1 and not module_files.intersection(seen_files):
            collisions.append({"type": "MODULE", "location": module,
                                "tickets": tickets, "authors": authors})

    return collisions


def check_not_yet_deployed(
    jira_df: pd.DataFrame,
    dev_status_map: dict,
) -> list[dict]:
    """
    Find tickets in 'Ready for QA' (or similar) whose linked PR is still OPEN.
    dev_status_map: {issue_key: fetch_dev_status() result}
    Returns list of {ticket_key, summary, pr_url, pr_title, pr_status}.
    """
    READY_STATUSES = {"ready for qa", "ready for testing", "in testing", "to test"}
    not_deployed: list[dict] = []

    for _, row in jira_df.iterrows():
        key    = row.get("Issue Key", "")
        status = str(row.get("Status", "")).lower().strip()
        if status not in READY_STATUSES:
            continue

        dev = dev_status_map.get(key)
        if not dev:
            continue

        for pr in dev.get("prs", []):
            if pr.get("status", "").upper() not in ("MERGED", "DEPLOYED"):
                not_deployed.append({
                    "ticket_key": key,
                    "summary":    row.get("Summary", ""),
                    "pr_url":     pr.get("url", ""),
                    "pr_title":   pr.get("title", ""),
                    "pr_status":  pr.get("status", "UNKNOWN"),
                })

    return not_deployed


# ---------------------------------------------------------------------------
# REST API Fallback (Live Mode without MCP)
# ---------------------------------------------------------------------------

def fetch_live_jira(base_url: str, email: str, token: str,
                     project_key: str, max_results: int = 100,
                     jql_override: str | None = None) -> pd.DataFrame:
    import requests
    from requests.auth import HTTPBasicAuth

    jql = jql_override if jql_override else f"project = {project_key} ORDER BY created DESC"
    url = f"{base_url.rstrip('/')}/rest/api/3/search/jql"
    resp = requests.post(
        url,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={"jql": jql,
              "maxResults": max_results,
              "fields": ["summary", "priority", "status", "assignee",
                         "issuetype", "components", "created",
                         "fixVersions", "customfield_10020"]},
        auth=HTTPBasicAuth(email, token),
        timeout=15,
    )
    resp.raise_for_status()

    rows = []
    for issue in resp.json().get("issues", []):
        f = issue["fields"]
        rows.append({
            "Issue Key": issue["key"],
            "Summary": f.get("summary", ""),
            "Priority": (f.get("priority") or {}).get("name", "Unknown"),
            "Status": (f.get("status") or {}).get("name", "Unknown"),
            "Assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "Issue Type": (f.get("issuetype") or {}).get("name", "Unknown"),
            "Component": ", ".join(c["name"] for c in (f.get("components") or [])) or "None",
            "Days Open": _days_since(f.get("created", "")),
            "FixVersionDate": _nearest_fix_version_date(f.get("fixVersions", [])),
            "SprintEndDate":  _parse_sprint_end_date(f.get("customfield_10020")),
        })

    return _normalize_jira_df(pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# Jira Filter Helpers (labels, statuses, sprints via REST API)
# ---------------------------------------------------------------------------

def fetch_jira_labels(base_url: str, email: str, token: str, project_key: str) -> list[str]:
    """Fetch all unique labels used in the Jira project."""
    import requests
    from requests.auth import HTTPBasicAuth

    resp = requests.post(
        f"{base_url.rstrip('/')}/rest/api/3/search/jql",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={"jql": f"project = {project_key} AND labels is not EMPTY",
              "maxResults": 100, "fields": ["labels"]},
        auth=HTTPBasicAuth(email, token),
        timeout=15,
    )
    resp.raise_for_status()
    labels: set[str] = set()
    for issue in resp.json().get("issues", []):
        for label in issue.get("fields", {}).get("labels", []):
            labels.add(label)
    return sorted(labels)


def fetch_jira_statuses(base_url: str, email: str, token: str, project_key: str) -> list[str]:
    """Fetch all statuses available in the Jira project."""
    import requests
    from requests.auth import HTTPBasicAuth

    resp = requests.get(
        f"{base_url.rstrip('/')}/rest/api/3/project/{project_key}/statuses",
        headers={"Accept": "application/json"},
        auth=HTTPBasicAuth(email, token),
        timeout=10,
    )
    resp.raise_for_status()
    statuses: set[str] = set()
    for issue_type in resp.json():
        for status in issue_type.get("statuses", []):
            name = status.get("name", "")
            if name:
                statuses.add(name)
    return sorted(statuses)


def fetch_jira_sprints(base_url: str, email: str, token: str, project_key: str) -> dict[str, int]:
    """Fetch all sprints (active and closed) for the Jira project.

    Returns a {name: id} dict so the JQL builder can use integer sprint IDs.
    """
    import requests
    from requests.auth import HTTPBasicAuth

    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json"}
    base = base_url.rstrip("/")

    boards_resp = requests.get(
        f"{base}/rest/agile/1.0/board",
        params={"projectKeyOrId": project_key},
        headers=headers, auth=auth, timeout=10,
    )
    if boards_resp.status_code != 200:
        return {}
    boards = boards_resp.json().get("values", [])
    if not boards:
        return {}

    board_id = boards[0]["id"]
    sprints: dict[str, int] = {}
    start = 0
    while True:
        resp = requests.get(
            f"{base}/rest/agile/1.0/board/{board_id}/sprint",
            params={"startAt": start, "maxResults": 50},
            headers=headers, auth=auth, timeout=10,
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        for sprint in data.get("values", []):
            name = sprint.get("name", "")
            sprint_id = sprint.get("id")
            if name and sprint_id is not None:
                sprints[name] = sprint_id
        if data.get("isLast", True):
            break
        start += 50
    return sprints


# ---------------------------------------------------------------------------
# Release Proximity Helpers (SCRUM-18)
# ---------------------------------------------------------------------------

def _nearest_fix_version_date(fix_versions: list) -> str:
    """Return the nearest fix version releaseDate as ISO string, or ''."""
    from datetime import date
    nearest = None
    for v in (fix_versions or []):
        rd = v.get("releaseDate", "") if isinstance(v, dict) else ""
        if rd:
            try:
                d = date.fromisoformat(str(rd)[:10])
                if nearest is None or d < nearest:
                    nearest = d
            except Exception:
                pass
    return nearest.isoformat() if nearest else ""


def _parse_sprint_end_date(sprint_field) -> str:
    """Extract sprint end date from Jira customfield_10020, or ''."""
    if not sprint_field:
        return ""
    sprints = sprint_field if isinstance(sprint_field, list) else [sprint_field]
    for sprint in sprints:
        if isinstance(sprint, dict):
            end = sprint.get("endDate", "")
            if end:
                return str(end)[:10]
        elif isinstance(sprint, str):
            m = re.search(r"endDate=([^,\]\s]+)", sprint)
            if m:
                return m.group(1)[:10]
    return ""


def _days_until_release(row) -> int | None:
    """Return minimum days until release (fix version or sprint end), or None."""
    from datetime import date
    today = date.today()
    candidates = []
    for col in ("FixVersionDate", "SprintEndDate"):
        ds = str(row.get(col, "") or "")
        if len(ds) >= 10:
            try:
                candidates.append((date.fromisoformat(ds[:10]) - today).days)
            except Exception:
                pass
    return min(candidates) if candidates else None


def _release_proximity_score(days: int | None) -> int:
    """Convert days until release to an urgency score contribution."""
    if days is None:
        return 0
    if days <= 2:
        return 70
    if days <= 7:
        return 35
    if days <= 14:
        return 20
    if days <= 21:
        return 5
    return 0


# ---------------------------------------------------------------------------
# Risk Scoring
# ---------------------------------------------------------------------------

def compute_risk_scores(
    jira_df: pd.DataFrame,
    git_df: pd.DataFrame | None = None,
    pr_cache: dict | None = None,
) -> pd.DataFrame:
    df = jira_df.copy()

    # --- Existing health signals ---
    priority_map = {"critical": 30, "high": 20, "medium": 10, "low": 5, "unknown": 15}
    df["_p"] = df["Priority"].str.lower().map(priority_map).fillna(15)
    df["_a"] = df["Days Open"].apply(lambda d: 20 if d > 14 else 10 if d > 7 else 0)
    if git_df is not None:
        linked = _extract_jira_keys_from_branches(git_df)
        df["_b"] = df["Issue Key"].apply(lambda k: 0 if k in linked else 25)
    else:
        df["_b"] = 12
    if pr_cache:
        df["_b"] = df.apply(
            lambda r: 0 if pr_cache.get(r["Issue Key"]) is True else r["_b"], axis=1
        )
    is_bug  = df["Issue Type"].str.lower().str.contains("bug", na=False)
    is_core = df["Component"].str.lower().str.contains("core|api", na=False)
    df["_t"] = (is_bug & is_core).map({True: 15, False: 5}).fillna(5)
    df["_u"] = df["Assignee"].str.lower().apply(lambda a: 10 if "unassigned" in a else 0)

    # --- Release proximity signal (SCRUM-18) ---
    df["_days_until"] = df.apply(_days_until_release, axis=1)
    df["_r"] = df["_days_until"].apply(_release_proximity_score)
    # Status vs proximity boost: active work with ≤2 days → extra push to RED
    in_progress_mask   = df["Status"].str.lower().str.contains(
        "in progress|in qa|in testing|in review", na=False
    )
    critical_time_mask = df["_days_until"].apply(lambda d: d is not None and d <= 2)
    df["_r"] = df["_r"] + (in_progress_mask & critical_time_mask) * 10

    df["RiskScore"] = (
        df["_p"] + df["_a"] + df["_b"] + df["_t"] + df["_u"] + df["_r"]
    ).clip(0, 100).astype(int)
    df["RiskBand"] = df["RiskScore"].apply(_score_to_band)

    def _reasons(row):
        reasons = []
        p = row["Priority"].lower()
        if p == "critical":
            reasons.append("Critical priority")
        elif p == "high":
            reasons.append("High priority")
        d = row["Days Open"]
        if d > 14:
            reasons.append(f"Open {int(d)} days")
        elif d > 7:
            reasons.append(f"Open {int(d)} days")
        if row["_b"] == 25:
            reasons.append("No linked branch")
        elif row["_b"] == 12:
            reasons.append("Branch link unknown")
        if row["_t"] == 15:
            reasons.append("Bug in core/API")
        if row["_u"] == 10:
            reasons.append("Unassigned")
        # Release proximity reason
        days = row["_days_until"]
        if days is not None:
            if days <= 0:
                reasons.append(f"Release overdue by {abs(int(days))}d")
            elif days == 1:
                reasons.append("1 day until release")
            else:
                reasons.append(f"{int(days)} days until release")
        return reasons

    df["RiskReasons"] = df.apply(_reasons, axis=1)
    return df.drop(columns=["_p", "_a", "_b", "_t", "_u", "_r", "_days_until"])


# ---------------------------------------------------------------------------
# PR Risk Analysis
# ---------------------------------------------------------------------------

_TEST_PATTERNS = re.compile(r"(test_|_test\.|\.spec\.|_spec\.|/tests?/|__tests?__)", re.IGNORECASE)
_SOURCE_EXTENSIONS = re.compile(r"\.(py|js|ts|tsx|jsx|java|go|rb|cs|cpp|c|kt|swift)$", re.IGNORECASE)
_LEGACY_PATTERNS = re.compile(
    r"(auth|login|session|middleware|permissions?|jwt|oauth|security"
    r"|settings|config|database|db\.py|models|schema|migrations?"
    r"|payment|billing|checkout|stripe|invoice"
    r"|legacy|old_|_v1|_deprecated"
    r"|\.github/workflows|Dockerfile|docker-compose|Makefile|\.circleci)",
    re.IGNORECASE,
)


def analyze_pr_risks(git_df: pd.DataFrame) -> list[dict]:
    if "Files Changed" not in git_df.columns:
        return []
    results = []
    for _, row in git_df.iterrows():
        files = [f.strip() for f in str(row.get("Files Changed", "")).split(",") if f.strip()]
        if not files:
            continue
        has_source = any(_SOURCE_EXTENSIONS.search(f) for f in files)
        has_tests = any(_TEST_PATTERNS.search(f) for f in files)
        missing_tests = has_source and not has_tests
        legacy_hits = [f for f in files if _LEGACY_PATTERNS.search(f)]
        if missing_tests or legacy_hits:
            flags = []
            if missing_tests:
                flags.append("MISSING TESTS")
            if legacy_hits:
                flags.append("LEGACY FILE RISK")
            results.append({
                "Branch": str(row.get("Branch", "")),
                "Author": str(row.get("Author", "Unknown")),
                "Flags": " | ".join(flags),
                "Legacy Files": legacy_hits,
                "Missing Tests": missing_tests,
                "Severity": "HIGH RISK" if (missing_tests and legacy_hits) else "ELEVATED RISK",
            })
    return results


def correlate_branches(jira_df: pd.DataFrame, git_df: pd.DataFrame) -> dict:
    linked_keys = _extract_jira_keys_from_branches(git_df)
    all_keys = set(jira_df["Issue Key"].tolist())
    correlated = []
    for _, row in git_df.iterrows():
        for k in re.findall(r"[A-Z]+-\d+", row.get("Branch", "")):
            if k in all_keys:
                correlated.append((k, row["Branch"]))
    orphaned = sorted(all_keys - linked_keys)
    unlinked = git_df[
        ~git_df["Branch"].apply(lambda b: bool(re.search(r"[A-Z]+-\d+", str(b))))
        & ~git_df["Branch"].isin(["main", "master", "develop", "staging"])
    ]["Branch"].tolist()
    return {"correlated": correlated, "orphaned_tickets": orphaned, "unlinked_branches": unlinked}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_jira_df(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "Issue Key": "UNKNOWN", "Summary": "", "Priority": "Unknown",
        "Status": "Unknown", "Assignee": "Unassigned",
        "Issue Type": "Unknown", "Component": "None", "Days Open": 0,
        "FixVersionDate": "",
        "SprintEndDate":  "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


def _extract_jira_keys_from_branches(git_df: pd.DataFrame) -> set:
    keys = set()
    for branch in git_df.get("Branch", []):
        keys.update(re.findall(r"[A-Z]+-\d+", str(branch)))
    return keys


def _score_to_band(score: int) -> str:
    if score <= 30:
        return "GREEN"
    elif score <= 60:
        return "YELLOW"
    elif score <= 80:
        return "ORANGE"
    return "RED"


def _days_since(iso_date_str: str) -> int:
    if not iso_date_str:
        return 0
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0
