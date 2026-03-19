import { useState } from 'react'

export default function PRDiffViewer({ ticket, data, loading }) {
  const [diffOpen, setDiffOpen] = useState(false)

  if (!ticket) return (
    <div className="state-msg" data-testid="pr-viewer-empty">Select a ticket to view its PR diff.</div>
  )

  if (loading) return <div className="state-msg" data-testid="pr-viewer-loading">Loading PR data…</div>

  if (!data) return <div className="state-msg" data-testid="pr-viewer-empty">No PR data.</div>

  if (data.error) return <div className="error-banner" data-testid="pr-viewer-error">{data.error}</div>

  if (!data.prs || data.prs.length === 0) return (
    <div className="state-msg" data-testid="pr-viewer-no-prs">No pull requests linked to <strong>{ticket['Issue Key']}</strong>.</div>
  )

  const diff = data.diff

  return (
    <div className="pr-viewer" data-testid="pr-viewer">
      <div className="pr-viewer-ticket">
        <span className="ticket-key">{ticket['Issue Key']}</span> — {ticket.Summary}
      </div>

      <div className="pr-list" data-testid="pr-list">
        {data.prs.map((pr, i) => (
          <div key={i} className="pr-row" data-testid={`pr-row-${i}`}>
            <span className={`pr-status-badge pr-${pr.status?.toLowerCase()}`}>{pr.status}</span>
            <a href={pr.url} target="_blank" rel="noreferrer" className="pr-link">
              {pr.title || pr.url}
            </a>
            <span className="pr-author">by {pr.author}</span>
          </div>
        ))}
      </div>

      {diff && !diff.error && (
        <>
          <div className="diff-metrics" data-testid="diff-metrics">
            <div className="diff-metric">
              <span className="diff-metric-value">{diff.changed_files}</span>
              <span className="diff-metric-label">files</span>
            </div>
            <div className="diff-metric diff-metric-add">
              <span className="diff-metric-value">+{diff.additions}</span>
              <span className="diff-metric-label">additions</span>
            </div>
            <div className="diff-metric diff-metric-del">
              <span className="diff-metric-value">-{diff.deletions}</span>
              <span className="diff-metric-label">deletions</span>
            </div>
          </div>

          {diff.files && diff.files.length > 0 && (
            <table className="diff-table" data-testid="diff-table">
              <thead>
                <tr><th>File</th><th>Status</th><th>+</th><th>-</th></tr>
              </thead>
              <tbody>
                {diff.files.map((f, i) => (
                  <tr key={i}>
                    <td className="diff-file-name">{f.filename}</td>
                    <td><span className={`file-status file-${f.status}`}>{f.status}</span></td>
                    <td className="additions">+{f.additions}</td>
                    <td className="deletions">-{f.deletions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {diff.diff_summary && (
            <div className="diff-expander">
              <button
                className="btn btn-ghost"
                onClick={() => setDiffOpen(o => !o)}
                data-testid="raw-diff-toggle"
              >
                {diffOpen ? '▲ Hide raw diff' : '▼ View raw diff'}
              </button>
              {diffOpen && (
                <pre className="diff-raw" data-testid="raw-diff-content">{diff.diff_summary}</pre>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
