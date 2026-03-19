defmodule Podqapath.DemoData do
  @moduledoc """
  Hardcoded demo data for offline / demo mode.
  Mirrors the Python mcp_bridge.py generate_sample_* functions.
  """

  @today ~D[2026-03-19]

  # ---------------------------------------------------------------------------
  # Filters
  # ---------------------------------------------------------------------------

  def projects do
    [
      %{key: "DEMO", name: "Demo Project"},
      %{key: "SCRUM", name: "SCRUM Board"}
    ]
  end

  def filters do
    %{
      labels: ["auth", "api", "regression", "sprint-critical", "needs-qa", "perf"],
      statuses: ["To Do", "In Progress", "In Review", "Ready for QA", "Done"],
      sprints: %{
        "Sprint 12 — Auth Hardening" => 42,
        "Sprint 13 — API Stability" => 43
      }
    }
  end

  # ---------------------------------------------------------------------------
  # Tickets  (raw, before risk scoring)
  # ---------------------------------------------------------------------------

  def tickets_raw do
    [
      %{
        "Issue Key"       => "DEMO-101",
        "Summary"         => "Auth middleware silently drops refresh tokens on mobile Safari",
        "Priority"        => "Critical",
        "Status"          => "In Progress",
        "Assignee"        => "Unassigned",
        "Issue Type"      => "Bug",
        "Component"       => "auth",
        "Days Open"       => 3,
        "FixVersionDate"  => "2026-03-20",
        "SprintEndDate"   => ""
      },
      %{
        "Issue Key"       => "DEMO-102",
        "Summary"         => "API rate limiter not applied to /v2/export endpoint",
        "Priority"        => "High",
        "Status"          => "In Progress",
        "Assignee"        => "priya.sharma",
        "Issue Type"      => "Bug",
        "Component"       => "api",
        "Days Open"       => 8,
        "FixVersionDate"  => "2026-04-01",
        "SprintEndDate"   => ""
      },
      %{
        "Issue Key"       => "DEMO-103",
        "Summary"         => "Update onboarding email sequence — new brand voice",
        "Priority"        => "Medium",
        "Status"          => "In Review",
        "Assignee"        => "carlos.mendes",
        "Issue Type"      => "Task",
        "Component"       => "messaging",
        "Days Open"       => 5,
        "FixVersionDate"  => "2026-04-07",
        "SprintEndDate"   => ""
      },
      %{
        "Issue Key"       => "DEMO-104",
        "Summary"         => "Add dark mode toggle to user settings panel",
        "Priority"        => "Low",
        "Status"          => "To Do",
        "Assignee"        => "hana.okonkwo",
        "Issue Type"      => "Story",
        "Component"       => "ui",
        "Days Open"       => 2,
        "FixVersionDate"  => "2026-05-15",
        "SprintEndDate"   => ""
      },
      %{
        "Issue Key"       => "DEMO-105",
        "Summary"         => "Migrate session token storage to HttpOnly cookies",
        "Priority"        => "High",
        "Status"          => "In Review",
        "Assignee"        => "alex.chen",
        "Issue Type"      => "Bug",
        "Component"       => "auth",
        "Days Open"       => 12,
        "FixVersionDate"  => "2026-03-20",
        "SprintEndDate"   => ""
      },
      %{
        "Issue Key"       => "DEMO-106",
        "Summary"         => "Webhook retry logic fails silently after 3 attempts",
        "Priority"        => "High",
        "Status"          => "Ready for QA",
        "Assignee"        => "priya.sharma",
        "Issue Type"      => "Bug",
        "Component"       => "api",
        "Days Open"       => 15,
        "FixVersionDate"  => "2026-03-25",
        "SprintEndDate"   => ""
      }
    ]
  end

  def today, do: @today

  # ---------------------------------------------------------------------------
  # PR / diff data
  # ---------------------------------------------------------------------------

  def pr_data("DEMO-101") do
    %{
      prs: [
        %{
          title:              "fix(auth): handle refresh token expiry on Safari mobile",
          url:                "https://github.com/acmecorp/platform/pull/847",
          status:             "OPEN",
          author:             "ghost-eng",
          source_branch:      "bugfix/DEMO-101-safari-refresh",
          destination_branch: "main",
          app_type:           "GitHub"
        }
      ],
      diff: %{
        title:         "fix(auth): handle refresh token expiry on Safari mobile",
        body:          "Fixes silent token drop on mobile Safari when ITP blocks third-party cookies.",
        state:         "open",
        changed_files: 3,
        additions:     87,
        deletions:     23,
        files: [
          %{filename: "src/auth/middleware.py",       status: "modified", additions: 45, deletions: 18},
          %{filename: "src/auth/token_store.py",      status: "modified", additions: 32, deletions: 5},
          %{filename: "src/utils/cookie_helpers.py",  status: "added",    additions: 10, deletions: 0}
        ],
        diff_summary: "--- a/src/auth/middleware.py\n+++ b/src/auth/middleware.py\n@@ -42,7 +42,12 @@\n-    if not token:\n-        return None\n+    if not token:\n+        # Safari ITP strips third-party cookies; fall back to HttpOnly session token\n+        token = request.cookies.get('_session_fallback')\n+        if not token:\n+            return None",
        error:         nil
      },
      description: "Auth middleware silently drops refresh tokens when Safari ITP blocks third-party cookie access. Affects ~12% of mobile users on iOS 17+."
    }
  end

  def pr_data("DEMO-102") do
    %{
      prs: [
        %{
          title:              "fix(api): enforce rate limit on /v2/export",
          url:                "https://github.com/acmecorp/platform/pull/851",
          status:             "OPEN",
          author:             "priya.sharma",
          source_branch:      "bugfix/DEMO-102-rate-limiter",
          destination_branch: "main",
          app_type:           "GitHub"
        }
      ],
      diff: %{
        title:         "fix(api): enforce rate limit on /v2/export",
        body:          "Applies the existing TokenBucketRateLimiter to the /v2/export route which was inadvertently excluded.",
        state:         "open",
        changed_files: 3,
        additions:     41,
        deletions:     8,
        files: [
          %{filename: "src/api/rate_limiter.py",    status: "modified", additions: 22, deletions: 5},
          %{filename: "src/api/export_handler.py",  status: "modified", additions: 14, deletions: 3},
          %{filename: "config/api_config.py",        status: "modified", additions: 5,  deletions: 0}
        ],
        diff_summary: "--- a/src/api/export_handler.py\n+++ b/src/api/export_handler.py\n@@ -18,6 +18,8 @@\n @router.get('/v2/export')\n+@rate_limiter.limit('100/hour')\n async def export_data(request: Request):\n",
        error:         nil
      },
      description: "The /v2/export endpoint bypasses the global rate limiter because it was registered after the middleware chain was finalized."
    }
  end

  def pr_data("DEMO-103") do
    %{
      prs:         [],
      diff:        nil,
      description: "Update all transactional onboarding emails to use the new Q2 brand voice guidelines. Affects welcome, day-3, and day-7 drip sequences."
    }
  end

  def pr_data("DEMO-104") do
    %{
      prs: [
        %{
          title:              "feat(ui): add dark mode toggle to settings",
          url:                "https://github.com/acmecorp/platform/pull/839",
          status:             "MERGED",
          author:             "hana.okonkwo",
          source_branch:      "feature/DEMO-104-dark-mode",
          destination_branch: "main",
          app_type:           "GitHub"
        }
      ],
      diff: %{
        title:         "feat(ui): add dark mode toggle to settings",
        body:          "Adds a system-preference-aware dark mode toggle. Preference is persisted in localStorage.",
        state:         "closed",
        changed_files: 2,
        additions:     58,
        deletions:     4,
        files: [
          %{filename: "ui/components/ThemeToggle.jsx", status: "added",    additions: 52, deletions: 0},
          %{filename: "ui/styles/theme.css",           status: "modified", additions: 6,  deletions: 4}
        ],
        diff_summary: "+// ThemeToggle.jsx\n+export function ThemeToggle() {\n+  const [dark, setDark] = useState(\n+    () => localStorage.getItem('theme') === 'dark'\n+  )\n",
        error:         nil
      },
      description: "Users have requested a dark mode option. The toggle should respect the system preference on first load and persist the user's override."
    }
  end

  def pr_data("DEMO-105") do
    %{
      prs: [
        %{
          title:              "fix(auth): migrate session tokens to HttpOnly cookies",
          url:                "https://github.com/acmecorp/platform/pull/849",
          status:             "OPEN",
          author:             "alex.chen",
          source_branch:      "bugfix/DEMO-105-httponly-cookies",
          destination_branch: "main",
          app_type:           "GitHub"
        }
      ],
      diff: %{
        title:         "fix(auth): migrate session tokens to HttpOnly cookies",
        body:          "Replaces localStorage-based session token with HttpOnly cookie to prevent XSS exfiltration.",
        state:         "open",
        changed_files: 3,
        additions:     112,
        deletions:     67,
        files: [
          %{filename: "src/auth/middleware.py",      status: "modified", additions: 55, deletions: 40},
          %{filename: "src/auth/session_store.py",   status: "modified", additions: 42, deletions: 27},
          %{filename: "migrations/0047_httponly.py", status: "added",    additions: 15, deletions: 0}
        ],
        diff_summary: "--- a/src/auth/middleware.py\n+++ b/src/auth/middleware.py\n@@ -10,5 +10,8 @@\n-    token = request.headers.get('X-Session-Token')\n+    token = request.cookies.get('session_id')  # HttpOnly; not accessible to JS\n+    if not token:\n+        raise AuthenticationError('Missing session cookie')\n",
        error:         nil
      },
      description: "Session tokens currently stored in localStorage are vulnerable to XSS. This PR moves them to HttpOnly cookies set by the server."
    }
  end

  def pr_data("DEMO-106") do
    %{
      prs: [
        %{
          title:              "fix(workers): add exponential backoff to webhook retry",
          url:                "https://github.com/acmecorp/platform/pull/852",
          status:             "OPEN",
          author:             "priya.sharma",
          source_branch:      "bugfix/DEMO-106-webhook-retry",
          destination_branch: "main",
          app_type:           "GitHub"
        }
      ],
      diff: %{
        title:         "fix(workers): add exponential backoff to webhook retry",
        body:          "After 3 failed attempts the worker silently marks the job done. This PR adds exponential backoff (max 5 attempts) and a dead-letter queue.",
        state:         "open",
        changed_files: 3,
        additions:     94,
        deletions:     31,
        files: [
          %{filename: "src/workers/webhook_retry.py", status: "modified", additions: 68, deletions: 25},
          %{filename: "src/workers/task_queue.py",    status: "modified", additions: 11, deletions: 6},
          %{filename: "tests/test_webhook.py",        status: "modified", additions: 15, deletions: 0}
        ],
        diff_summary: "--- a/src/workers/webhook_retry.py\n+++ b/src/workers/webhook_retry.py\n@@ -33,8 +33,14 @@\n-    if attempt >= 3:\n-        mark_done(job_id)\n+    if attempt >= MAX_ATTEMPTS:\n+        dead_letter_queue.push(job_id)\n+        logger.error('Webhook job %s exhausted retries', job_id)\n+        return\n+    delay = min(2 ** attempt, 300)  # cap at 5 minutes\n+    schedule_retry(job_id, delay_seconds=delay)\n",
        error:         nil
      },
      description: "Webhook delivery fails silently after 3 attempts with no logging, no dead-letter queue, and no alerting. Affects payment confirmation and third-party integrations."
    }
  end

  def pr_data(_key) do
    %{prs: [], diff: nil, description: ""}
  end
end
