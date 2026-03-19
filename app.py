"""
app.py — PodQApath | Command Center
Jira | Git | Chat
"""

import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path

import mcp_bridge as bridge

load_dotenv()

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PodQApath | Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

AGENT_MD_PATH = Path(__file__).parent / "QA_AGENT.md"
QA_SYSTEM_PROMPT = AGENT_MD_PATH.read_text() if AGENT_MD_PATH.exists() else "You are a QA assistant."

# ---------------------------------------------------------------------------
# Pod Configuration
# Edit POD_FIELD_ID to match your Jira custom field (Admin > Custom Fields).
# Edit POD_QA_MAP to map pod names to your QA team members.
# Both can also be set via environment variables.
# ---------------------------------------------------------------------------

POD_FIELD_ID: str = os.getenv("POD_FIELD_ID", "customfield_10020")

import json as _json
_pod_qa_env = os.getenv("POD_QA_MAP", "")
POD_QA_MAP: dict[str, str] = (
    _json.loads(_pod_qa_env) if _pod_qa_env else {
        "Platform":    "Alice Chen",
        "Growth":      "Bob Martinez",
        "Payments":    "Carol Singh",
        "Core API":    "Dave Kim",
        "Mobile":      "Eve Okafor",
    }
)

TARGET_STATUSES: list[str] = [
    "Ready for QA",
    "In Testing",
    "In Progress",
    "In Review",
    "To Do",
    "Done",
]

# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

defaults = {
    "jira_df": None,
    "git_df": None,
    "chat_history": [],
    "mode": "local",
    "mcp_server_params": [],
    "mcp_tools_available": [],
    "git_status_text": "",
    "selected_pod": "All Pods",
    "selected_status": "All Statuses",
    # Dev-status / PR tracking
    "selected_ticket_key": None,
    "dev_status_data": None,
    "pr_diff_data": None,
    "traceability_cache": {},
    # Credentials carried across reruns
    "_jira_base_url": "",
    "_jira_email": "",
    "_jira_token": "",
    "_github_token": "",
    "_project_key": "",
    # Live mode filter state
    "_available_tags": [],
    "_available_statuses": [],
    "_available_sprints": {},
    "_filters_loaded": False,
    "_filter_tags": [],
    "_filter_statuses": [],
    "_filter_sprints": [],
    # Release Audit / Environment Monitor
    "qa_payload": [],           # merged PRs from last 24h
    "collision_warnings": [],   # cross-PR file/module collisions
    "not_yet_deployed": [],     # Ready for QA tickets with open PRs
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛡️ PodQApath")
    st.markdown("### *Bridging the gap between Pods, Tickets, and Code*")
    st.divider()

    mode_label = st.radio(
        "Data Source Mode",
        options=["local", "live"],
        format_func=lambda x: "📂 Local CSV Audit" if x == "local" else "☁️ Live MCP / Cloud API",
        index=0 if st.session_state.mode == "local" else 1,
        key="mode_radio",
    )
    st.session_state.mode = mode_label

    # ---- Pod Filters (shown in both modes) ----
    st.divider()
    st.subheader("Pod Filters")

    pod_options = ["All Pods"] + sorted(POD_QA_MAP.keys())
    selected_pod = st.selectbox(
        "Select Pod",
        options=pod_options,
        index=pod_options.index(st.session_state.selected_pod)
              if st.session_state.selected_pod in pod_options else 0,
        key="pod_selector",
    )
    st.session_state.selected_pod = selected_pod

    status_options = ["All Statuses"] + TARGET_STATUSES
    selected_status = st.selectbox(
        "Target Status",
        options=status_options,
        index=status_options.index(st.session_state.selected_status)
              if st.session_state.selected_status in status_options else 0,
        key="status_selector",
    )
    st.session_state.selected_status = selected_status

    # Show assigned QA for the active pod
    if selected_pod != "All Pods":
        assigned_qa = POD_QA_MAP.get(selected_pod, "Unassigned")
        st.caption(f"Assigned QA: **{assigned_qa}**")

    st.divider()

    # ---- LOCAL MODE ----
    if st.session_state.mode == "local":
        st.subheader("Upload CSV Files")
        jira_file = st.file_uploader("Jira Export CSV", type=["csv"], key="jira_upload")
        git_file  = st.file_uploader("Git Branch CSV",  type=["csv"], key="git_upload")

        if jira_file:
            st.session_state.jira_df = bridge.load_jira_csv(jira_file)
            st.success("Jira CSV loaded")
        if git_file:
            st.session_state.git_df = bridge.load_git_csv(git_file)
            st.success("Git CSV loaded")

        st.divider()
        if st.button("Load Sample Data", use_container_width=True):
            st.session_state.jira_df = bridge.generate_sample_jira_df()
            st.session_state.git_df  = bridge.generate_sample_git_df()
            st.session_state.mcp_server_params = []
            st.success("Sample data loaded")

    # ---- LIVE MCP MODE ----
    else:
        # Load credentials exclusively from .env
        base_url     = os.getenv("JIRA_BASE_URL", "")
        email        = os.getenv("JIRA_EMAIL", "")
        token        = os.getenv("JIRA_API_TOKEN", "")
        project_key  = os.getenv("JIRA_PROJECT_KEY", "PROJ")
        github_token = os.getenv("GITHUB_TOKEN", "")
        max_results  = int(os.getenv("JIRA_MAX_RESULTS", "50"))
        repo_path    = os.getenv("GIT_REPO_PATH", "")

        missing_vars = [k for k, v in {
            "JIRA_BASE_URL": base_url, "JIRA_EMAIL": email,
            "JIRA_API_TOKEN": token, "JIRA_PROJECT_KEY": project_key,
        }.items() if not v]
        if missing_vars:
            st.error(f"Missing .env vars: {', '.join(missing_vars)}")

        use_mcp = st.toggle("Use MCP Server", value=True,
                             help="Connect via mcp-atlassian. Disable to use plain REST API.")

        # ---- Connect & Load Filters ----
        if st.button("Connect & Load Filters", use_container_width=True,
                     disabled=bool(missing_vars)):
            with st.spinner("Fetching filters from Jira..."):
                try:
                    st.session_state._available_tags     = bridge.fetch_jira_labels(base_url, email, token, project_key)
                    st.session_state._available_statuses = bridge.fetch_jira_statuses(base_url, email, token, project_key)
                    st.session_state._available_sprints  = bridge.fetch_jira_sprints(base_url, email, token, project_key)
                    st.session_state._filters_loaded     = True
                    st.session_state._jira_base_url      = base_url
                    st.session_state._jira_email         = email
                    st.session_state._jira_token         = token
                    st.session_state._github_token       = github_token
                    st.session_state._project_key        = project_key
                    st.success("Filters loaded")
                except Exception as e:
                    st.error(f"Failed to load filters: {e}")

        # ---- Filter Dropdowns ----
        _tag_default    = [t for t in st.session_state._filter_tags     if t in st.session_state._available_tags]
        _status_default = [s for s in st.session_state._filter_statuses if s in st.session_state._available_statuses]
        _sprint_default = [s for s in st.session_state._filter_sprints  if s in st.session_state._available_sprints]

        st.session_state._filter_tags = st.multiselect(
            "Tags", options=st.session_state._available_tags, default=_tag_default,
            placeholder="All tags", disabled=not st.session_state._filters_loaded,
        )
        st.session_state._filter_statuses = st.multiselect(
            "Statuses", options=st.session_state._available_statuses, default=_status_default,
            placeholder="All statuses", disabled=not st.session_state._filters_loaded,
        )
        st.session_state._filter_sprints = st.multiselect(
            "Sprint", options=list(st.session_state._available_sprints.keys()), default=_sprint_default,
            placeholder="All sprints", disabled=not st.session_state._filters_loaded,
        )

        if st.button("Fetch Live Data", use_container_width=True, type="primary",
                     disabled=bool(missing_vars)):
            # Build JQL — apply pod + dropdown filters
            jql_parts = [f"project = {project_key}"]
            if selected_pod != "All Pods":
                jql_parts.append(f'"{POD_FIELD_ID}" = "{selected_pod}"')
            if selected_status != "All Statuses":
                jql_parts.append(f'status = "{selected_status}"')
            if st.session_state._filter_tags:
                tags_jql = ", ".join(f'"{t}"' for t in st.session_state._filter_tags)
                jql_parts.append(f"labels in ({tags_jql})")
            if st.session_state._filter_statuses:
                statuses_jql = ", ".join(f'"{s}"' for s in st.session_state._filter_statuses)
                jql_parts.append(f"status in ({statuses_jql})")
            if st.session_state._filter_sprints:
                sprints_jql = ", ".join(
                    str(st.session_state._available_sprints[s])
                    for s in st.session_state._filter_sprints
                    if s in st.session_state._available_sprints
                )
                if sprints_jql:
                    jql_parts.append(f"sprint in ({sprints_jql})")
            jql_parts.append("ORDER BY created DESC")
            custom_jql = " AND ".join(jql_parts[:-1]) + " " + jql_parts[-1]

            st.caption(f"JQL: `{custom_jql}`")

            params_list = []
            # --- Jira ---
            if use_mcp:
                with st.spinner("Connecting to Atlassian MCP server..."):
                    try:
                        jira_params = bridge.atlassian_server_params(base_url, email, token)
                        st.session_state.jira_df = bridge.fetch_jira_via_mcp(
                            base_url, email, token, project_key, max_results,
                            jql_override=custom_jql,
                        )
                        params_list = [jira_params]
                        tools = bridge.list_mcp_tools(jira_params)
                        st.session_state.mcp_tools_available = [t.name for t in tools]
                        st.success(f"MCP: fetched {len(st.session_state.jira_df)} issues "
                                   f"({len(tools)} tools available)")
                    except Exception as e:
                        st.warning(f"MCP failed ({e}). Falling back to REST API...")
                        try:
                            st.session_state.jira_df = bridge.fetch_live_jira(
                                base_url, email, token, project_key, max_results,
                                jql_override=custom_jql,
                            )
                            st.session_state.mcp_tools_available = []
                            st.success(f"REST: fetched {len(st.session_state.jira_df)} issues")
                        except Exception as e2:
                            st.error(f"REST API also failed: {e2}")
            else:
                with st.spinner("Fetching from Jira REST API..."):
                    try:
                        st.session_state.jira_df = bridge.fetch_live_jira(
                            base_url, email, token, project_key, max_results,
                            jql_override=custom_jql,
                        )
                        st.session_state.mcp_tools_available = []
                        st.success(f"REST: fetched {len(st.session_state.jira_df)} issues")
                    except Exception as e:
                        st.error(f"Jira API error: {e}")

            # Reset payload on new fetch
            st.session_state.qa_payload        = []
            st.session_state.collision_warnings = []
            st.session_state.not_yet_deployed   = []

            # --- Git via MCP ---
            if repo_path and use_mcp:
                with st.spinner("Connecting to Git MCP server..."):
                    try:
                        git_params = bridge.git_server_params(repo_path)
                        st.session_state.git_df = bridge.fetch_git_status_via_mcp(repo_path)
                        git_tools = bridge.list_mcp_tools(git_params)
                        params_list.append(git_params)
                        st.success(f"Git MCP: {len(git_tools)} tools available")
                    except Exception as e:
                        st.warning(f"Git MCP unavailable: {e}")

            st.session_state.mcp_server_params = params_list
            st.session_state._jira_base_url    = base_url
            st.session_state._jira_email       = email
            st.session_state._jira_token       = token
            st.session_state._github_token     = github_token
            st.session_state._project_key      = project_key

    # ---- QA Payload (live mode only) ----
    if st.session_state.mode == "live":
        st.divider()
        has_creds_sidebar = bool(st.session_state._jira_base_url and st.session_state._jira_token)
        audit_hours = st.number_input("Audit Window (hours)", min_value=1, max_value=168,
                                       value=24, step=1, key="audit_hours")
        if st.button("🚀 Load QA Payload", use_container_width=True,
                     disabled=not has_creds_sidebar,
                     help="Fetch merged PRs from the last N hours"):
            with st.spinner(f"Scanning last {audit_hours}h for merged PRs..."):
                try:
                    payload = bridge.fetch_qa_payload(
                        st.session_state._jira_base_url,
                        st.session_state._jira_email,
                        st.session_state._jira_token,
                        st.session_state._project_key,
                        github_token=st.session_state._github_token,
                        hours=int(audit_hours),
                    )
                    st.session_state.qa_payload = payload
                    st.session_state.collision_warnings = bridge.detect_collisions(payload)
                    # Status sync — build dev_status_map from traceability_cache
                    if st.session_state.jira_df is not None:
                        # Use cached dev_status data we already have
                        dev_map = {}
                        if st.session_state.dev_status_data and st.session_state.selected_ticket_key:
                            dev_map[st.session_state.selected_ticket_key] = st.session_state.dev_status_data
                        st.session_state.not_yet_deployed = bridge.check_not_yet_deployed(
                            st.session_state.jira_df, dev_map
                        )
                    st.success(f"Payload: {len(payload)} merged PRs | "
                               f"{len(st.session_state.collision_warnings)} collision(s)")
                except Exception as e:
                    st.error(f"Payload fetch error: {e}")

    st.divider()

    # Risk overview
    if st.session_state.jira_df is not None:
        df_scored = bridge.compute_risk_scores(st.session_state.jira_df, st.session_state.git_df)
        band_counts = df_scored["RiskBand"].value_counts()
        st.subheader("Risk Overview")
        for band, emoji in [("RED", "🔴"), ("ORANGE", "🟠"), ("YELLOW", "🟡"), ("GREEN", "🟢")]:
            st.metric(f"{emoji} {band}", band_counts.get(band, 0))

    # MCP status
    if st.session_state.mcp_server_params:
        st.divider()
        st.caption(f"🔌 **MCP Active** — {len(st.session_state.mcp_server_params)} server(s), "
                   f"{len(st.session_state.mcp_tools_available)} tools")
        if st.session_state.mcp_tools_available:
            with st.expander("Available Tools"):
                for name in sorted(st.session_state.mcp_tools_available):
                    st.code(name, language=None)

# ---------------------------------------------------------------------------
# Main Layout
# ---------------------------------------------------------------------------

col1, col2, col3 = st.columns([2, 2, 1.5], gap="medium")

# ---------------------------------------------------------------------------
# Column 1: Jira
# ---------------------------------------------------------------------------

with col1:
    source_badge = "🔌 MCP" if st.session_state.mcp_server_params else "📂 Local/REST"
    st.header(f"🎫 Jira Tickets {source_badge}")

    # Active filter badges
    active_pod    = st.session_state.selected_pod
    active_status = st.session_state.selected_status
    badge_parts = []
    if active_pod != "All Pods":
        assigned_qa = POD_QA_MAP.get(active_pod, "Unassigned")
        badge_parts.append(f"Pod: **{active_pod}** → QA: **{assigned_qa}**")
    if active_status != "All Statuses":
        badge_parts.append(f"Status: **{active_status}**")
    if badge_parts:
        st.caption("  |  ".join(badge_parts))

    if st.session_state.jira_df is None:
        st.info("No Jira data. Upload a CSV or connect via the sidebar.")
    else:
        df_scored = bridge.compute_risk_scores(st.session_state.jira_df, st.session_state.git_df)

        # Assigned QA column
        if "Pod" in df_scored.columns:
            df_scored["Assigned QA"] = df_scored["Pod"].map(POD_QA_MAP).fillna("Unassigned")
        else:
            qa_for_pod = POD_QA_MAP.get(active_pod, "—") if active_pod != "All Pods" else "—"
            df_scored["Assigned QA"] = qa_for_pod

        # Traceability badge column — uses cache, "—" if not yet checked
        cache = st.session_state.traceability_cache
        df_scored["PR"] = df_scored["Issue Key"].map(
            lambda k: "✅" if cache.get(k) is True
                      else "🔴" if cache.get(k) is False
                      else "—"
        )

        display_df = df_scored.reset_index(drop=True)

        BAND_EMOJI = {"RED": "🔴", "ORANGE": "🟠", "YELLOW": "🟡", "GREEN": "🟢"}
        BAND_LABEL = {
            "RED":    ("🔴 Critical risk", "Score 81–100 — needs attention before release"),
            "ORANGE": ("🟠 High risk",     "Score 61–80 — review carefully"),
            "YELLOW": ("🟡 Medium risk",   "Score 31–60 — monitor closely"),
            "GREEN":  ("🟢 Low risk",      "Score 0–30 — looking good"),
        }

        with st.expander("Risk score guide", expanded=False):
            for band in ["RED", "ORANGE", "YELLOW", "GREEN"]:
                label, desc = BAND_LABEL[band]
                st.markdown(f"**{label}** — {desc}")
            st.caption(
                "Score factors: priority (+5–30), days open (+0–20), "
                "no linked branch (+25), bug in core/API (+15), unassigned (+10)"
            )

        # Card list — full width, stacked
        for _, card_row in display_df.iterrows():
            c_key    = card_row["Issue Key"]
            band     = card_row["RiskBand"]
            score    = card_row["RiskScore"]
            status   = card_row["Status"]
            pr_icon  = card_row["PR"]
            reasons  = card_row.get("RiskReasons") or []
            selected = st.session_state.selected_ticket_key == c_key
            with st.container(border=True):
                summary = str(card_row.get("Summary", ""))
                summary_short = summary[:55] + "…" if len(summary) > 55 else summary
                jira_base = st.session_state.get("_jira_base_url", "").rstrip("/")
                if jira_base:
                    key_html = f'<a href="{jira_base}/browse/{c_key}" target="_blank" style="text-decoration:none;">{c_key}</a>'
                else:
                    key_html = f"<strong>{c_key}</strong>"
                band_label, _ = BAND_LABEL.get(band, (f"{BAND_EMOJI.get(band,'⚪')} {band}", ""))
                reasons_str = " · ".join(reasons) if reasons else "No risk flags"
                st.markdown(
                    f"{BAND_EMOJI.get(band, '⚪')} {key_html} {pr_icon} "
                    f"<span style='font-size:0.8em;color:gray;'>score {score}</span><br>"
                    f"<span style='font-size:0.9em;font-weight:600;'>{summary_short}</span><br>"
                    f"<span style='font-size:0.78em;color:gray;'>Why: {reasons_str}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(status)
                if st.button(
                    "✓ Selected" if selected else "Select",
                    key=f"card_{c_key}",
                    use_container_width=True,
                    type="primary" if selected else "secondary",
                ):
                    if st.session_state.selected_ticket_key != c_key:
                        st.session_state.selected_ticket_key = c_key
                        st.session_state.dev_status_data     = None
                        st.session_state.pr_diff_data        = None
                    st.rerun()

        red_count = int((df_scored["RiskBand"] == "RED").sum())
        if red_count >= 3:
            st.error(f"⚠️ RELEASE BLOCK — {red_count} critical issues require immediate attention.")

        # ---- Ticket Detail & PR Panel ----
        ticket_key = st.session_state.selected_ticket_key
        if ticket_key and ticket_key in display_df["Issue Key"].values:
            st.divider()

            # Traceability Badge
            has_creds = bool(st.session_state._jira_base_url and st.session_state._jira_token)
            cached    = st.session_state.traceability_cache.get(ticket_key)

            badge_col, fetch_col = st.columns([3, 1])
            with badge_col:
                if cached is True:
                    st.success(f"✅ **Traceability: LINKED** — `{ticket_key}` has PR(s)")
                elif cached is False:
                    st.error(f"🔴 **Traceability: MISSING** — `{ticket_key}` has no linked PR")
                else:
                    st.info(f"🔗 **`{ticket_key}` selected** — click Fetch to check PR linkage")

            with fetch_col:
                fetch_disabled = not has_creds
                if st.button("Fetch PR", key="fetch_dev_status", disabled=fetch_disabled,
                             help="Requires live Jira credentials" if fetch_disabled else ""):
                    with st.spinner(f"Checking dev-status for {ticket_key}..."):
                        try:
                            data = bridge.fetch_dev_status(
                                st.session_state._jira_base_url,
                                st.session_state._jira_email,
                                st.session_state._jira_token,
                                ticket_key,
                            )
                            st.session_state.dev_status_data = data
                            st.session_state.traceability_cache[ticket_key] = data["has_pr"]
                        except Exception as e:
                            st.error(f"Dev-status error: {e}")

            # Linked PRs section
            dev = st.session_state.dev_status_data
            if dev and dev.get("prs"):
                st.markdown("**Linked PRs**")
                for pr in dev["prs"]:
                    state_icon = "🟢" if pr["status"] in ("OPEN", "MERGED") else "🔵"
                    pr_line = f"{state_icon} [{pr['title'] or pr['url']}]({pr['url']})  `{pr['status']}`  by {pr['author']}"
                    st.markdown(pr_line)

                    # Auto-populate Column 2 with diff for the first PR
                    if (st.session_state.pr_diff_data is None
                            and pr.get("url")
                            and "github.com" in pr["url"]):
                        with st.spinner("Loading PR diff..."):
                            st.session_state.pr_diff_data = bridge.fetch_github_pr_diff(
                                pr["url"],
                                github_token=st.session_state._github_token,
                            )

            elif dev and not dev.get("prs"):
                st.warning("No pull requests found for this ticket.")

# ---------------------------------------------------------------------------
# Column 2: Environment Monitor
# ---------------------------------------------------------------------------

with col2:
    st.header("🌐 Environment Monitor")

    payload    = st.session_state.qa_payload
    collisions = st.session_state.collision_warnings
    not_dep    = st.session_state.not_yet_deployed

    env_tab, diff_tab, csv_tab = st.tabs(
        ["🚀 QA Payload", "🔍 PR Diff", "📂 Branch CSV"]
    )

    # ------------------------------------------------------------------ #
    # Tab 1 — QA Environment Payload                                       #
    # ------------------------------------------------------------------ #
    with env_tab:
        if not payload:
            st.info("No payload loaded. Click **🚀 Load QA Payload** in the sidebar "
                    "(Live mode) to scan merged PRs from the last 24 hours.")
        else:
            st.caption(f"**Current QA Environment Payload** — {len(payload)} merged PR(s)")
            payload_df = pd.DataFrame([{
                "Ticket":        p["ticket_key"],
                "Summary":       p["ticket_summary"][:50],
                "PR":            p["pr_title"][:40] or p["pr_url"],
                "Status":        p["pr_status"],
                "Author":        p["pr_author"],
                "Branch":        p["source_branch"],
                "Files":         len(p.get("files", [])),
            } for p in payload])
            st.dataframe(payload_df, use_container_width=True, height=220)

        # ---- Collision Warnings ----
        st.divider()
        if collisions:
            st.subheader(f"⚠️ Collision Warnings ({len(collisions)})")
            for c in collisions:
                tickets_str = ", ".join(f"`{t}`" for t in c["tickets"])
                authors_str = ", ".join(c.get("authors", []))
                with st.container(border=True):
                    if c["type"] == "FILE":
                        st.warning(
                            f"**File Collision** — `{c['location']}`\n\n"
                            f"Touched by: {tickets_str} (authors: {authors_str})\n\n"
                            f"*Recommend targeted regression testing on this file.*"
                        )
                    else:
                        st.warning(
                            f"**Module Collision** — `{c['location']}/`\n\n"
                            f"Multiple changes detected by: {tickets_str}\n\n"
                            f"*Recommend extra regression testing in this module.*"
                        )
        elif payload:
            st.success("✅ No collisions detected across merged PRs.")

        # ---- Not Yet Deployed ----
        st.divider()
        if not_dep:
            st.subheader(f"🚫 Not Yet Deployed ({len(not_dep)})")
            for item in not_dep:
                with st.container(border=True):
                    st.error(
                        f"**{item['ticket_key']}** — {item['summary']}\n\n"
                        f"Status: *Ready for QA* but PR is **{item['pr_status']}** (not merged)\n\n"
                        f"[{item['pr_title'] or item['pr_url']}]({item['pr_url']})\n\n"
                        f"⚠️ *Do not test — code has not been deployed.*"
                    )
        elif payload:
            st.success("✅ All Ready for QA tickets have merged PRs.")

    # ------------------------------------------------------------------ #
    # Tab 2 — PR Diff (auto-populated from Col 1 ticket selection)         #
    # ------------------------------------------------------------------ #
    with diff_tab:
        pr_diff = st.session_state.pr_diff_data
        if pr_diff is None:
            st.info("Select a ticket in Column 1 and click **Fetch PR** to load its diff here.")
        elif pr_diff.get("error"):
            st.warning(f"Diff unavailable: {pr_diff['error']}")
        else:
            st.caption(f"**{pr_diff.get('title', '')}** — `{pr_diff.get('state', '').upper()}`")
            m1, m2, m3 = st.columns(3)
            m1.metric("Changed Files", pr_diff.get("changed_files", 0))
            m2.metric("Additions",     f"+{pr_diff.get('additions', 0)}")
            m3.metric("Deletions",     f"-{pr_diff.get('deletions', 0)}")

            if pr_diff.get("files"):
                st.dataframe(pd.DataFrame(pr_diff["files"]),
                             use_container_width=True, height=180)

            if pr_diff.get("diff_summary"):
                with st.expander("View Raw Diff", expanded=False):
                    st.markdown(pr_diff["diff_summary"])

            if st.button("Clear Diff", key="clear_diff"):
                st.session_state.pr_diff_data = None
                st.rerun()

    # ------------------------------------------------------------------ #
    # Tab 3 — Branch CSV + PR Risk Flags (local/CSV mode)                  #
    # ------------------------------------------------------------------ #
    with csv_tab:
        git_df = st.session_state.git_df
        if git_df is None:
            st.info("Upload a Git branch CSV in the sidebar (Local mode).")
        else:
            st.dataframe(git_df, use_container_width=True, height=180)

            pr_risks = bridge.analyze_pr_risks(git_df)
            if pr_risks:
                st.subheader("🚨 PR Risk Flags")
                for risk in pr_risks:
                    is_critical = "MISSING TESTS" in risk["Flags"] and "LEGACY FILE RISK" in risk["Flags"]
                    with st.container(border=True):
                        if is_critical:
                            st.error(f"🔥 **HIGH RISK** — `{risk['Branch']}` by {risk['Author']}")
                        else:
                            st.warning(f"⚠️ **{risk['Severity']}** — `{risk['Branch']}` by {risk['Author']}")
                        st.markdown(f"**Flags:** `{risk['Flags']}`")
                        if risk["Legacy Files"]:
                            st.markdown("**Critical Files:** " + ", ".join(f"`{f}`" for f in risk["Legacy Files"]))
                        if risk["Missing Tests"]:
                            st.markdown("**Missing Tests:** No test files detected.")

            if st.session_state.jira_df is not None and "Branch" in git_df.columns:
                st.subheader("Branch Correlation")
                correlation = bridge.correlate_branches(st.session_state.jira_df, git_df)
                tab1, tab2, tab3 = st.tabs(["✅ Correlated", "🔴 Orphaned", "⚠️ Unlinked"])
                with tab1:
                    if correlation["correlated"]:
                        st.dataframe(pd.DataFrame(correlation["correlated"],
                                                   columns=["Jira Key", "Branch"]),
                                     use_container_width=True)
                    else:
                        st.warning("No correlated tickets found.")
                with tab2:
                    if correlation["orphaned_tickets"]:
                        st.dataframe(pd.DataFrame(correlation["orphaned_tickets"],
                                                   columns=["Orphaned Key"]),
                                     use_container_width=True)
                    else:
                        st.success("All tickets have branches.")
                with tab3:
                    if correlation["unlinked_branches"]:
                        st.dataframe(pd.DataFrame(correlation["unlinked_branches"],
                                                   columns=["Unlinked Branch"]),
                                     use_container_width=True)
                    else:
                        st.success("All branches are linked.")

# ---------------------------------------------------------------------------
# Column 3: QA-7 Agentic Chat
# ---------------------------------------------------------------------------

with col3:
    mcp_active = bool(st.session_state.mcp_server_params)
    st.header("🤖 QA-7" + (" ⚡ Agentic" if mcp_active else " Chat"))

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        st.info("Set `ANTHROPIC_API_KEY` in `.env` to activate QA-7.", icon="🔑")
    else:
        if mcp_active:
            st.caption(f"✅ Agentic mode — {len(st.session_state.mcp_tools_available)} MCP tools available")
        else:
            st.caption("✅ Chat mode — load live data to enable agentic tool use")

    # Chat history display
    chat_container = st.container(height=360)
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                if isinstance(msg["content"], str):
                    st.markdown(msg["content"])
                else:
                    # Render content blocks (tool calls etc.)
                    for block in msg["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            st.markdown(block["text"])
                        elif isinstance(block, dict) and block.get("type") == "tool_use":
                            st.markdown(f"*Calling tool: `{block['name']}`...*")

    def build_data_context() -> str:
        parts = []

        # Pod context — always injected so QA-7 knows who to ping
        pod_lines = "\n".join(f"- **{pod}** → {qa}" for pod, qa in POD_QA_MAP.items())
        active_pod_line = (
            f"Currently viewing pod: **{st.session_state.selected_pod}**"
            + (f" (Assigned QA: **{POD_QA_MAP.get(st.session_state.selected_pod, 'Unassigned')}**)"
               if st.session_state.selected_pod != "All Pods" else "")
        )
        active_status_line = (
            f"Active status filter: **{st.session_state.selected_status}**"
        )
        parts.append(
            f"## Pod Configuration\n"
            f"POD_FIELD_ID: `{POD_FIELD_ID}`\n\n"
            f"### Pod → QA Map\n{pod_lines}\n\n"
            f"### Active Filters\n{active_pod_line}\n{active_status_line}"
        )

        if st.session_state.jira_df is not None:
            df_s = bridge.compute_risk_scores(st.session_state.jira_df, st.session_state.git_df)
            if "Pod" in df_s.columns:
                df_s["Assigned QA"] = df_s["Pod"].map(POD_QA_MAP).fillna("Unassigned")
            else:
                qa_for_pod = POD_QA_MAP.get(st.session_state.selected_pod, "—") \
                             if st.session_state.selected_pod != "All Pods" else "—"
                df_s["Assigned QA"] = qa_for_pod
            parts.append("## Jira Data (Risk Scored)\n" + df_s.to_markdown(index=False))
        else:
            parts.append("## Jira\nNo data loaded.")

        if st.session_state.git_df is not None:
            parts.append("## Git Data\n" + st.session_state.git_df.to_markdown(index=False))
            risks = bridge.analyze_pr_risks(st.session_state.git_df)
            if risks:
                lines = [f"- `{r['Branch']}` ({r['Author']}): {r['Flags']}" +
                         (f" | Legacy: {', '.join(r['Legacy Files'])}" if r["Legacy Files"] else "")
                         for r in risks]
                parts.append("## PR Risk Flags\n" + "\n".join(lines))
            if st.session_state.jira_df is not None:
                c = bridge.correlate_branches(st.session_state.jira_df, st.session_state.git_df)
                parts.append(f"## Branch Correlation\n"
                              f"- Correlated: {c['correlated']}\n"
                              f"- Orphaned tickets: {c['orphaned_tickets']}\n"
                              f"- Unlinked branches: {c['unlinked_branches']}")
        else:
            parts.append("## Git\nNo data loaded.")

        if mcp_active:
            parts.append(f"## MCP Tools Available\n" +
                         "\n".join(f"- `{n}`" for n in sorted(st.session_state.mcp_tools_available)))

        # Release Audit context
        if st.session_state.qa_payload:
            payload_lines = "\n".join(
                f"- `{p['ticket_key']}` — {p['pr_title'] or p['pr_url']} "
                f"({p['pr_status']}, by {p['pr_author']}, files: {len(p.get('files', []))})"
                for p in st.session_state.qa_payload
            )
            parts.append(f"## QA Environment Payload (Merged PRs)\n{payload_lines}")

        if st.session_state.collision_warnings:
            col_lines = "\n".join(
                f"- **{c['type']} COLLISION** in `{c['location']}` — "
                f"tickets: {', '.join(c['tickets'])} | authors: {', '.join(c.get('authors', []))}"
                for c in st.session_state.collision_warnings
            )
            parts.append(f"## Collision Warnings\n{col_lines}")

        if st.session_state.not_yet_deployed:
            nd_lines = "\n".join(
                f"- `{n['ticket_key']}` — {n['summary']} | PR status: {n['pr_status']} (not merged)"
                for n in st.session_state.not_yet_deployed
            )
            parts.append(
                f"## Not Yet Deployed (Ready for QA but PR still OPEN)\n"
                f"These tickets MUST NOT be tested — code is not in the environment.\n{nd_lines}"
            )

        # Dev-status / Impact Analysis context
        if st.session_state.selected_ticket_key:
            parts.append(f"## Selected Ticket\n`{st.session_state.selected_ticket_key}`")

        dev = st.session_state.dev_status_data
        if dev:
            pr_list = "\n".join(
                f"- [{p['title'] or p['url']}]({p['url']}) — {p['status']} by {p['author']}"
                for p in dev.get("prs", [])
            ) or "None"
            parts.append(
                f"## Jira Ticket Description\n{dev.get('description', 'N/A')}\n\n"
                f"## Linked Pull Requests\n{pr_list}\n\n"
                f"## Traceability\n{'LINKED — PR found' if dev.get('has_pr') else 'MISSING — no PR found'}"
            )

        pr_diff = st.session_state.pr_diff_data
        if pr_diff and not pr_diff.get("error"):
            file_list = "\n".join(
                f"- `{f['filename']}` ({f['status']}, +{f['additions']}/-{f['deletions']})"
                for f in pr_diff.get("files", [])
            )
            parts.append(
                f"## PR Diff Summary\n"
                f"**Title:** {pr_diff.get('title', '')}\n"
                f"**State:** {pr_diff.get('state', '')}\n"
                f"**Description:** {pr_diff.get('body', '')}\n\n"
                f"**Files Changed ({pr_diff.get('changed_files', 0)}):**\n{file_list}\n\n"
                f"**Patch (truncated):**\n{pr_diff.get('diff_summary', '')[:3000]}"
            )

        return "\n\n---\n\n".join(parts)

    user_input = st.chat_input("Ask QA-7 anything... or 'Analyze ticket PROJ-101'")

    if user_input:
        if not anthropic_key:
            st.warning("QA-7 is offline. Set `ANTHROPIC_API_KEY` in `.env`.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            data_context = build_data_context()
            system = QA_SYSTEM_PROMPT + "\n\n---\n\n# LIVE DASHBOARD DATA\n\n" + data_context

            messages = []
            for m in st.session_state.chat_history:
                messages.append({"role": m["role"], "content": m["content"]})

            model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

            try:
                if mcp_active:
                    # --- AGENTIC MODE: tool-call loop ---
                    status_placeholder = st.empty()
                    tool_log = []

                    def on_tool_call(msg: str):
                        tool_log.append(msg)
                        status_placeholder.info("\n\n".join(tool_log))

                    with st.spinner("QA-7 working (agentic)..."):
                        reply, updated_messages = bridge.run_agentic_loop(
                            messages=messages,
                            system=system,
                            anthropic_key=anthropic_key,
                            model=model,
                            server_params_list=st.session_state.mcp_server_params,
                            status_callback=on_tool_call,
                        )
                    status_placeholder.empty()
                else:
                    # --- STANDARD CHAT MODE ---
                    import anthropic
                    client = anthropic.Anthropic(api_key=anthropic_key)
                    with st.spinner("QA-7 thinking..."):
                        response = client.messages.create(
                            model=model,
                            max_tokens=1024,
                            system=system,
                            messages=messages,
                        )
                        reply = response.content[0].text

                st.session_state.chat_history.append({"role": "assistant", "content": reply})
                st.rerun()

            except Exception as e:
                st.error(f"QA-7 error: {e}")

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
