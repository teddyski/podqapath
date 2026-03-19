defmodule Podqapath.JiraClient do
  @moduledoc """
  Jira REST API client using Req.
  Covers: labels, statuses, sprints, ticket search, dev-status (PR links).
  """

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  defp base_req(base_url, email, token) do
    Req.new(
      base_url: String.trim_trailing(base_url, "/"),
      auth: {:basic, "#{email}:#{token}"},
      headers: [{"accept", "application/json"}],
      receive_timeout: 15_000
    )
  end

  defp jira_cfg do
    %{
      base_url: Application.get_env(:podqapath, :jira_base_url, ""),
      email:    Application.get_env(:podqapath, :jira_email, ""),
      token:    Application.get_env(:podqapath, :jira_api_token, "")
    }
  end

  def configured? do
    cfg = jira_cfg()
    Enum.all?([cfg.base_url, cfg.email, cfg.token], &(String.length(&1) > 0))
  end

  # ---------------------------------------------------------------------------
  # Projects
  # ---------------------------------------------------------------------------

  def fetch_projects do
    cfg = jira_cfg()
    req = base_req(cfg.base_url, cfg.email, cfg.token)

    case Req.get(req, url: "/rest/api/3/project", params: [maxResults: 100]) do
      {:ok, %{status: 200, body: body}} ->
        projects =
          body
          |> Enum.map(fn p -> %{key: p["key"], name: p["name"]} end)
          |> Enum.sort_by(& &1.name)

        {:ok, projects}

      {:ok, resp} ->
        {:error, "Project fetch failed: #{resp.status}"}

      {:error, reason} ->
        {:error, "Project fetch error: #{inspect(reason)}"}
    end
  end

  # ---------------------------------------------------------------------------
  # Labels
  # ---------------------------------------------------------------------------

  def fetch_labels(project_key) do
    cfg = jira_cfg()
    req = base_req(cfg.base_url, cfg.email, cfg.token)

    case Req.post(req,
           url: "/rest/api/3/search/jql",
           json: %{
             jql:        "project = #{project_key} AND labels is not EMPTY",
             maxResults: 100,
             fields:     ["labels"]
           }
         ) do
      {:ok, %{status: 200, body: body}} ->
        labels =
          body
          |> Map.get("issues", [])
          |> Enum.flat_map(fn issue ->
            issue |> get_in(["fields", "labels"]) || []
          end)
          |> Enum.uniq()
          |> Enum.sort()

        {:ok, labels}

      {:ok, resp} ->
        {:error, "Jira labels request failed: #{resp.status}"}

      {:error, reason} ->
        {:error, "Jira labels request error: #{inspect(reason)}"}
    end
  end

  # ---------------------------------------------------------------------------
  # Statuses
  # ---------------------------------------------------------------------------

  def fetch_statuses(project_key) do
    cfg = jira_cfg()
    req = base_req(cfg.base_url, cfg.email, cfg.token)

    case Req.get(req, url: "/rest/api/3/project/#{project_key}/statuses") do
      {:ok, %{status: 200, body: body}} ->
        statuses =
          body
          |> Enum.flat_map(fn issue_type ->
            issue_type |> Map.get("statuses", []) |> Enum.map(&Map.get(&1, "name", ""))
          end)
          |> Enum.reject(&(&1 == ""))
          |> Enum.uniq()
          |> Enum.sort()

        {:ok, statuses}

      {:ok, resp} ->
        {:error, "Jira statuses request failed: #{resp.status}"}

      {:error, reason} ->
        {:error, "Jira statuses request error: #{inspect(reason)}"}
    end
  end

  # ---------------------------------------------------------------------------
  # Sprints
  # ---------------------------------------------------------------------------

  def fetch_sprints(project_key) do
    cfg = jira_cfg()
    req = base_req(cfg.base_url, cfg.email, cfg.token)

    with {:ok, board_id} <- fetch_first_board_id(req, project_key),
         {:ok, sprints}  <- paginate_sprints(req, board_id) do
      {:ok, sprints}
    end
  end

  defp fetch_first_board_id(req, project_key) do
    case Req.get(req,
           url:    "/rest/agile/1.0/board",
           params: [projectKeyOrId: project_key]
         ) do
      {:ok, %{status: 200, body: %{"values" => [board | _]}}} ->
        {:ok, board["id"]}

      {:ok, %{status: 200}} ->
        {:error, "No boards found for project #{project_key}"}

      {:ok, resp} ->
        {:error, "Board fetch failed: #{resp.status}"}

      {:error, reason} ->
        {:error, inspect(reason)}
    end
  end

  defp paginate_sprints(req, board_id, start \\ 0, acc \\ %{}) do
    case Req.get(req,
           url:    "/rest/agile/1.0/board/#{board_id}/sprint",
           params: [startAt: start, maxResults: 50]
         ) do
      {:ok, %{status: 200, body: body}} ->
        new_sprints =
          body
          |> Map.get("values", [])
          |> Enum.reduce(%{}, fn sprint, m ->
            name = sprint["name"]
            id   = sprint["id"]
            if name && id, do: Map.put(m, name, id), else: m
          end)

        merged = Map.merge(acc, new_sprints)

        if body["isLast"] == true or map_size(new_sprints) == 0 do
          {:ok, merged}
        else
          paginate_sprints(req, board_id, start + 50, merged)
        end

      {:ok, resp} ->
        {:error, "Sprint fetch failed: #{resp.status}"}

      {:error, reason} ->
        {:error, inspect(reason)}
    end
  end

  # ---------------------------------------------------------------------------
  # Ticket search
  # ---------------------------------------------------------------------------

  @fields ["summary", "priority", "status", "assignee", "issuetype",
           "components", "created", "fixVersions", "customfield_10020"]

  def fetch_tickets(project_key, opts \\ []) do
    cfg = jira_cfg()
    req = base_req(cfg.base_url, cfg.email, cfg.token)

    jql = build_jql(project_key, opts)

    case Req.post(req,
           url:  "/rest/api/3/search/jql",
           json: %{jql: jql, maxResults: 100, fields: @fields}
         ) do
      {:ok, %{status: 200, body: body}} ->
        tickets =
          body
          |> Map.get("issues", [])
          |> Enum.map(&normalize_issue/1)

        {:ok, tickets}

      {:ok, resp} ->
        {:error, "Ticket search failed: #{resp.status}"}

      {:error, reason} ->
        {:error, inspect(reason)}
    end
  end

  defp build_jql(project_key, opts) do
    parts = ["project = #{project_key}"]

    parts =
      case Keyword.get(opts, :tags, []) do
        [] -> parts
        tags ->
          tags_jql = tags |> Enum.map(&~s("#{&1}")) |> Enum.join(", ")
          parts ++ ["labels in (#{tags_jql})"]
      end

    parts =
      case Keyword.get(opts, :statuses, []) do
        [] -> parts
        statuses ->
          s_jql = statuses |> Enum.map(&~s("#{&1}")) |> Enum.join(", ")
          parts ++ ["status in (#{s_jql})"]
      end

    parts =
      case Keyword.get(opts, :sprint_ids, []) do
        [] -> parts
        ids ->
          id_jql = ids |> Enum.map(&to_string/1) |> Enum.join(", ")
          parts ++ ["sprint in (#{id_jql})"]
      end

    (parts |> Enum.join(" AND ")) <> " ORDER BY created DESC"
  end

  defp normalize_issue(issue) do
    f = issue["fields"] || %{}

    %{
      "Issue Key"      => issue["key"] || "UNKNOWN",
      "Summary"        => f["summary"] || "",
      "Priority"       => (f["priority"] || %{}) |> Map.get("name", "Unknown"),
      "Status"         => (f["status"]   || %{}) |> Map.get("name", "Unknown"),
      "Assignee"       => (f["assignee"] || %{}) |> Map.get("displayName", "Unassigned"),
      "Issue Type"     => (f["issuetype"] || %{}) |> Map.get("name", "Unknown"),
      "Component"      => (f["components"] || []) |> Enum.map(&Map.get(&1, "name", "")) |> Enum.join(", ") |> then(fn s -> if s == "", do: "None", else: s end),
      "Days Open"      => days_since(f["created"]),
      "FixVersionDate" => nearest_fix_version_date(f["fixVersions"] || []),
      "SprintEndDate"  => parse_sprint_end_date(f["customfield_10020"])
    }
  end

  defp days_since(nil), do: 0
  defp days_since(""), do: 0
  defp days_since(iso_str) do
    case DateTime.from_iso8601(String.replace(iso_str, "Z", "+00:00")) do
      {:ok, dt, _} ->
        DateTime.diff(DateTime.utc_now(), dt, :second) |> div(86_400)
      _ ->
        0
    end
  end

  defp nearest_fix_version_date([]), do: ""
  defp nearest_fix_version_date(fix_versions) do
    fix_versions
    |> Enum.flat_map(fn v ->
      case v["releaseDate"] do
        nil -> []
        rd  ->
          case Date.from_iso8601(String.slice(rd, 0, 10)) do
            {:ok, d} -> [d]
            _        -> []
          end
      end
    end)
    |> case do
      []    -> ""
      dates -> dates |> Enum.min(Date) |> Date.to_iso8601()
    end
  end

  defp parse_sprint_end_date(nil), do: ""
  defp parse_sprint_end_date(sprint_field) when is_list(sprint_field) do
    sprint_field |> Enum.find_value("", &extract_end_date/1)
  end
  defp parse_sprint_end_date(sprint_field), do: extract_end_date(sprint_field)

  defp extract_end_date(%{"endDate" => end_date}) when is_binary(end_date) and end_date != "" do
    String.slice(end_date, 0, 10)
  end
  defp extract_end_date(sprint) when is_binary(sprint) do
    case Regex.run(~r/endDate=([^,\]\s]+)/, sprint) do
      [_, date] -> String.slice(date, 0, 10)
      _         -> ""
    end
  end
  defp extract_end_date(_), do: ""

  # ---------------------------------------------------------------------------
  # Dev status (PR links per ticket)
  # ---------------------------------------------------------------------------

  def fetch_dev_status(issue_key) do
    cfg = jira_cfg()
    req = base_req(cfg.base_url, cfg.email, cfg.token)

    with {:ok, {issue_id, description}} <- fetch_issue_meta(req, issue_key),
         {:ok, pr_count}                <- fetch_pr_count(req, issue_id) do
      if pr_count == 0 do
        {:ok, %{prs: [], description: description}}
      else
        prs = collect_prs(req, issue_id)
        {:ok, %{prs: prs, description: description}}
      end
    end
  end

  defp fetch_issue_meta(req, issue_key) do
    case Req.get(req,
           url:    "/rest/api/3/issue/#{issue_key}",
           params: [fields: "id,summary,description"]
         ) do
      {:ok, %{status: 200, body: body}} ->
        issue_id    = body["id"]
        description = body |> get_in(["fields", "description"]) |> extract_adf()
        {:ok, {issue_id, description}}

      {:ok, resp} ->
        {:error, "Issue fetch failed: #{resp.status}"}

      {:error, reason} ->
        {:error, inspect(reason)}
    end
  end

  defp fetch_pr_count(req, issue_id) do
    case Req.get(req,
           url:    "/rest/dev-status/1.0/issue/summary",
           params: [issueId: issue_id]
         ) do
      {:ok, %{status: 200, body: body}} ->
        count =
          body
          |> get_in(["summary", "pullrequest", "overall", "count"]) || 0

        {:ok, count}

      {:ok, _} -> {:ok, 0}
      {:error, reason} -> {:error, inspect(reason)}
    end
  end

  defp collect_prs(req, issue_id) do
    app_types = ["GitHub", "GitHub Enterprise", "Bitbucket", "GitLab"]

    Enum.flat_map(app_types, fn app_type ->
      case Req.get(req,
             url: "/rest/dev-status/1.0/issue/detail",
             params: [issueId: issue_id, applicationType: app_type, dataType: "pullrequest"]
           ) do
        {:ok, %{status: 200, body: body}} ->
          body
          |> Map.get("detail", [])
          |> Enum.flat_map(fn repo ->
            repo |> Map.get("pullRequests", []) |> Enum.map(&normalize_pr(&1, app_type))
          end)

        _ -> []
      end
    end)
  end

  defp normalize_pr(pr, app_type) do
    src = pr["source"] || %{}
    dst = pr["destination"] || %{}

    src_branch =
      case src["branch"] do
        b when is_binary(b) -> b
        b when is_map(b)    -> b["name"] || ""
        _                   -> ""
      end

    dst_branch =
      case dst["branch"] do
        b when is_binary(b) -> b
        b when is_map(b)    -> b["name"] || ""
        _                   -> ""
      end

    %{
      title:              pr["name"] || "",
      url:                pr["url"] || "",
      status:             pr["status"] || "UNKNOWN",
      author:             (pr["author"] || %{}) |> Map.get("name", ""),
      source_branch:      src_branch,
      destination_branch: dst_branch,
      app_type:           app_type
    }
  end

  # ---------------------------------------------------------------------------
  # ADF (Atlassian Document Format) flattener
  # ---------------------------------------------------------------------------

  defp extract_adf(nil), do: ""
  defp extract_adf(text) when is_binary(text), do: text
  defp extract_adf(adf) when is_map(adf) or is_list(adf) do
    adf |> walk_adf([]) |> Enum.join(" ") |> String.trim()
  end

  defp walk_adf(%{"type" => "text", "text" => text}, acc), do: [text | acc]
  defp walk_adf(%{"content" => children} = node, acc) when is_list(children) do
    child_acc =
      Enum.reduce(children, [], fn child, a -> walk_adf(child, a) end)
    _ = node
    child_acc ++ acc
  end
  defp walk_adf(list, acc) when is_list(list) do
    Enum.reduce(list, acc, fn item, a -> walk_adf(item, a) end)
  end
  defp walk_adf(_, acc), do: acc
end
