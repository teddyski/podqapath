import { useState } from 'react'
import { loadFilters } from '../api'

export default function Sidebar({
  projectKey, onProjectKeyChange,
  filters, onFiltersLoaded,
  activeFilters, onActiveFiltersChange,
  onFetchTickets, loading,
}) {
  const [filtersLoading, setFiltersLoading] = useState(false)
  const [filtersError, setFiltersError] = useState('')

  async function handleConnect() {
    setFiltersLoading(true)
    setFiltersError('')
    try {
      const data = await loadFilters(projectKey)
      onFiltersLoaded(data)
    } catch (e) {
      setFiltersError(e.message)
    } finally {
      setFiltersLoading(false)
    }
  }

  function toggleItem(key, item) {
    const current = activeFilters[key]
    const next = current.includes(item) ? current.filter(x => x !== item) : [...current, item]
    onActiveFiltersChange({ ...activeFilters, [key]: next })
  }

  function toggleSprint(name) {
    const id = filters.sprints[name]
    const current = activeFilters.sprintIds
    const next = current.includes(id) ? current.filter(x => x !== id) : [...current, id]
    onActiveFiltersChange({ ...activeFilters, sprintIds: next })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-logo">🛡️</span>
        <span className="sidebar-title">PodQApath</span>
      </div>

      <div className="sidebar-section">
        <label className="sidebar-label">Project Key</label>
        <input
          className="sidebar-input"
          value={projectKey}
          onChange={e => onProjectKeyChange(e.target.value.toUpperCase())}
          placeholder="e.g. SCRUM"
        />
      </div>

      <button className="btn btn-secondary" onClick={handleConnect} disabled={filtersLoading}>
        {filtersLoading ? 'Connecting…' : 'Connect & Load Filters'}
      </button>
      {filtersError && <div className="error-small">{filtersError}</div>}

      {filters.labels.length > 0 && (
        <div className="sidebar-section">
          <label className="sidebar-label">Tags</label>
          <div className="chip-group">
            {filters.labels.map(l => (
              <button
                key={l}
                className={`chip ${activeFilters.tags.includes(l) ? 'chip-active' : ''}`}
                onClick={() => toggleItem('tags', l)}
              >{l}</button>
            ))}
          </div>
        </div>
      )}

      {filters.statuses.length > 0 && (
        <div className="sidebar-section">
          <label className="sidebar-label">Statuses</label>
          <div className="chip-group">
            {filters.statuses.map(s => (
              <button
                key={s}
                className={`chip ${activeFilters.statuses.includes(s) ? 'chip-active' : ''}`}
                onClick={() => toggleItem('statuses', s)}
              >{s}</button>
            ))}
          </div>
        </div>
      )}

      {Object.keys(filters.sprints || {}).length > 0 && (
        <div className="sidebar-section">
          <label className="sidebar-label">Sprint</label>
          <div className="chip-group">
            {Object.keys(filters.sprints).map(name => {
              const id = filters.sprints[name]
              return (
                <button
                  key={name}
                  className={`chip ${activeFilters.sprintIds.includes(id) ? 'chip-active' : ''}`}
                  onClick={() => toggleSprint(name)}
                >{name}</button>
              )
            })}
          </div>
        </div>
      )}

      <button className="btn btn-primary" onClick={onFetchTickets} disabled={loading}>
        {loading ? 'Fetching…' : '☁️ Fetch Live Data'}
      </button>

      <div className="sidebar-section risk-key">
        <label className="sidebar-label">Risk Key</label>
        {[
          ['RED',    '#ff4b4b', '🔴 Critical — release imminent or health critical'],
          ['ORANGE', '#ff8c00', '🟠 High — proximity or multiple flags'],
          ['YELLOW', '#ffd700', '🟡 Medium — monitor before sprint end'],
          ['GREEN',  '#21c354', '🟢 Low — healthy, release not near'],
        ].map(([band, color, desc]) => (
          <div key={band} className="risk-key-row">
            <span className="risk-dot" style={{ background: color }} />
            <span className="risk-key-desc">{desc}</span>
          </div>
        ))}
        <p className="risk-key-caption">
          Dominant: release proximity (≤2d +70, ≤7d +35, ≤14d +20, ≤21d +5) · priority · age · branch · type · assignee
        </p>
      </div>
    </aside>
  )
}
