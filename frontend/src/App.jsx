import { useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import TicketList from './components/TicketList'
import PRDiffViewer from './components/PRDiffViewer'
import ChatPanel from './components/ChatPanel'
import { fetchTickets, fetchPRDiff } from './api'

export default function App() {
  const [projectKey, setProjectKey] = useState(
    import.meta.env.VITE_PROJECT_KEY || 'SCRUM'
  )
  const [filters, setFilters] = useState({ labels: [], statuses: [], sprints: {} })
  const [activeFilters, setActiveFilters] = useState({ tags: [], statuses: [], sprintIds: [] })
  const [tickets, setTickets] = useState([])
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [ticketError, setTicketError] = useState('')
  const [selectedTicket, setSelectedTicket] = useState(null)
  const [prData, setPrData] = useState(null)
  const [loadingPR, setLoadingPR] = useState(false)

  const handleFetchTickets = useCallback(async () => {
    setLoadingTickets(true)
    setTicketError('')
    try {
      const data = await fetchTickets({
        projectKey,
        tags: activeFilters.tags,
        statuses: activeFilters.statuses,
        sprintIds: activeFilters.sprintIds,
      })
      setTickets(data)
    } catch (e) {
      setTicketError(e.message)
    } finally {
      setLoadingTickets(false)
    }
  }, [projectKey, activeFilters])

  const handleSelectTicket = useCallback(async (ticket) => {
    setSelectedTicket(ticket)
    setPrData(null)
    setLoadingPR(true)
    try {
      const data = await fetchPRDiff(ticket['Issue Key'])
      setPrData(data)
    } catch (e) {
      setPrData({ error: e.message })
    } finally {
      setLoadingPR(false)
    }
  }, [])

  // Build context string for QA-7
  const chatContext = tickets.length
    ? `Project: ${projectKey}\nTicket count: ${tickets.length}\n` +
      tickets.slice(0, 10).map(t =>
        `${t['Issue Key']} [${t.RiskBand}] ${t.Summary} — ${t.Status}`
      ).join('\n')
    : ''

  return (
    <div className="app">
      <Sidebar
        projectKey={projectKey}
        onProjectKeyChange={setProjectKey}
        filters={filters}
        onFiltersLoaded={setFilters}
        activeFilters={activeFilters}
        onActiveFiltersChange={setActiveFilters}
        onFetchTickets={handleFetchTickets}
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
            onSelect={handleSelectTicket}
          />
        </section>
        <section className="col col-diff">
          <h2>🔍 Code Change Viewer</h2>
          <PRDiffViewer
            ticket={selectedTicket}
            data={prData}
            loading={loadingPR}
          />
        </section>
        <section className="col col-chat">
          <h2>🤖 QA-7</h2>
          <ChatPanel context={chatContext} />
        </section>
      </main>
    </div>
  )
}
