import { useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import TicketList from './components/TicketList'
import PRDiffViewer from './components/PRDiffViewer'
import TestRunner from './components/TestRunner'
import ChatPanel from './components/ChatPanel'
import { loadFilters, fetchTickets, fetchPRDiff } from './api'

export default function App() {
  const [projectKey, setProjectKey] = useState(
    import.meta.env.VITE_PROJECT_KEY || ''
  )
  const [filters, setFilters] = useState({ labels: [], statuses: [], sprints: {} })
  const [activeFilters, setActiveFilters] = useState({ tags: [], statuses: [], sprintIds: [] })
  const [tickets, setTickets] = useState([])
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [ticketError, setTicketError] = useState('')
  const [selectedTicket, setSelectedTicket] = useState(null)
  const [prData, setPrData] = useState(null)
  const [loadingPR, setLoadingPR] = useState(false)
  const [demoMode, setDemoMode] = useState(false)
  const [testResults, setTestResults] = useState('')
  const [showTestRunner, setShowTestRunner] = useState(false)

  const handleFetchTickets = useCallback(async () => {
    setLoadingTickets(true)
    setTicketError('')
    try {
      const data = await fetchTickets({
        projectKey,
        tags: activeFilters.tags,
        statuses: activeFilters.statuses,
        sprintIds: activeFilters.sprintIds,
        demoMode,
      })
      setTickets(data)
    } catch (e) {
      setTicketError(e.message)
    } finally {
      setLoadingTickets(false)
    }
  }, [projectKey, activeFilters, demoMode])

  const handleSelectTicket = useCallback(async (ticket) => {
    setSelectedTicket(ticket)
    setPrData(null)
    setLoadingPR(true)
    try {
      const data = await fetchPRDiff(ticket['Issue Key'], demoMode)
      setPrData(data)
    } catch (e) {
      setPrData({ error: e.message })
    } finally {
      setLoadingPR(false)
    }
  }, [demoMode])

  const handleTestTicket = useCallback((ticket) => {
    if (ticket['Issue Key'] === selectedTicket?.['Issue Key']) {
      // Already selected — just toggle the runner panel
      setShowTestRunner(v => !v)
    } else {
      // New ticket — select it (loads PR) and show the runner when ready
      handleSelectTicket(ticket)
      setShowTestRunner(true)
    }
  }, [selectedTicket, handleSelectTicket])

  const handleLoadDemo = useCallback(async () => {
    setDemoMode(true)
    setTicketError('')
    try {
      const filterData = await loadFilters('DEMO', true)
      setFilters(filterData)
      setActiveFilters({ tags: [], statuses: [], sprintIds: [] })
      setSelectedTicket(null)
      setPrData(null)
    } catch (e) {
      setTicketError(e.message)
      return
    }
    setLoadingTickets(true)
    try {
      const data = await fetchTickets({ projectKey: 'DEMO', demoMode: true })
      setTickets(data)
    } catch (e) {
      setTicketError(e.message)
    } finally {
      setLoadingTickets(false)
    }
  }, [])

  // Build context string for QA-7
  const chatContext = (() => {
    const parts = []

    if (tickets.length) {
      parts.push(
        `## Loaded Tickets (${tickets.length} total, project: ${projectKey})\n` +
        tickets.map(t =>
          `- ${t['Issue Key']} [${t.RiskBand} score:${t.RiskScore}] ${t.Summary} — ${t.Status} | ${t.Priority} | ${t.Assignee}`
        ).join('\n')
      )
    }

    if (selectedTicket) {
      const t = selectedTicket
      parts.push(
        `## Currently Selected Ticket\n` +
        `Key: ${t['Issue Key']}\n` +
        `Summary: ${t.Summary}\n` +
        `Status: ${t.Status}\n` +
        `Priority: ${t.Priority}\n` +
        `Assignee: ${t.Assignee}\n` +
        `Risk Band: ${t.RiskBand} (score ${t.RiskScore})\n` +
        `Risk Reasons: ${(t.RiskReasons || []).join(', ')}`
      )
    }

    if (prData && !prData.error) {
      if (prData.prs && prData.prs.length > 0) {
        const pr = prData.prs[0]
        parts.push(
          `## Linked PR\n` +
          `Title: ${pr.title}\n` +
          `Status: ${pr.status}\n` +
          `Author: ${pr.author}\n` +
          `URL: ${pr.url}`
        )
      }
      if (prData.diff && !prData.diff.error) {
        const d = prData.diff
        parts.push(
          `## PR Diff Summary\n` +
          `Changed files: ${d.changed_files} | Additions: +${d.additions} | Deletions: -${d.deletions}\n` +
          `Files:\n` +
          (d.files || []).map(f => `  ${f.status} ${f.filename} (+${f.additions} -${f.deletions})`).join('\n')
        )
        if (d.diff_summary) {
          parts.push(`## Raw Diff (truncated)\n${d.diff_summary.slice(0, 2000)}`)
        }
      }
      if (prData.description) {
        parts.push(`## Ticket Description\n${prData.description}`)
      }
    }

    if (testResults) {
      parts.push(`## Latest Test Run\n${testResults}`)
    }

    return parts.join('\n\n')
  })()

  // Extract GitHub repo base URL from loaded PR data for TestRunner auto-fill
  const autoFillUrl = (() => {
    const prUrl = prData?.prs?.[0]?.url || ''
    const m = prUrl.match(/^(https:\/\/github\.com\/[^/]+\/[^/]+)/)
    return m ? m[1] : ''
  })()

  return (
    <div className="app" data-testid="app">
      <Sidebar
        projectKey={projectKey}
        onProjectKeyChange={setProjectKey}
        filters={filters}
        onFiltersLoaded={setFilters}
        activeFilters={activeFilters}
        onActiveFiltersChange={setActiveFilters}
        onFetchTickets={handleFetchTickets}
        onLoadDemo={handleLoadDemo}
        loading={loadingTickets}
      />
      <main className="main-grid">
        <section className="col col-tickets">
          <h2>🎫 Jira Tickets</h2>
          {ticketError && <div className="error-banner">{ticketError}</div>}
          <TicketList
            tickets={tickets}
            loading={loadingTickets}
            selectedKey={selectedTicket?.['Issue Key']}
            loadingPR={loadingPR}
            onSelect={handleSelectTicket}
            onTest={handleTestTicket}
          />
        </section>
        <section className="col col-diff">
          <h2>🔍 Code Change Viewer</h2>
          <div style={{ order: showTestRunner ? 1 : 0 }}>
            <PRDiffViewer
              ticket={selectedTicket}
              data={prData}
              loading={loadingPR}
            />
          </div>
          <div style={{ order: showTestRunner ? 0 : 1 }}>
            <TestRunner
              autoFillUrl={autoFillUrl}
              onResultsUpdate={setTestResults}
            />
          </div>
        </section>
        <section className="col col-chat">
          <h2>🤖 QA-7</h2>
          <ChatPanel context={chatContext} />
        </section>
      </main>
    </div>
  )
}
