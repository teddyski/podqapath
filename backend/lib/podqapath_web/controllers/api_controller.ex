defmodule PodqapathWeb.ApiController do
  use PodqapathWeb, :controller

  alias Podqapath.{DemoData, RiskScorer, JiraClient, GithubClient}

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  defp is_demo?(req_demo_mode) do
    Application.get_env(:podqapath, :demo_mode, false) or req_demo_mode
  end

  defp jira_configured? do
    JiraClient.configured?()
  end

  # ---------------------------------------------------------------------------
  # OPTIONS — preflight handler
  # ---------------------------------------------------------------------------

  def options(conn, _params) do
    send_resp(conn, 204, "")
  end

  # ---------------------------------------------------------------------------
  # GET /api/health
  # ---------------------------------------------------------------------------

  def health(conn, _params) do
    json(conn, %{status: "ok", jira_configured: jira_configured?()})
  end

  # ---------------------------------------------------------------------------
  # GET /api/projects
  # ---------------------------------------------------------------------------

  def projects(conn, params) do
    demo_mode = Map.get(params, "demo_mode", false)

    if is_demo?(demo_mode) do
      json(conn, DemoData.projects())
    else
      unless jira_configured?() do
        conn |> put_status(503) |> json(%{error: "Jira credentials not configured"}) |> halt()
      else
        case JiraClient.fetch_projects() do
          {:ok, projects} -> json(conn, projects)
          {:error, reason} -> conn |> put_status(500) |> json(%{error: reason})
        end
      end
    end
  end

  # ---------------------------------------------------------------------------
  # POST /api/filters
  # ---------------------------------------------------------------------------

  def filters(conn, params) do
    demo_mode   = Map.get(params, "demo_mode", false)
    project_key = Map.get(params, "project_key", "SCRUM")

    if is_demo?(demo_mode) do
      json(conn, DemoData.filters())
    else
      unless jira_configured?() do
        conn |> put_status(503) |> json(%{error: "Jira credentials not configured"}) |> halt()
      else
        with {:ok, labels}   <- JiraClient.fetch_labels(project_key),
             {:ok, statuses} <- JiraClient.fetch_statuses(project_key),
             {:ok, sprints}  <- JiraClient.fetch_sprints(project_key) do
          json(conn, %{labels: labels, statuses: statuses, sprints: sprints})
        else
          {:error, reason} ->
            conn |> put_status(500) |> json(%{error: reason})
        end
      end
    end
  end

  # ---------------------------------------------------------------------------
  # POST /api/tickets
  # ---------------------------------------------------------------------------

  def tickets(conn, params) do
    demo_mode   = Map.get(params, "demo_mode", false)
    project_key = Map.get(params, "project_key", "SCRUM")
    tags        = Map.get(params, "tags", [])
    statuses    = Map.get(params, "statuses", [])
    sprint_ids  = Map.get(params, "sprint_ids", [])

    today = Date.utc_today()

    if is_demo?(demo_mode) do
      scored = RiskScorer.score_tickets(DemoData.tickets_raw(), today)
      json(conn, scored)
    else
      unless jira_configured?() do
        conn |> put_status(503) |> json(%{error: "Jira credentials not configured"}) |> halt()
      else
        opts = [tags: tags, statuses: statuses, sprint_ids: sprint_ids]

        case JiraClient.fetch_tickets(project_key, opts) do
          {:ok, raw_tickets} ->
            scored = RiskScorer.score_tickets(raw_tickets, today)
            json(conn, scored)

          {:error, reason} ->
            conn |> put_status(500) |> json(%{error: reason})
        end
      end
    end
  end

  # ---------------------------------------------------------------------------
  # POST /api/pr-diff
  # ---------------------------------------------------------------------------

  def pr_diff(conn, params) do
    demo_mode  = Map.get(params, "demo_mode", false)
    ticket_key = Map.get(params, "ticket_key", "")

    if is_demo?(demo_mode) do
      json(conn, DemoData.pr_data(ticket_key))
    else
      unless jira_configured?() do
        conn |> put_status(503) |> json(%{error: "Jira credentials not configured"}) |> halt()
      else
        case JiraClient.fetch_dev_status(ticket_key) do
          {:ok, %{prs: [], description: desc}} ->
            json(conn, %{prs: [], diff: nil, description: desc})

          {:ok, %{prs: prs, description: desc}} ->
            first_pr = List.first(prs)
            github_token = Application.get_env(:podqapath, :github_token, "")

            diff =
              if String.contains?(first_pr[:url] || "", "github.com") and github_token != "" do
                case GithubClient.fetch_pr_diff(first_pr[:url], github_token) do
                  {:ok, d}   -> d
                  {:error, _} -> nil
                end
              else
                nil
              end

            json(conn, %{prs: prs, diff: diff, description: desc})

          {:error, reason} ->
            conn |> put_status(500) |> json(%{error: reason})
        end
      end
    end
  end

  # ---------------------------------------------------------------------------
  # POST /api/chat
  # ---------------------------------------------------------------------------

  def chat(conn, params) do
    message      = Map.get(params, "message", "")
    history      = Map.get(params, "history", [])
    manager_mode = Map.get(params, "manager_mode", false)
    context      = Map.get(params, "context", "")

    api_key = Application.get_env(:podqapath, :anthropic_api_key, "")
    model   = Application.get_env(:podqapath, :anthropic_model, "claude-sonnet-4-6")

    if api_key == "" do
      conn |> put_status(503) |> json(%{error: "ANTHROPIC_API_KEY not configured"})
    else
      persona_file = if manager_mode, do: "QA_MANAGER.md", else: "QA_AGENT.md"
      persona_path = Path.join([__DIR__, "..", "..", "..", "..", "..", persona_file])

      system =
        case File.read(persona_path) do
          {:ok, content} -> content
          {:error, _}    -> "You are a QA assistant."
        end

      system =
        if context != "" do
          system <> "\n\n---\n\n# LIVE DASHBOARD DATA\n\n#{context}"
        else
          system
        end

      messages = history ++ [%{"role" => "user", "content" => message}]

      req =
        Req.new(
          base_url: "https://api.anthropic.com",
          headers: [
            {"x-api-key", api_key},
            {"anthropic-version", "2023-06-01"},
            {"content-type", "application/json"}
          ],
          receive_timeout: 60_000
        )

      body = %{
        model:      model,
        max_tokens: 1024,
        system:     system,
        messages:   messages
      }

      case Req.post(req, url: "/v1/messages", json: body) do
        {:ok, %{status: 200, body: resp_body}} ->
          text =
            resp_body
            |> Map.get("content", [])
            |> Enum.filter(&(Map.get(&1, "type") == "text"))
            |> Enum.map(&Map.get(&1, "text", ""))
            |> Enum.join("")

          json(conn, %{reply: text})

        {:ok, resp} ->
          conn
          |> put_status(500)
          |> json(%{error: "Anthropic API returned #{resp.status}"})

        {:error, reason} ->
          conn
          |> put_status(500)
          |> json(%{error: "Anthropic API error: #{inspect(reason)}"})
      end
    end
  end

  # ---------------------------------------------------------------------------
  # POST /api/run-tests  (SSE streaming)
  # ---------------------------------------------------------------------------

  def run_tests(conn, params) do
    repo_path = Map.get(params, "repo_path", "") |> String.trim()
    repo_url  = Map.get(params, "repo_url", "")  |> String.trim()
    base_url  = Map.get(params, "base_url", "http://localhost:3000") |> String.trim()

    conn =
      conn
      |> put_resp_header("content-type", "text/event-stream")
      |> put_resp_header("cache-control", "no-cache")
      |> put_resp_header("x-accel-buffering", "no")
      |> send_chunked(200)

    {work_dir, tmp_dir} =
      if repo_url != "" and repo_path == "" do
        tmp = System.tmp_dir!() |> Path.join("podqapath-#{:os.system_time(:millisecond)}")
        File.mkdir_p!(tmp)
        stream_event(conn, %{type: "output", text: "Cloning repository..."})

        case System.cmd("git", ["clone", "--depth=1", repo_url, tmp],
               stderr_to_stdout: true
             ) do
          {_, 0} -> {tmp, tmp}
          {msg, _} ->
            stream_event(conn, %{type: "error", message: "git clone failed: #{String.slice(msg, 0, 300)}"})
            File.rm_rf(tmp)
            {nil, nil}
        end
      else
        {repo_path, nil}
      end

    cond do
      is_nil(work_dir) ->
        conn

      work_dir == "" ->
        stream_event(conn, %{type: "error", message: "Provide a repo path or GitHub URL."})
        conn

      not File.exists?(work_dir) ->
        stream_event(conn, %{type: "error", message: "Path not found: #{work_dir}"})
        conn

      true ->
        run_playwright(conn, work_dir, tmp_dir, base_url)
    end
  end

  defp run_playwright(conn, work_dir, tmp_dir, base_url) do
    config_names = ["playwright.config.js", "playwright.config.ts", "playwright.config.mjs"]

    config_path =
      config_names
      |> Enum.find_value(fn name ->
        candidate = Path.join(work_dir, name)
        if File.exists?(candidate), do: candidate, else: nil
      end)
      |> then(fn direct ->
        if direct do
          direct
        else
          # Search recursively
          config_names
          |> Enum.flat_map(fn name -> Path.wildcard(Path.join([work_dir, "**", name])) end)
          |> List.first()
        end
      end)

    if is_nil(config_path) do
      stream_event(conn, %{type: "error", message: "No Playwright config found in repo."})
      cleanup(tmp_dir)
      conn
    else
      config_cwd = Path.dirname(config_path)
      rel_config = Path.relative_to(config_path, work_dir)
      stream_event(conn, %{type: "start", config: rel_config})

      conn = maybe_install_deps(conn, config_cwd)

      env =
        System.get_env()
        |> Map.put("PLAYWRIGHT_FORCE_TTY", "0")
        |> Map.put("CI", "1")
        |> then(fn e -> if base_url != "", do: Map.put(e, "BASE_URL", base_url), else: e end)

      pw_bin = Path.join([config_cwd, "node_modules", ".bin", "playwright"])

      conn = run_discovery(conn, pw_bin, config_path, config_cwd, env)
      conn = run_suite(conn, pw_bin, config_path, config_cwd, env)

      cleanup(tmp_dir)
      conn
    end
  end

  defp maybe_install_deps(conn, config_cwd) do
    node_modules = Path.join(config_cwd, "node_modules")

    if File.exists?(node_modules) do
      conn
    else
      stream_event(conn, %{type: "output", text: "Installing dependencies..."})

      case System.cmd("npm", ["install", "--prefer-offline"],
             cd: config_cwd,
             stderr_to_stdout: true
           ) do
        {_, 0} ->
          # Also install Playwright browsers
          pw_bin = Path.join([config_cwd, "node_modules", ".bin", "playwright"])
          System.cmd(pw_bin, ["install", "--with-deps"],
            cd: config_cwd,
            stderr_to_stdout: true
          )
          conn

        {_, _} ->
          stream_event(conn, %{type: "error", message: "npm install failed."})
          conn
      end
    end
  end

  defp run_discovery(conn, pw_bin, config_path, config_cwd, env) do
    # Phase 1: discover tests (non-fatal — failure is OK)
    env_list = Enum.map(env, fn {k, v} -> {k, v} end)

    try do
      case System.cmd(pw_bin, ["test", "--config", config_path, "--list"],
             cd: config_cwd,
             env: env_list,
             stderr_to_stdout: true
           ) do
        {output, _} ->
          output
          |> String.split("\n")
          |> Enum.each(fn line ->
            if title = parse_list_line(line) do
              stream_event(conn, %{type: "discovered", title: title})
            end
          end)

          conn
      end
    rescue
      _ -> conn
    end
  end

  defp run_suite(conn, pw_bin, config_path, config_cwd, env) do
    # Phase 2: run and stream results using Port for line-by-line output
    env_list = Enum.map(env, fn {k, v} -> {to_charlist(k), to_charlist(v)} end)

    port =
      Port.open(
        {:spawn_executable, pw_bin},
        [
          :binary,
          :exit_status,
          {:args, ["test", "--config", config_path, "--reporter=list"]},
          {:cd, config_cwd},
          {:env, env_list},
          :stderr_to_stdout,
          {:line, 4096}
        ]
      )

    {conn, passed, failed} = stream_port_output(conn, port, 0, 0)
    exit_code = receive_exit(port)

    stream_event(conn, %{type: "done", exit_code: exit_code, passed: passed, failed: failed})
    conn
  end

  defp stream_port_output(conn, port, passed, failed) do
    receive do
      {^port, {:data, {:eol, line}}} ->
        text = String.trim(line)

        {conn, passed, failed} =
          if text != "" do
            case parse_result_line(text) do
              {status, title, duration} when status in ["pass", "fail"] ->
                {p, f} =
                  if status == "pass",
                    do: {passed + 1, failed},
                    else: {passed, failed + 1}

                stream_event(conn, %{
                  type:     "result",
                  status:   status,
                  title:    title,
                  duration: duration
                })

                {conn, p, f}

              _ ->
                summary_re = ~r/(\d+)\s+passed/

                case Regex.run(summary_re, text) do
                  [_, p_str] ->
                    p = String.to_integer(p_str)
                    failed_re = ~r/(\d+)\s+failed/

                    f =
                      case Regex.run(failed_re, text) do
                        [_, f_str] -> String.to_integer(f_str)
                        _          -> 0
                      end

                    stream_event(conn, %{type: "summary", passed: p, failed: f})
                    {conn, passed, failed}

                  _ ->
                    stream_event(conn, %{type: "output", text: text})
                    {conn, passed, failed}
                end
            end
          else
            {conn, passed, failed}
          end

        stream_port_output(conn, port, passed, failed)

      {^port, {:exit_status, _}} ->
        {conn, passed, failed}
    after
      300_000 ->
        # 5 min timeout
        Port.close(port)
        stream_event(conn, %{type: "error", message: "Test run timed out after 5 minutes."})
        {conn, passed, failed}
    end
  end

  defp receive_exit(port) do
    receive do
      {^port, {:exit_status, code}} -> code
    after
      5_000 -> -1
    end
  end

  # ---------------------------------------------------------------------------
  # Playwright output parsers
  # ---------------------------------------------------------------------------

  defp parse_list_line(line) do
    stripped = String.trim_leading(line)

    if String.starts_with?(stripped, "[") do
      parts = String.split(stripped, " › ")

      if length(parts) >= 3 do
        parts |> Enum.drop(2) |> Enum.join(" › ") |> String.trim()
      else
        nil
      end
    else
      nil
    end
  end

  defp parse_result_line(text) do
    stripped = String.trim_leading(text)
    first_char = String.first(stripped) || ""

    status =
      cond do
        first_char in ["✓", "·"] -> "pass"
        first_char in ["✗", "×", "✘"] -> "fail"
        true -> nil
      end

    if status do
      rest = Regex.replace(~r/^[✓·✗×✘]\s+\d+\s+/, stripped, "")
      parts = String.split(rest, " › ")

      if length(parts) >= 3 do
        title_dur = parts |> Enum.drop(2) |> Enum.join(" › ")

        case Regex.run(~r/^(.+?)\s+\(([\d.]+s)\)\s*$/, title_dur) do
          [_, title, dur] -> {status, String.trim(title), dur}
          _               -> {status, String.trim(title_dur), ""}
        end
      else
        {nil, nil, nil}
      end
    else
      {nil, nil, nil}
    end
  end

  # ---------------------------------------------------------------------------
  # SSE helpers
  # ---------------------------------------------------------------------------

  defp stream_event(conn, data) do
    json_data = Jason.encode!(data)
    chunk(conn, "data: #{json_data}\n\n")
    conn
  end

  defp cleanup(nil), do: :ok
  defp cleanup(tmp_dir) do
    File.rm_rf(tmp_dir)
    :ok
  end
end
