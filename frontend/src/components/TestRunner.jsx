import { useState, useRef, useEffect, useCallback } from 'react'

export default function TestRunner({ prData, autoRunTest, onClearAutoRun, onResultsUpdate }) {
  const [repoPath, setRepoPath] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [baseUrl, setBaseUrl] = useState('http://localhost:3000')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  // tests: [{title, status: 'pending'|'pass'|'fail', duration?}]
  const [tests, setTests] = useState([])
  // raw output lines (errors, info) that aren't test result rows
  const [rawLines, setRawLines] = useState([])
  const [summary, setSummary] = useState(null) // {passed, failed}
  const outputRef = useRef(null)

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [tests, rawLines])

  const handleRun = useCallback(async (overrideUrl = null) => {
    const urlToUse = overrideUrl !== null ? overrideUrl : repoUrl.trim()
    const pathToUse = overrideUrl !== null ? '' : repoPath.trim()

    if (!pathToUse && !urlToUse) {
      setError('Enter a repo path or GitHub URL')
      return
    }
    setError('')
    setRunning(true)
    setTests([])
    setRawLines([])
    setSummary(null)

    const accumulated = []

    try {
      const res = await fetch('/api/run-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo_path: pathToUse,
          repo_url: urlToUse,
          base_url: baseUrl.trim() || 'http://localhost:3000',
        }),
      })

      if (!res.ok) {
        setError(await res.text())
        setRunning(false)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n')
        buffer = parts.pop()
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue
          try {
            const event = JSON.parse(part.slice(6))
            handleEvent(event, accumulated)
          } catch { /* malformed chunk */ }
        }
      }

      if (onResultsUpdate && accumulated.length) {
        onResultsUpdate(accumulated.join('\n'))
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }, [repoPath, repoUrl, baseUrl, onResultsUpdate])

  // Auto-run only when the ▶ Test button was clicked and prData has arrived
  useEffect(() => {
    if (!autoRunTest || !prData) return
    const prUrl = prData?.prs?.[0]?.url || ''
    if (!prUrl.includes('github.com')) return
    const m = prUrl.match(/^(https:\/\/github\.com\/[^/]+\/[^/]+)/)
    if (!m) return
    onClearAutoRun?.()
    const repoBase = m[1]
    setRepoUrl(repoBase)
    setRepoPath('')
    handleRun(repoBase)
  }, [prData, autoRunTest]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleEvent(event, accumulated) {
    if (event.type === 'error') {
      setError(event.message)
    } else if (event.type === 'discovered') {
      setTests(prev => {
        // avoid duplicates from multiple browsers
        if (prev.some(t => t.title === event.title)) return prev
        return [...prev, { title: event.title, status: 'pending' }]
      })
    } else if (event.type === 'result') {
      accumulated.push(`${event.status === 'pass' ? '✓' : '✗'} ${event.title} (${event.duration})`)
      setTests(prev => {
        const idx = prev.findIndex(t => t.title === event.title)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = { ...next[idx], status: event.status, duration: event.duration }
          return next
        }
        // Result for a test not discovered (e.g. discovery was skipped)
        return [...prev, { title: event.title, status: event.status, duration: event.duration }]
      })
    } else if (event.type === 'output') {
      accumulated.push(event.text)
      setRawLines(prev => [...prev, event.text])
    } else if (event.type === 'summary') {
      setSummary({ passed: event.passed, failed: event.failed })
      accumulated.push(`\n${event.passed} passed, ${event.failed} failed`)
    }
    // 'start' and 'done' need no state update
  }

  const hasResults = tests.length > 0 || rawLines.length > 0

  return (
    <div className="test-runner" data-testid="test-runner">
      <div className="test-runner-header-static">
        🧪 Repo Test Runner
        {running && <span className="test-runner-running-badge">running…</span>}
      </div>

      <div className="test-runner-body">
        <div className="sidebar-field">
          <label className="sidebar-label">Repo Path</label>
          <input
            className="sidebar-input"
            value={repoPath}
            onChange={e => setRepoPath(e.target.value)}
            placeholder="/absolute/path/to/repo"
            disabled={running}
            data-testid="test-runner-repo-path"
          />
        </div>

        <div style={{ fontSize: '10px', color: 'var(--text-muted)', textAlign: 'center' }}>— or —</div>

        <div className="sidebar-field">
          <label className="sidebar-label">GitHub URL</label>
          <input
            className="sidebar-input"
            value={repoUrl}
            onChange={e => setRepoUrl(e.target.value)}
            placeholder="https://github.com/org/repo"
            disabled={running}
            data-testid="test-runner-repo-url"
          />
        </div>

        <div className="sidebar-field">
          <label className="sidebar-label">Base URL</label>
          <input
            className="sidebar-input"
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
            placeholder="http://localhost:3000"
            disabled={running}
            data-testid="test-runner-base-url"
          />
        </div>

        {error && <div className="error-small" data-testid="test-runner-error">{error}</div>}

        <button
          className="btn btn-primary"
          onClick={() => handleRun()}
          disabled={running}
          style={{ width: '100%' }}
          data-testid="test-runner-run-btn"
        >
          {running ? '⏳ Running…' : '▶ Run Tests'}
        </button>

        {hasResults && (
          <div className="test-runner-results" ref={outputRef} data-testid="test-runner-results">
            {tests.map((t, i) => (
              <div
                key={i}
                className={`test-result-row test-result-${t.status}`}
                data-testid={`test-result-${t.status}`}
              >
                <span className="test-result-icon">
                  {t.status === 'pending' ? '⬜' : t.status === 'pass' ? '✅' : '❌'}
                </span>
                <span className="test-result-title" title={t.title}>{t.title}</span>
                {t.duration && <span className="test-result-dur">({t.duration})</span>}
              </div>
            ))}

            {rawLines.length > 0 && (
              <div className="test-raw-output">
                {rawLines.map((line, i) => (
                  <div key={i} className="test-raw-line">{line}</div>
                ))}
              </div>
            )}

            {summary && (
              <div className={`test-summary ${summary.failed > 0 ? 'test-summary-fail' : 'test-summary-pass'}`}
                data-testid="test-runner-summary">
                {summary.passed > 0 && <span>✅ {summary.passed} passed</span>}
                {summary.failed > 0 && <span> · ❌ {summary.failed} failed</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
