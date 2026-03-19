const BASE = '/api'

export async function fetchProjects(demoMode = false) {
  const res = await fetch(`${BASE}/projects?demo_mode=${demoMode}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function loadFilters(projectKey, demoMode = false) {
  const res = await fetch(`${BASE}/filters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_key: projectKey, demo_mode: demoMode }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchTickets({ projectKey, tags, statuses, sprintIds, demoMode = false }) {
  const res = await fetch(`${BASE}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_key: projectKey,
      tags: tags || [],
      statuses: statuses || [],
      sprint_ids: sprintIds || [],
      demo_mode: demoMode,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchPRDiff(ticketKey, demoMode = false) {
  const res = await fetch(`${BASE}/pr-diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket_key: ticketKey, demo_mode: demoMode }),
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
