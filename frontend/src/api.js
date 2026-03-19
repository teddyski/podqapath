const BASE = '/api'

export async function loadFilters(projectKey) {
  const res = await fetch(`${BASE}/filters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_key: projectKey }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchTickets({ projectKey, tags, statuses, sprintIds }) {
  const res = await fetch(`${BASE}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_key: projectKey,
      tags: tags || [],
      statuses: statuses || [],
      sprint_ids: sprintIds || [],
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchPRDiff(ticketKey) {
  const res = await fetch(`${BASE}/pr-diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket_key: ticketKey }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function sendChat({ message, history, managerMode, context }) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      manager_mode: managerMode,
      context: context || '',
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
