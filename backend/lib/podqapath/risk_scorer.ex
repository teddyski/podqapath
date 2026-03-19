defmodule Podqapath.RiskScorer do
  @moduledoc """
  Computes risk scores for Jira tickets.
  Ported from mcp_bridge.py compute_risk_scores / helper functions.
  """

  @priority_scores %{
    "critical" => 30,
    "high"     => 20,
    "medium"   => 10,
    "low"      => 5,
    "unknown"  => 15
  }

  @doc """
  Given a list of ticket maps (with string keys), compute and append
  RiskScore, RiskBand, and RiskReasons to each ticket.
  Returns the enriched list.
  """
  def score_tickets(tickets, today \\ Date.utc_today()) do
    Enum.map(tickets, &score_ticket(&1, today))
  end

  defp score_ticket(ticket, today) do
    priority  = ticket["Priority"] || "Unknown"
    status    = ticket["Status"]   || ""
    assignee  = ticket["Assignee"] || ""
    issue_type = ticket["Issue Type"] || ""
    component  = ticket["Component"] || ""
    days_open  = ticket["Days Open"] || 0

    p = priority_score(priority)
    a = age_score(days_open)
    b = 12  # branch score unknown — no git data in this endpoint
    tc = type_component_score(issue_type, component)
    u = unassigned_score(assignee)

    days_until = days_until_release(ticket, today)
    r = release_proximity_score(days_until)

    # Status vs proximity boost: active work ≤2 days → extra push to RED
    r =
      if in_active_status?(status) and days_until != nil and days_until <= 2 do
        r + 10
      else
        r
      end

    raw_score = p + a + b + tc + u + r
    risk_score = raw_score |> max(0) |> min(100)
    risk_band  = score_to_band(risk_score)
    reasons    = build_reasons(priority, days_open, b, tc, u, days_until)

    ticket
    |> Map.put("RiskScore",   risk_score)
    |> Map.put("RiskBand",    risk_band)
    |> Map.put("RiskReasons", reasons)
  end

  # ---------------------------------------------------------------------------
  # Sub-scores
  # ---------------------------------------------------------------------------

  defp priority_score(priority) do
    Map.get(@priority_scores, String.downcase(priority), 15)
  end

  defp age_score(days) when days > 14, do: 20
  defp age_score(days) when days > 7,  do: 10
  defp age_score(_),                   do: 0

  defp type_component_score(issue_type, component) do
    is_bug  = String.contains?(String.downcase(issue_type), "bug")
    is_core = Regex.match?(~r/core|api/i, component)
    if is_bug and is_core, do: 15, else: 5
  end

  defp unassigned_score(assignee) do
    if String.contains?(String.downcase(assignee), "unassigned"), do: 10, else: 0
  end

  defp release_proximity_score(nil), do: 0
  defp release_proximity_score(days) when days <= 2,  do: 70
  defp release_proximity_score(days) when days <= 7,  do: 35
  defp release_proximity_score(days) when days <= 14, do: 20
  defp release_proximity_score(days) when days <= 21, do: 5
  defp release_proximity_score(_),                    do: 0

  defp in_active_status?(status) do
    Regex.match?(~r/in progress|in qa|in testing|in review/i, status)
  end

  # ---------------------------------------------------------------------------
  # Release date helpers
  # ---------------------------------------------------------------------------

  defp days_until_release(ticket, today) do
    candidates =
      [ticket["FixVersionDate"], ticket["SprintEndDate"]]
      |> Enum.reject(&(is_nil(&1) or &1 == ""))
      |> Enum.flat_map(fn ds ->
        case Date.from_iso8601(String.slice(ds, 0, 10)) do
          {:ok, d} -> [Date.diff(d, today)]
          _        -> []
        end
      end)

    if Enum.empty?(candidates), do: nil, else: Enum.min(candidates)
  end

  # ---------------------------------------------------------------------------
  # Risk band
  # ---------------------------------------------------------------------------

  def score_to_band(score) when score <= 30, do: "GREEN"
  def score_to_band(score) when score <= 60, do: "YELLOW"
  def score_to_band(score) when score <= 80, do: "ORANGE"
  def score_to_band(_),                      do: "RED"

  # ---------------------------------------------------------------------------
  # Risk reasons
  # ---------------------------------------------------------------------------

  defp build_reasons(priority, days_open, branch_score, type_comp, unassigned_score, days_until) do
    reasons = []

    reasons =
      case String.downcase(priority) do
        "critical" -> ["Critical priority" | reasons]
        "high"     -> ["High priority" | reasons]
        _          -> reasons
      end

    reasons =
      cond do
        days_open > 14 -> ["Open #{days_open} days" | reasons]
        days_open > 7  -> ["Open #{days_open} days" | reasons]
        true           -> reasons
      end

    reasons =
      cond do
        branch_score == 25 -> ["No linked branch" | reasons]
        branch_score == 12 -> ["Branch link unknown" | reasons]
        true               -> reasons
      end

    reasons = if type_comp == 15, do: ["Bug in core/API" | reasons], else: reasons
    reasons = if unassigned_score == 10, do: ["Unassigned" | reasons], else: reasons

    reasons =
      cond do
        days_until == nil    -> reasons
        days_until <= 0      -> ["Release overdue by #{abs(days_until)}d" | reasons]
        days_until == 1      -> ["1 day until release" | reasons]
        true                 -> ["#{days_until} days until release" | reasons]
      end

    Enum.reverse(reasons)
  end
end
