import { useState } from 'react'
import { MacroModal, macroLabel } from '../components/MacroModal'

const KEY_GRID = [['1','2','3','4'],['5','6','7','8']]

export default function MacrosPage({ t, macros, api, onRefresh }) {
  const [editing, setEditing] = useState(null)

  const handleSave = async (keyId, press, hold) => {
    setEditing(null)
    await (press ? api?.set_macro(`KP:${keyId}`,      press.type, press.action) : api?.delete_macro(`KP:${keyId}`))
    await (hold  ? api?.set_macro(`KP:${keyId}:HOLD`, hold.type,  hold.action)  : api?.delete_macro(`KP:${keyId}:HOLD`))
    onRefresh?.()
  }

  return (
    <div>
      <div style={{ marginBottom:24 }}>
        <h1 style={{ fontSize:20, fontWeight:700, marginBottom:4 }}>Macros</h1>
        <p style={{ fontSize:13, color:t.muted }}>Click a key to assign press and hold actions.</p>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, maxWidth:560 }}>
        {KEY_GRID.flat().map(keyId => {
          const press = macros[`KP:${keyId}`]
          const hold  = macros[`KP:${keyId}:HOLD`]
          return (
            <button key={keyId} onClick={() => setEditing(keyId)}
              style={{ background:t.card, border:`1px solid ${t.border}`, borderRadius:8, padding:'14px 12px', cursor:'pointer', textAlign:'left', transition:'border-color 0.15s, background 0.15s' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor=t.accent; e.currentTarget.style.background=t.hover }}
              onMouseLeave={e => { e.currentTarget.style.borderColor=t.border; e.currentTarget.style.background=t.card }}>
              <div style={{ fontSize:18, fontWeight:700, color:t.dim, marginBottom:6 }}>{keyId}</div>
              <div style={{ fontSize:11, color:press?t.text:t.dim, marginBottom:3, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                ▶ {press ? macroLabel(press) : 'empty'}
              </div>
              <div style={{ fontSize:11, color:hold?t.muted:t.dim, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                ⏸ {hold ? macroLabel(hold) : 'empty'}
              </div>
            </button>
          )
        })}
      </div>

      {editing !== null && (
        <MacroModal
          t={t} api={api} title={`Key ${editing}`}
          pressData={macros[`KP:${editing}`]}
          holdData={macros[`KP:${editing}:HOLD`]}
          onSave={(press, hold) => handleSave(editing, press, hold)}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}
