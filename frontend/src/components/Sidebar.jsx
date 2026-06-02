import { useState } from 'react'

const NAV = [
  { id: 'Macros',   label: 'Macros',        icon: '⌨' },
  { id: 'Encoders', label: 'Encoders',       icon: '🎛' },
  { id: 'Settings', label: 'Settings',       icon: '⚙' },
  { id: 'Upload',   label: 'Upload Firmware',icon: '⬆' },
  { id: 'Test',     label: 'Test Mode',      icon: '▶' },
]

export default function Sidebar({
  t, page, setPage, dark, setDark,
  connected, port,
  profiles, activeProfile,
  onSwitch, onNew, onDelete,
}) {
  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState('')

  const btn = (extra = {}) => ({
    display: 'flex', alignItems: 'center', gap: 10,
    width: '100%', textAlign: 'left',
    padding: '8px 12px', borderRadius: 6,
    border: 'none', cursor: 'pointer', fontSize: 13,
    transition: 'background 0.1s',
    ...extra,
  })

  return (
    <aside style={{
      width: 210, minWidth: 210,
      background: t.sidebar,
      borderRight: `1px solid ${t.border}`,
      display: 'flex', flexDirection: 'column',
      userSelect: 'none',
    }}>
      {/* Header */}
      <div style={{ padding: '18px 16px 14px', borderBottom: `1px solid ${t.border}` }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, letterSpacing: '-0.3px' }}>
          MacroPad
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 5 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: connected ? t.success : t.danger,
            flexShrink: 0,
          }} />
          <span style={{ fontSize: 11, color: t.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {connected ? port : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '10px 8px', overflowY: 'auto' }}>
        {NAV.map(item => (
          <button
            key={item.id}
            onClick={() => setPage(item.id)}
            style={btn({
              background: page === item.id ? t.hover : 'transparent',
              color: page === item.id ? t.text : t.muted,
              fontWeight: page === item.id ? 600 : 400,
              marginBottom: 2,
            })}
          >
            <span style={{ width: 18, textAlign: 'center', fontSize: 13, flexShrink: 0 }}>
              {item.icon}
            </span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Profile picker */}
      <div style={{ padding: '12px', borderTop: `1px solid ${t.border}` }}>
        <div style={{
          fontSize: 10, fontWeight: 600, color: t.dim,
          textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 7,
        }}>
          Profile
        </div>
        <select
          value={activeProfile}
          onChange={e => onSwitch(e.target.value)}
          style={{
            width: '100%', padding: '6px 8px', marginBottom: 6,
            borderRadius: 5, border: `1px solid ${t.border}`,
            background: t.card, color: t.text, fontSize: 12, cursor: 'pointer',
          }}
        >
          {profiles.map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        {adding ? (
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              autoFocus
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && newName.trim()) {
                  onNew(newName.trim()); setNewName(''); setAdding(false)
                }
                if (e.key === 'Escape') { setNewName(''); setAdding(false) }
              }}
              placeholder="Profile name…"
              style={{
                flex: 1, padding: '5px 8px', borderRadius: 5,
                border: `1px solid ${t.accent}`, background: t.elevated,
                color: t.text, fontSize: 12, outline: 'none',
              }}
            />
            <button
              onClick={() => { setNewName(''); setAdding(false) }}
              style={{ padding: '5px 8px', borderRadius: 5, border: 'none', background: t.elevated, color: t.muted, cursor: 'pointer' }}
            >
              ✕
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => setAdding(true)}
              style={{
                flex: 1, padding: '5px', borderRadius: 5,
                border: `1px solid ${t.border}`, background: 'transparent',
                color: t.muted, cursor: 'pointer', fontSize: 12,
              }}
            >
              + New
            </button>
            <button
              onClick={() => profiles.length > 1 && onDelete(activeProfile)}
              disabled={profiles.length <= 1}
              style={{
                padding: '5px 10px', borderRadius: 5,
                border: `1px solid ${t.border}`, background: 'transparent',
                color: profiles.length <= 1 ? t.dim : t.danger,
                cursor: profiles.length <= 1 ? 'not-allowed' : 'pointer', fontSize: 12,
              }}
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Theme toggle */}
      <div style={{
        padding: '10px 12px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderTop: `1px solid ${t.border}`,
      }}>
        <span style={{ fontSize: 12, color: t.muted }}>Dark mode</span>
        <button
          onClick={() => setDark(!dark)}
          style={{
            width: 36, height: 20, borderRadius: 10, border: 'none',
            background: dark ? t.accent : t.border,
            cursor: 'pointer', position: 'relative', padding: 0, flexShrink: 0,
          }}
        >
          <div style={{
            width: 14, height: 14, borderRadius: '50%', background: '#fff',
            position: 'absolute', top: 3,
            left: dark ? 19 : 3,
            transition: 'left 0.15s',
          }} />
        </button>
      </div>
    </aside>
  )
}
