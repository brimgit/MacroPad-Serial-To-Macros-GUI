import { useState, useEffect, useRef } from 'react'

export const MACRO_TYPES      = ['Keyboard Key','Media Control','Function Key','Modifier Key','Type Text','Mute App','Recorded']
export const MEDIA_OPTIONS    = ['play/pause','next track','prev track','volume up','volume down','mute']
export const MODIFIER_OPTIONS = ['ctrl','alt','shift','win','ctrl+c','ctrl+v','ctrl+z','ctrl+x','ctrl+a','alt+tab','ctrl+alt+del','ctrl+shift+esc']
export const FKEY_OPTIONS     = Array.from({length:24},(_,i)=>`f${i+1}`)

export function macroLabel(m) {
  if (!m) return null
  if (m.type === 'Mute App')  return 'Mute app'
  if (m.type === 'Recorded')  return `Recorded (${_evCount(m.action)} events)`
  if (m.type === 'Type Text') return `"${m.action}"`
  return m.action || m.type
}

function _evCount(json) {
  try { return JSON.parse(json).length } catch { return '?' }
}

export function fieldStyle(t) {
  return { width:'100%', padding:'7px 10px', borderRadius:5, border:`1px solid ${t.border}`, background:t.elevated, color:t.text, fontSize:13, boxSizing:'border-box', outline:'none' }
}
export const solidBtn   = t => ({ padding:'7px 18px', borderRadius:6, border:'none', background:t.accent, color:'#fff', fontSize:13, fontWeight:600, cursor:'pointer' })
export const outlineBtn = t => ({ padding:'7px 18px', borderRadius:6, border:`1px solid ${t.border}`, background:'transparent', color:t.muted, fontSize:13, cursor:'pointer' })

// ── Recording UI ─────────────────────────────────────────────────────────────

function RecordingInput({ t, api, value, onChange }) {
  const [phase,    setPhase]    = useState('idle')   // 'idle' | 'recording' | 'done'
  const [count,    setCount]    = useState(0)
  const [errMsg,   setErrMsg]   = useState('')
  const [blink,    setBlink]    = useState(true)     // pulsing dot
  const pollRef   = useRef(null)
  const blinkRef  = useRef(null)

  const stopPoll = () => { clearInterval(pollRef.current); clearInterval(blinkRef.current) }
  useEffect(() => () => stopPoll(), [])

  const eventCount = value?.startsWith('[') ? _evCount(value) : 0

  const startRecording = async () => {
    setErrMsg('')
    setCount(0)
    const r = await api?.start_recording()
    if (!r?.ok) { setErrMsg(r?.error || 'Failed to start'); return }
    setPhase('recording')
    pollRef.current  = setInterval(async () => {
      const s = await api?.get_recording_status?.()
      if (s?.count >= 0) setCount(s.count)
    }, 150)
    blinkRef.current = setInterval(() => setBlink(b => !b), 500)
  }

  const stopRecording = async () => {
    stopPoll()
    const r = await api?.stop_recording()
    if (r?.ok && r?.events) {
      onChange(r.events)
      setCount(r.count ?? 0)
      setPhase('done')
    } else {
      setErrMsg(r?.error || 'Failed to stop')
      setPhase('idle')
    }
  }

  if (phase === 'recording') {
    return (
      <div style={{ background:'#1a0000', border:'1px solid #ef4444', borderRadius:6, padding:'10px 12px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:'#ef4444', opacity: blink ? 1 : 0.15, transition:'opacity 0.1s' }} />
          <span style={{ fontSize:13, color:'#ef4444', fontWeight:600 }}>Recording…</span>
          <span style={{ fontSize:12, color:'#94a3b8', marginLeft:'auto' }}>{count} events</span>
        </div>
        <div style={{ fontSize:11, color:'#94a3b8', marginBottom:10 }}>
          All keyboard input is being captured. Press your sequence, then stop.
        </div>
        <button onClick={stopRecording}
          style={{ width:'100%', padding:'7px', borderRadius:5, border:'none', background:'#ef4444', color:'#fff', fontSize:13, fontWeight:600, cursor:'pointer' }}>
          ■ Stop Recording
        </button>
      </div>
    )
  }

  return (
    <div style={{ background:t.elevated, border:`1px solid ${t.border}`, borderRadius:6, padding:'10px 12px' }}>
      <div style={{ fontSize:12, color: eventCount > 0 ? t.success : t.dim, marginBottom:10 }}>
        {eventCount > 0 ? `✓ ${eventCount} events recorded` : 'No recording yet'}
      </div>
      <button onClick={startRecording}
        style={{ width:'100%', padding:'7px', borderRadius:5, border:`1px solid #ef4444`, background:'transparent', color:'#ef4444', fontSize:13, fontWeight:600, cursor:'pointer' }}>
        ● {eventCount > 0 ? 'Re-record' : 'Start Recording'}
      </button>
      {errMsg && <div style={{ fontSize:11, color:'#ef4444', marginTop:6 }}>{errMsg}</div>}
    </div>
  )
}

// ── shared action input ───────────────────────────────────────────────────────

export function ActionInput({ t, api, type, value, onChange }) {
  const sel = opts => (
    <select value={value} onChange={e => onChange(e.target.value)} style={fieldStyle(t)}>
      <option value="">Select…</option>
      {opts.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
  if (type === 'Media Control')  return sel(MEDIA_OPTIONS)
  if (type === 'Function Key')   return sel(FKEY_OPTIONS)
  if (type === 'Modifier Key')   return sel(MODIFIER_OPTIONS)
  if (type === 'Mute App')       return <input value="Toggle mute for assigned app" readOnly style={{...fieldStyle(t), color:t.muted}} />
  if (type === 'Recorded')       return <RecordingInput t={t} api={api} value={value} onChange={onChange} />
  return (
    <input type="text" value={value} onChange={e => onChange(e.target.value)}
      placeholder={type === 'Type Text' ? 'Text to type…' : 'Key (a, space, enter…)'}
      style={fieldStyle(t)} />
  )
}

function MacroSection({ t, api, label, type, setType, action, setAction }) {
  return (
    <div style={{ marginBottom:16 }}>
      <div style={{ fontSize:11, fontWeight:600, color:t.muted, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:8 }}>{label}</div>
      <select value={type} onChange={e => { setType(e.target.value); setAction('') }}
        style={{ ...fieldStyle(t), marginBottom:8 }}>
        <option value="">— None —</option>
        {MACRO_TYPES.map(mt => <option key={mt} value={mt}>{mt}</option>)}
      </select>
      {type && <ActionInput t={t} api={api} type={type} value={action} onChange={setAction} />}
    </div>
  )
}

// ── modal ─────────────────────────────────────────────────────────────────────

export function MacroModal({ t, api, title, pressData, holdData, onSave, onClose, showHold=true }) {
  const [pressType,   setPressType]   = useState(pressData?.type   ?? '')
  const [pressAction, setPressAction] = useState(pressData?.action ?? '')
  const [holdType,    setHoldType]    = useState(holdData?.type    ?? '')
  const [holdAction,  setHoldAction]  = useState(holdData?.action  ?? '')

  const save = () => onSave(
    pressType ? { type:pressType, action:pressAction } : null,
    showHold  ? (holdType ? { type:holdType, action:holdAction } : null) : undefined,
  )

  return (
    <div style={{ position:'fixed', inset:0, zIndex:100, background:'rgba(0,0,0,0.6)', display:'flex', alignItems:'center', justifyContent:'center' }}
      onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        style={{ background:t.card, border:`1px solid ${t.border}`, borderRadius:10, padding:24, width:380, boxShadow:'0 20px 60px rgba(0,0,0,0.5)', maxHeight:'90vh', overflowY:'auto' }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
          <span style={{ fontSize:15, fontWeight:700 }}>{title}</span>
          <button onClick={onClose} style={{ background:'none', border:'none', color:t.muted, cursor:'pointer', fontSize:16 }}>✕</button>
        </div>
        <MacroSection t={t} api={api} label="Press"           type={pressType} setType={setPressType} action={pressAction} setAction={setPressAction} />
        {showHold && <MacroSection t={t} api={api} label="Hold (500 ms+)" type={holdType} setType={setHoldType} action={holdAction} setAction={setHoldAction} />}
        <div style={{ display:'flex', justifyContent:'flex-end', gap:8, marginTop:4 }}>
          <button onClick={onClose} style={outlineBtn(t)}>Cancel</button>
          <button onClick={save}    style={solidBtn(t)}>Save</button>
        </div>
      </div>
    </div>
  )
}
