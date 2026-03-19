import { useState, useRef, useEffect } from 'react'
import { loadFilters } from '../api'
import TestRunner from './TestRunner'

// ---------------------------------------------------------------------------
// Multi-select dropdown
// ---------------------------------------------------------------------------
function MultiSelect({ label, options, selected, onChange, disabled, placeholder, testId }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function toggle(val) {
    const next = selected.includes(val)
      ? selected.filter(x => x !== val)
      : [...selected, val]
    onChange(next)
  }

  const summary = selected.length === 0
    ? placeholder || `All ${label.toLowerCase()}`
    : `${selected.length} selected`

  return (
    <div className="sidebar-field" ref={ref}>
      <label className="sidebar-label">{label}</label>
      <button
        className={`multiselect-trigger ${disabled ? 'multiselect-disabled' : ''} ${open ? 'multiselect-open' : ''}`}
        onClick={() => !disabled && setOpen(o => !o)}
        disabled={disabled}
        type="button"
        data-testid={testId}
      >
        <span className="multiselect-summary">{summary}</span>
        <span className="multiselect-arrow">{open ? '▲' : '▼'}</span>
      </button>
      {open && !disabled && (
        <div className="multiselect-dropdown">
          {options.length === 0 && (
            <div className="multiselect-empty">No options</div>
          )}
          {options.map(opt => (
            <label key={opt} className="multiselect-option">
              <input
                type="checkbox"
                checked={selected.includes(opt)}
                onChange={() => toggle(opt)}
              />
              <span>{opt}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
export default function Sidebar({
  projectKey, onProjectKeyChange,
  filters, onFiltersLoaded,
  activeFilters, onActiveFiltersChange,
  onFetchTickets, onLoadDemo, onTestResultsUpdate, loading,
}) {
  const [filtersLoading, setFiltersLoading] = useState(false)
  const [filtersError, setFiltersError] = useState('')
  const filtersLoaded = filters.labels.length > 0 || filters.statuses.length > 0

  async function handleConnect() {
    if (!projectKey.trim()) {
      setFiltersError('Enter a project key first')
      return
    }
    setFiltersLoading(true)
    setFiltersError('')
    try {
      const data = await loadFilters(projectKey.trim())
      onFiltersLoaded(data)
    } catch (e) {
      setFiltersError(e.message)
    } finally {
      setFiltersLoading(false)
    }
  }

  function setTags(tags) { onActiveFiltersChange({ ...activeFilters, tags }) }
  function setStatuses(statuses) { onActiveFiltersChange({ ...activeFilters, statuses }) }
  function setSprints(names) {
    const ids = names.map(n => filters.sprints[n]).filter(Boolean)
    onActiveFiltersChange({ ...activeFilters, sprintIds: ids, sprintNames: names })
  }

  const sprintOptions = Object.keys(filters.sprints || {})
  const selectedSprintNames = (activeFilters.sprintNames || []).filter(n => n in (filters.sprints || {}))

  return (
    <aside className="sidebar" data-testid="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-logo">🛡️</span>
        <span className="sidebar-title">PodQApath</span>
      </div>

      {/* ── Demo Mode ── */}
      <div className="connect-form" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
        <button
          className="btn btn-secondary"
          onClick={onLoadDemo}
          disabled={loading}
          data-testid="demo-mode-btn"
          style={{ width: '100%' }}
        >
          🧪 Load Demo Data
        </button>
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.7rem', color: 'var(--text-muted, #888)' }}>
          No credentials needed
        </p>
      </div>

      {/* ── Connect form ── */}
      <div className="connect-form">
        <label className="sidebar-label">Project Key</label>
        <input
          className="sidebar-input"
          value={projectKey}
          onChange={e => {
            onProjectKeyChange(e.target.value.toUpperCase())
            setFiltersError('')
          }}
          onKeyDown={e => e.key === 'Enter' && handleConnect()}
          placeholder="e.g. SCRUM"
          disabled={filtersLoading}
          data-testid="project-key-input"
        />
        <button
          className="btn btn-secondary"
          onClick={handleConnect}
          disabled={filtersLoading || !projectKey.trim()}
          data-testid="connect-btn"
        >
          {filtersLoading ? 'Connecting…' : 'Connect & Load Filters'}
        </button>
        {filtersError && <div className="error-small">{filtersError}</div>}
        {filtersLoaded && (
          <div className="filters-loaded-badge">
            ✓ Connected to <strong>{projectKey}</strong>
          </div>
        )}
      </div>

      {/* ── Filters ── */}
      <div className="filters-section">
        <MultiSelect
          label="Tags"
          options={filters.labels}
          selected={activeFilters.tags}
          onChange={setTags}
          disabled={!filtersLoaded}
          placeholder="All tags"
          testId="filter-tags"
        />
        <MultiSelect
          label="Statuses"
          options={filters.statuses}
          selected={activeFilters.statuses}
          onChange={setStatuses}
          disabled={!filtersLoaded}
          placeholder="All statuses"
          testId="filter-statuses"
        />
        <MultiSelect
          label="Sprint"
          options={sprintOptions}
          selected={selectedSprintNames}
          onChange={setSprints}
          disabled={!filtersLoaded}
          placeholder="All sprints"
          testId="filter-sprint"
        />
      </div>

      <button
        className="btn btn-primary fetch-btn"
        onClick={onFetchTickets}
        disabled={loading || !filtersLoaded}
        title={!filtersLoaded ? 'Connect first to load filters' : ''}
        data-testid="fetch-btn"
      >
        {loading ? 'Fetching…' : '☁️ Fetch Live Data'}
      </button>

      {/* ── Repo Test Runner ── */}
      <TestRunner onResultsUpdate={onTestResultsUpdate} />

      {/* ── Risk Key ── */}
      <div className="risk-key">
        <label className="sidebar-label">Risk Key</label>
        {[
          ['#ff4b4b', '🔴 Critical — release imminent or health critical'],
          ['#ff8c00', '🟠 High — proximity or multiple flags'],
          ['#ffd700', '🟡 Medium — monitor before sprint end'],
          ['#21c354', '🟢 Low — healthy, release not near'],
        ].map(([color, desc]) => (
          <div key={color} className="risk-key-row">
            <span className="risk-dot" style={{ background: color }} />
            <span className="risk-key-desc">{desc}</span>
          </div>
        ))}
        <p className="risk-key-caption">
          Dominant: proximity (≤2d +70, ≤7d +35, ≤14d +20, ≤21d +5) · priority · age · branch
        </p>
      </div>
    </aside>
  )
}
