defmodule Podqapath.GithubClient do
  @moduledoc """
  GitHub REST API v3 client using Req.
  Fetches PR metadata and file-level diff summaries.
  """

  @github_api "https://api.github.com"

  # ---------------------------------------------------------------------------
  # PR diff
  # ---------------------------------------------------------------------------

  @doc """
  Fetch file-level diff for a GitHub PR URL of the form
  `https://github.com/owner/repo/pull/123`.

  Returns a map matching the Python fetch_github_pr_diff() output.
  """
  def fetch_pr_diff(pr_url, github_token \\ nil) do
    token = github_token || Application.get_env(:podqapath, :github_token, "")

    case parse_github_url(pr_url) do
      {:error, _} = err ->
        err

      {:ok, {owner, repo, pr_number}} ->
        req = build_req(token)

        with {:ok, pr_data}    <- fetch_pr_meta(req, owner, repo, pr_number),
             {:ok, files_data} <- fetch_pr_files(req, owner, repo, pr_number) do
          {:ok, build_diff_result(pr_data, files_data)}
        end
    end
  end

  # ---------------------------------------------------------------------------
  # Private
  # ---------------------------------------------------------------------------

  defp parse_github_url(url) do
    pattern = ~r|https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)|

    case Regex.run(pattern, url) do
      [_, owner, repo, pr_number] -> {:ok, {owner, repo, pr_number}}
      _                           -> {:error, "Cannot parse GitHub URL: #{url}"}
    end
  end

  defp build_req(token) do
    headers = [{"accept", "application/vnd.github.v3+json"}]

    headers =
      if token && token != "" do
        [{"authorization", "Bearer #{token}"} | headers]
      else
        headers
      end

    Req.new(base_url: @github_api, headers: headers, receive_timeout: 10_000)
  end

  defp fetch_pr_meta(req, owner, repo, pr_number) do
    case Req.get(req, url: "/repos/#{owner}/#{repo}/pulls/#{pr_number}") do
      {:ok, %{status: 200, body: body}} -> {:ok, body}
      {:ok, resp}                       -> {:error, "PR fetch failed: #{resp.status}"}
      {:error, reason}                  -> {:error, inspect(reason)}
    end
  end

  defp fetch_pr_files(req, owner, repo, pr_number) do
    case Req.get(req, url: "/repos/#{owner}/#{repo}/pulls/#{pr_number}/files") do
      {:ok, %{status: 200, body: body}} -> {:ok, body}
      {:ok, resp}                       -> {:error, "PR files fetch failed: #{resp.status}"}
      {:error, reason}                  -> {:error, inspect(reason)}
    end
  end

  defp build_diff_result(pr_data, files_data) do
    files_limited = Enum.take(files_data, 25)

    {files, additions, deletions, diff_parts} =
      Enum.reduce(files_limited, {[], 0, 0, []}, fn file, {fs, adds, dels, parts} ->
        fname    = file["filename"] || ""
        fstatus  = file["status"]   || ""
        fadd     = file["additions"] || 0
        fdel     = file["deletions"] || 0
        patch    = file["patch"] || ""

        new_file = %{
          filename:  fname,
          status:    fstatus,
          additions: fadd,
          deletions: fdel
        }

        new_part =
          if patch != "" do
            truncated = String.slice(patch, 0, 600)
            "### #{fname}\n```diff\n#{truncated}\n```"
          else
            nil
          end

        parts = if new_part, do: [new_part | parts], else: parts
        {[new_file | fs], adds + fadd, dels + fdel, parts}
      end)

    diff_summary =
      diff_parts
      |> Enum.reverse()
      |> Enum.take(6)
      |> Enum.join("\n\n")

    %{
      title:         pr_data["title"] || "",
      body:          (pr_data["body"] || "") |> String.slice(0, 1000),
      state:         pr_data["state"] || "",
      changed_files: pr_data["changed_files"] || 0,
      additions:     additions,
      deletions:     deletions,
      files:         Enum.reverse(files),
      diff_summary:  diff_summary,
      error:         nil
    }
  end
end
