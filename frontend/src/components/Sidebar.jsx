import { useState } from 'react'

const NAV = [
  { id: 'Macros',   label: 'Macros',         icon: '⌨' },
  { id: 'Encoders', label: 'Encoders',        icon: '🎛' },
  { id: 'Settings', label: 'Settings',        icon: '⚙' },
  { id: 'Upload',   label: 'Upload Firmware', icon: '⬆' },
  { id: 'Test',     label: 'Test Mode',       icon: '▶' },
]

export default function Sidebar({
  t, page, setPage, dark, setDark,
  connected, port,
  profiles, activeProfile,
  onSwitch, onNew, onDelete, onRename, onDuplicate,
}) {
  const [collapsed,  setCollapsed]  = useState(false)
  const [adding,     setAdding]     = useState(false)
  const [newName,    setNewName]    = useState('')
  const [renaming,   setRenaming]   = useState(false)
  const [renameVal,  setRenameVal]  = useState('')

  const startRename  = () => { setRenameVal(activeProfile); setRenaming(true) }
  const commitRename = () => {
    const v = renameVal.trim()
    if (v && v !== activeProfile) onRename?.(activeProfile, v)
    setRenaming(false)
  }

  const iconBtn = (onClick, label, title, style = {}) => (
    <button onClick={onClick} title={title}
      style={{ padding:'5px 7px', borderRadius:5, border:`1px solid ${t.border}`, background:'transparent', color:t.dim, cursor:'pointer', fontSize:12, flexShrink:0, ...style }}>
      {label}
    </button>
  )

  // ── Collapsed view ────────────────────────────────────────────────────────
  if (collapsed) return (
    <aside style={{
      width:52, minWidth:52,
      background: t.sidebar,
      borderRight: `1px solid ${t.border}`,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center',
      userSelect: 'none',
      transition: 'width 0.2s',
    }}>
      {/* Expand button */}
      <button onClick={() => setCollapsed(false)} title="Expand sidebar"
        style={{ width:'100%', padding:'16px 0 12px', border:'none', background:'transparent', color:t.muted, cursor:'pointer', fontSize:16 }}>
        »
      </button>

      {/* Connection dot */}
      <div title={connected ? port : 'Disconnected'}
        className={connected ? 'dot-connected' : ''}
        style={{ width:8, height:8, borderRadius:'50%', background:connected?t.success:t.danger, margin:'0 0 8px' }} />

      {/* Nav icons */}
      <nav style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:2, paddingTop:4, width:'100%' }}>
        {NAV.map(item => (
          <button key={item.id} onClick={() => setPage(item.id)} title={item.label}
            style={{
              width:'100%', padding:'10px 0', border:'none', cursor:'pointer',
              background: page === item.id ? t.hover : 'transparent',
              color: page === item.id ? t.text : t.muted,
              fontSize:18, transition:'background 0.1s',
            }}>
            {item.icon}
          </button>
        ))}
      </nav>

      {/* Dark mode icon */}
      <button onClick={() => setDark(!dark)} title="Toggle dark mode"
        style={{ padding:'10px 0', width:'100%', border:'none', background:'transparent', color:t.muted, cursor:'pointer', fontSize:15 }}>
        {dark ? '☀' : '🌙'}
      </button>
    </aside>
  )

  // ── Expanded view ─────────────────────────────────────────────────────────
  return (
    <aside style={{
      width: 210, minWidth: 210,
      background: t.sidebar,
      borderRight: `1px solid ${t.border}`,
      display: 'flex', flexDirection: 'column',
      userSelect: 'none',
      transition: 'width 0.2s',
    }}>
      {/* Header */}
      <div style={{ padding:'14px 12px 12px', borderBottom:`1px solid ${t.border}`, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <div style={{ fontSize:15, fontWeight:700, color:t.text, letterSpacing:'-0.3px' }}>MacroPad</div>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginTop:4 }}>
            <div className={connected ? 'dot-connected' : ''} style={{ width:7, height:7, borderRadius:'50%', background:connected?t.success:t.danger, flexShrink:0 }} />
            <span className="mono" style={{ fontSize:11, color:t.muted, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {connected ? port : 'Disconnected'}
            </span>
          </div>
        </div>
        <button onClick={() => setCollapsed(true)} title="Collapse sidebar"
          style={{ padding:'4px 8px', border:`1px solid ${t.border}`, borderRadius:5, background:'transparent', color:t.dim, cursor:'pointer', fontSize:13, flexShrink:0 }}>
          «
        </button>
      </div>

      {/* Nav */}
      <nav style={{ flex:1, padding:'10px 8px', overflowY:'auto' }}>
        {NAV.map(item => (
          <button key={item.id} onClick={() => setPage(item.id)}
            style={{
              display:'flex', alignItems:'center', gap:10,
              width:'100%', textAlign:'left', padding:'8px 12px', borderRadius:6,
              border:'none', cursor:'pointer', fontSize:13,
              background: page === item.id ? t.hover : 'transparent',
              color: page === item.id ? t.text : t.muted,
              fontWeight: page === item.id ? 600 : 400,
              marginBottom:2, transition:'background 0.1s',
            }}>
            <span style={{ width:18, textAlign:'center', fontSize:13, flexShrink:0 }}>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Profile picker */}
      <div style={{ padding:'12px', borderTop:`1px solid ${t.border}` }}>
        <div style={{ fontSize:10, fontWeight:600, color:t.dim, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:7 }}>
          Profile
        </div>

        {renaming ? (
          <div style={{ display:'flex', gap:4, marginBottom:6 }}>
            <input autoFocus value={renameVal} onChange={e => setRenameVal(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenaming(false) }}
              style={{ flex:1, padding:'5px 8px', borderRadius:5, border:`1px solid ${t.accent}`, background:t.elevated, color:t.text, fontSize:12, outline:'none' }} />
            <button onClick={commitRename} style={{ padding:'5px 8px', borderRadius:5, border:'none', background:t.accent, color:'#fff', cursor:'pointer', fontSize:12 }}>✓</button>
            <button onClick={() => setRenaming(false)} style={{ padding:'5px 8px', borderRadius:5, border:'none', background:t.elevated, color:t.muted, cursor:'pointer' }}>✕</button>
          </div>
        ) : (
          <div style={{ display:'flex', gap:4, alignItems:'center', marginBottom:6 }}>
            <select value={activeProfile} onChange={e => onSwitch(e.target.value)}
              style={{ flex:1, padding:'6px 8px', borderRadius:5, border:`1px solid ${t.border}`, background:t.card, color:t.text, fontSize:12, cursor:'pointer' }}>
              {profiles.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            {iconBtn(startRename, '✎', 'Rename profile')}
          </div>
        )}

        {adding ? (
          <div style={{ display:'flex', gap:4, marginBottom:6 }}>
            <input autoFocus value={newName} onChange={e => setNewName(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && newName.trim()) { onNew(newName.trim()); setNewName(''); setAdding(false) }
                if (e.key === 'Escape') { setNewName(''); setAdding(false) }
              }}
              placeholder="Profile name…"
              style={{ flex:1, padding:'5px 8px', borderRadius:5, border:`1px solid ${t.accent}`, background:t.elevated, color:t.text, fontSize:12, outline:'none' }} />
            <button onClick={() => { setNewName(''); setAdding(false) }}
              style={{ padding:'5px 8px', borderRadius:5, border:'none', background:t.elevated, color:t.muted, cursor:'pointer' }}>✕</button>
          </div>
        ) : (
          <div style={{ display:'flex', gap:4 }}>
            <button onClick={() => setAdding(true)}
              style={{ flex:1, padding:'5px', borderRadius:5, border:`1px solid ${t.border}`, background:'transparent', color:t.muted, cursor:'pointer', fontSize:12 }}>
              + New
            </button>
            <button onClick={() => onDuplicate?.(activeProfile)} title="Duplicate profile"
              style={{ padding:'5px 8px', borderRadius:5, border:`1px solid ${t.border}`, background:'transparent', color:t.muted, cursor:'pointer', fontSize:12 }}>
              ⧉
            </button>
            <button onClick={() => profiles.length > 1 && onDelete(activeProfile)} disabled={profiles.length <= 1}
              style={{ padding:'5px 10px', borderRadius:5, border:`1px solid ${t.border}`, background:'transparent', color:profiles.length<=1?t.dim:t.danger, cursor:profiles.length<=1?'not-allowed':'pointer', fontSize:12 }}>
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Theme toggle */}
      <div style={{ padding:'10px 12px', display:'flex', alignItems:'center', justifyContent:'space-between', borderTop:`1px solid ${t.border}` }}>
        <span style={{ fontSize:12, color:t.muted }}>Dark mode</span>
        <button onClick={() => setDark(!dark)}
          style={{ width:36, height:20, borderRadius:10, border:'none', background:dark?t.accent:t.border, cursor:'pointer', position:'relative', padding:0, flexShrink:0 }}>
          <div style={{ width:14, height:14, borderRadius:'50%', background:'#fff', position:'absolute', top:3, left:dark?19:3, transition:'left 0.15s' }} />
        </button>
      </div>
    </aside>
  )
}
