import { useState, useRef } from 'react'
import { MacroModal, macroLabel } from '../components/MacroModal'

const KEY_GRID = [['1','2','3','4'],['5','6','7','8']]
const ALL_KEYS = KEY_GRID.flat()

export default function MacrosPage({ t, macros, api, onRefresh }) {
  const [editing,   setEditing]   = useState(null)
  const [clipboard, setClipboard] = useState(null)
  const [dragOver,  setDragOver]  = useState(null)
  const [undoState, setUndoState] = useState(null)  // { keyId, press, hold }
  const dragSrc = useRef(null)

  const handleSave = async (keyId, press, hold) => {
    // Snapshot current state for undo before overwriting
    setUndoState({
      keyId,
      press: macros[`KP:${keyId}`]      ?? null,
      hold:  macros[`KP:${keyId}:HOLD`] ?? null,
    })
    setEditing(null)
    if (press) await api?.set_macro(`KP:${keyId}`,      press.type, press.action)
    else       await api?.delete_macro(`KP:${keyId}`)
    if (hold)  await api?.set_macro(`KP:${keyId}:HOLD`, hold.type,  hold.action, hold.hold_ms ?? 500)
    else       await api?.delete_macro(`KP:${keyId}:HOLD`)
    onRefresh?.()
  }

  const handleUndo = async () => {
    if (!undoState) return
    const { keyId, press, hold } = undoState
    setUndoState(null)
    if (press) await api?.set_macro(`KP:${keyId}`,      press.type, press.action)
    else       await api?.delete_macro(`KP:${keyId}`).catch(() => {})
    if (hold)  await api?.set_macro(`KP:${keyId}:HOLD`, hold.type,  hold.action, hold.hold_ms ?? 500)
    else       await api?.delete_macro(`KP:${keyId}:HOLD`).catch(() => {})
    onRefresh?.()
  }

  // ── copy / paste ─────────────────────────────────────────────────────────
  const copyKey = (keyId, e) => {
    e.stopPropagation()
    setClipboard({
      press: macros[`KP:${keyId}`]      ?? null,
      hold:  macros[`KP:${keyId}:HOLD`] ?? null,
    })
  }

  const pasteKey = async (keyId, e) => {
    e.stopPropagation()
    if (!clipboard) return
    await handleSave(keyId, clipboard.press, clipboard.hold)
  }

  // ── drag and drop ─────────────────────────────────────────────────────────
  const onDragStart = (keyId)     => { dragSrc.current = keyId }
  const onDragOver  = (keyId, e)  => { e.preventDefault(); setDragOver(keyId) }
  const onDragLeave = ()          => setDragOver(null)

  const onDrop = async (targetId, e) => {
    e.preventDefault()
    setDragOver(null)
    const srcId = dragSrc.current
    if (!srcId || srcId === targetId) return
    const srcPress = macros[`KP:${srcId}`]        ?? null
    const srcHold  = macros[`KP:${srcId}:HOLD`]   ?? null
    const tgtPress = macros[`KP:${targetId}`]      ?? null
    const tgtHold  = macros[`KP:${targetId}:HOLD`] ?? null
    // Swap: write target's macros into src slot
    if (tgtPress) await api?.set_macro(`KP:${srcId}`, tgtPress.type, tgtPress.action)
    else          await api?.delete_macro(`KP:${srcId}`).catch(() => {})
    if (tgtHold)  await api?.set_macro(`KP:${srcId}:HOLD`, tgtHold.type, tgtHold.action, tgtHold.hold_ms ?? 500)
    else          await api?.delete_macro(`KP:${srcId}:HOLD`).catch(() => {})
    // Write src's macros into target slot
    if (srcPress) await api?.set_macro(`KP:${targetId}`, srcPress.type, srcPress.action)
    else          await api?.delete_macro(`KP:${targetId}`).catch(() => {})
    if (srcHold)  await api?.set_macro(`KP:${targetId}:HOLD`, srcHold.type, srcHold.action, srcHold.hold_ms ?? 500)
    else          await api?.delete_macro(`KP:${targetId}:HOLD`).catch(() => {})
    onRefresh?.()
  }

  return (
    <div>
      <div style={{ marginBottom:24, display:'flex', alignItems:'flex-start', justifyContent:'space-between' }}>
        <div>
          <h1 style={{ fontSize:20, fontWeight:700, marginBottom:4 }}>Macros</h1>
          <p style={{ fontSize:13, color:t.muted }}>
            Click to assign. Drag to swap.{clipboard ? ' Clipboard ready — click Paste on any key.' : ''}
          </p>
        </div>
        {undoState && (
          <button onClick={handleUndo}
            style={{ padding:'6px 14px', borderRadius:6, border:`1px solid ${t.border}`, background:'transparent', color:t.muted, fontSize:12, cursor:'pointer', flexShrink:0, marginTop:4 }}>
            ↩ Undo
          </button>
        )}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, maxWidth:560 }}>
        {ALL_KEYS.map(keyId => {
          const press      = macros[`KP:${keyId}`]
          const hold       = macros[`KP:${keyId}:HOLD`]
          const isDragOver = dragOver === keyId
          return (
            <div key={keyId}
              draggable
              onDragStart={() => onDragStart(keyId)}
              onDragOver={e  => onDragOver(keyId, e)}
              onDragLeave={onDragLeave}
              onDrop={e      => onDrop(keyId, e)}
              style={{
                background: isDragOver ? t.hover : t.card,
                border: `1px solid ${isDragOver ? t.accent : t.border}`,
                borderRadius:8, padding:'12px', cursor:'grab',
                transition:'border-color 0.1s, background 0.1s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor=t.accent; e.currentTarget.style.background=t.hover }}
              onMouseLeave={e => { if (dragOver !== keyId) { e.currentTarget.style.borderColor=t.border; e.currentTarget.style.background=t.card } }}
            >
              <div style={{ fontSize:18, fontWeight:700, color:t.dim, marginBottom:6 }}>{keyId}</div>

              {/* Click area to edit */}
              <div onClick={() => setEditing(keyId)} style={{ cursor:'pointer' }}>
                <div style={{ fontSize:11, color:press?t.text:t.dim, marginBottom:3, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  ▶ {press ? macroLabel(press) : 'empty'}
                </div>
                <div style={{ fontSize:11, color:hold?t.muted:t.dim, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  ⏸ {hold ? macroLabel(hold) : 'empty'}
                </div>
              </div>

              {/* Copy / Paste */}
              <div style={{ display:'flex', gap:4, marginTop:8 }}>
                <button onClick={e => copyKey(keyId, e)}
                  style={{ flex:1, padding:'3px', borderRadius:4, border:`1px solid ${t.border}`, background:'transparent', color:t.dim, fontSize:10, cursor:'pointer' }}>
                  Copy
                </button>
                <button onClick={e => pasteKey(keyId, e)} disabled={!clipboard}
                  style={{ flex:1, padding:'3px', borderRadius:4, border:`1px solid ${clipboard?t.accent:t.border}`, background:'transparent', color:clipboard?t.accent:t.dim, fontSize:10, cursor:clipboard?'pointer':'not-allowed' }}>
                  Paste
                </button>
              </div>
            </div>
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
