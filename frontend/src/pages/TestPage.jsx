import { useState, useEffect } from 'react'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8']

export default function TestPage({ t }) {
  const [lastKey,   setLastKey]   = useState(null)
  const [lastMacro, setLastMacro] = useState(null)
  const [log,       setLog]       = useState([])
  const [active,    setActive]    = useState(null) // briefly lit key

  useEffect(() => {
    const onKeyPress = (e) => {
      const { key, macro_key, macro } = e.detail
      setLastKey(key)
      setLastMacro(macro)
      setActive(key)
      setLog(prev => [
        { key, macro_key, macro, ts: new Date().toLocaleTimeString() },
        ...prev.slice(0, 49),
      ])
      setTimeout(() => setActive(k => k === key ? null : k), 300)
    }
    window.addEventListener('macropad:key_press', onKeyPress)
    return () => window.removeEventListener('macropad:key_press', onKeyPress)
  }, [])

  const macroLabel = (m) => {
    if (!m) return '—'
    if (m.type === 'Mute App') return 'Mute app'
    if (m.type === 'Type Text') return `Type: "${m.action}"`
    return `${m.type}: ${m.action}`
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Test Mode</h1>
        <p style={{ fontSize: 13, color: t.muted }}>Press keys on your MacroPad to verify macro assignments.</p>
      </div>

      {/* Key grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 72px)', gap: 10, marginBottom: 28 }}>
        {KEYS.map(k => {
          const isActive = active === k
          return (
            <div
              key={k}
              style={{
                width: 72, height: 72,
                background: isActive ? t.accent : t.card,
                border: `2px solid ${isActive ? t.accent : lastKey === k ? t.borderLight : t.border}`,
                borderRadius: 10,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 4,
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              <span className="mono" style={{ fontSize: 20, fontWeight: 700, color: isActive ? '#fff' : t.dim }}>{k}</span>
            </div>
          )
        })}
      </div>

      {/* Last fired */}
      <div style={{
        background: t.card, border: `1px solid ${t.border}`,
        borderRadius: 8, padding: '14px 18px', marginBottom: 20,
        maxWidth: 400,
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: t.dim, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
          Last Action
        </div>
        {lastKey ? (
          <>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Key {lastKey}</div>
            <div style={{ fontSize: 13, color: t.muted }}>{macroLabel(lastMacro)}</div>
          </>
        ) : (
          <div style={{ fontSize: 13, color: t.dim }}>Waiting for key press…</div>
        )}
      </div>

      {/* Event log */}
      {log.length > 0 && (
        <div style={{ maxWidth: 480 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.dim, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
            Event Log
          </div>
          <div style={{
            background: t.card, border: `1px solid ${t.border}`,
            borderRadius: 8, maxHeight: 280, overflowY: 'auto',
          }}>
            {log.map((entry, i) => (
              <div
                key={i}
                style={{
                  display: 'flex', gap: 12, alignItems: 'flex-start',
                  padding: '8px 14px',
                  borderBottom: i < log.length - 1 ? `1px solid ${t.border}` : 'none',
                  fontSize: 12,
                }}
              >
                <span style={{ color: t.dim, flexShrink: 0, fontFamily: 'monospace' }}>{entry.ts}</span>
                <span style={{ color: t.accent, flexShrink: 0, fontWeight: 600 }}>Key {entry.key}</span>
                <span style={{ color: t.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {macroLabel(entry.macro)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
