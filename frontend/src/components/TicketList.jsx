const BAND_COLOR = { RED: '#ff4b4b', ORANGE: '#ff8c00', YELLOW: '#ffd700', GREEN: '#21c354' }
const BAND_EMOJI = { RED: '🔴', ORANGE: '🟠', YELLOW: '🟡', GREEN: '🟢' }

export default function TicketList({ tickets, loading, selectedKey, loadingPR, onSelect, onTest }) {
  if (loading) return <div className="state-msg">Loading tickets…</div>
  if (!tickets.length) return (
    <div className="state-msg">
      No tickets loaded. Connect to Jira and click <strong>Fetch Live Data</strong>.
    </div>
  )

  return (
    <div className="ticket-list" data-testid="ticket-list">
      {tickets.map(t => {
        const key = t['Issue Key']
        const band = t.RiskBand || 'GREEN'
        const color = BAND_COLOR[band] || '#21c354'
        const reasons = Array.isArray(t.RiskReasons) ? t.RiskReasons : []
        const isSelected = key === selectedKey
        const testDisabled = isSelected && loadingPR

        return (
          <div
            key={key}
            className={`ticket-card ${isSelected ? 'ticket-card-selected' : ''}`}
            style={{ borderLeft: `4px solid ${color}` }}
            data-testid={`ticket-card-${key}`}
          >
            <div className="ticket-card-header">
              <span className="ticket-band-emoji">{BAND_EMOJI[band]}</span>
              <span className="ticket-key">{key}</span>
              <span className="ticket-score">score {t.RiskScore}</span>
            </div>
            <div className="ticket-summary">{t.Summary}</div>
            <div className="ticket-meta">
              <span className="ticket-status">{t.Status}</span>
              {t.Priority && <span className="ticket-priority">{t.Priority}</span>}
            </div>
            {reasons.length > 0 && (
              <div className="ticket-reasons">Why: {reasons.join(' · ')}</div>
            )}
            <div className="ticket-actions">
              <button
                className={`btn ${isSelected ? 'btn-primary' : 'btn-ghost'} ticket-select-btn`}
                onClick={() => onSelect(t)}
                data-testid={`ticket-select-btn-${key}`}
              >
                {isSelected ? '✓ Selected' : 'Select'}
              </button>
              <button
                className="btn btn-ghost ticket-test-btn"
                onClick={() => onTest(t)}
                disabled={testDisabled}
                data-testid={`ticket-test-btn-${key}`}
                title={testDisabled ? 'Loading PR…' : 'Show test runner'}
              >
                {testDisabled ? '⏳' : '▶ Test'}
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
