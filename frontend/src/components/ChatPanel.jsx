import { useState, useRef, useEffect } from 'react'
import { sendChat } from '../api'

export default function ChatPanel({ context }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [managerMode, setManagerMode] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  async function handleSend() {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setError('')

    const userMsg = { role: 'user', content: msg }
    setHistory(h => [...h, userMsg])
    setLoading(true)

    try {
      const { reply } = await sendChat({
        message: msg,
        history: history.map(m => ({ role: m.role, content: m.content })),
        managerMode,
        context,
      })
      setHistory(h => [...h, { role: 'assistant', content: reply }])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-mode-bar">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={managerMode}
            onChange={e => setManagerMode(e.target.checked)}
            className="toggle-input"
          />
          <span className="toggle-track" />
          <span className="toggle-text">
            {managerMode ? 'Manager mode — plain language' : 'Technical mode — full analysis'}
          </span>
        </label>
      </div>

      <div className="chat-messages">
        {history.length === 0 && (
          <div className="chat-empty">
            Ask QA-7 anything about your release — risk, tickets, collisions, or readiness.
          </div>
        )}
        {history.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg-${m.role}`}>
            <span className="chat-msg-role">{m.role === 'user' ? 'You' : 'QA-7'}</span>
            <div className="chat-msg-content">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg-assistant">
            <span className="chat-msg-role">QA-7</span>
            <div className="chat-msg-content chat-thinking">Thinking…</div>
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask QA-7… (Enter to send)"
          rows={2}
          disabled={loading}
        />
        <button className="btn btn-primary chat-send" onClick={handleSend} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
