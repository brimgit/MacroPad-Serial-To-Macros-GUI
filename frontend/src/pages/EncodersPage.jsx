import { useState, useEffect, useRef, useCallback } from 'react'
import { MacroModal, macroLabel } from '../components/MacroModal'

const LED_MODES = ['default', 'solid', 'fade']
const EFFECTS   = ['Off', 'Breathe', 'Wave', 'Rainbow', 'Chase', 'Color Cycle', 'Sparkle']
const BTN_KEYS  = ['A', 'B', 'C', 'D']
const N = 10

// ── color helpers ─────────────────────────────────────────────────────────────
function rgbToHex([r,g,b]) { return '#'+[r,g,b].map(v=>v.toString(16).padStart(2,'0')).join('') }
function hexToRgb(h) { return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)] }
function lerp(a,b,t) { return a+(b-a)*t }
function lerpRgb(a,b,t) { return [lerp(a[0],b[0],t),lerp(a[1],b[1],t),lerp(a[2],b[2],t)] }
function css([r,g,b]) { return `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})` }
function hslRgb(h,s,l) {
  h/=360; s/=100; l/=100
  const f=n=>{ const k=(n+h*12)%12,a=s*Math.min(l,1-l); return l-a*Math.max(-1,Math.min(k-3,9-k,1)) }
  return [f(0)*255,f(8)*255,f(4)*255]
}
function baseRgb(i,mode,color,color2) {
  const frac=N>1?i/(N-1):0
  if(mode==='default') return lerpRgb([0,200,0],[200,0,0],frac)
  if(mode==='fade')    return lerpRgb(color,color2,frac)
  return [...color]
}

// ── idle effect ───────────────────────────────────────────────────────────────
function computeEffect(effect,mode,color,color2,t) {
  const leds = Array.from({length:N},(_,i)=>({rgb:baseRgb(i,mode,color,color2),br:1}))
  if(effect==='Off')        return leds.map(()=>({rgb:[20,30,45],br:1}))
  if(effect==='Breathe')  { const br=(Math.sin(t*.002)+1)/2; return leds.map(l=>({...l,br})) }
  if(effect==='Wave')       return leds.map((l,i)=>({...l,br:(Math.sin(t*.002+i*.75)+1)/2}))
  if(effect==='Rainbow')    return leds.map((_,i)=>({rgb:hslRgb(((i/N*360)+t*.05)%360,100,50),br:1}))
  if(effect==='Chase') {
    const span=N*2-2, raw=(t*.008)%span, pos=raw<N?raw:span-raw
    return leds.map((l,i)=>({...l,br:Math.max(0,1-Math.abs(i-pos)*.7)}))
  }
  if(effect==='Color Cycle') { const rgb=hslRgb((t*.06)%360,100,50); return leds.map(()=>({rgb,br:1})) }
  if(effect==='Sparkle') {
    const frame=Math.floor(t/90)
    return leds.map((l,i)=>{const on=((frame*11+i*7)%17)<4; return {rgb:on?l.rgb:[20,30,45],br:on?1:.3}})
  }
  return leds
}

// ── LED ring ──────────────────────────────────────────────────────────────────
function LEDRing({ mode, color, color2, effect, volume, muted, flashMuted }) {
  const [, setTick]  = useState(0)
  const [showVol, setShowVol] = useState(false)
  const volTimer = useRef(null)

  // RAF refs for idle-effect animation
  const rafRef   = useRef(null)
  const startRef = useRef(null)
  const tRef     = useRef(0)

  // ── muted-flash state machine (mirrors Python: continuous → 3 slow blinks) ─
  const flash = useRef({ state: 'idle', ledOn: true, lastEvent: 0, timer: null })
  const runActiveRef = useRef(null)
  const runFinalRef  = useRef(null)

  useEffect(() => {
    const f = flash.current
    const upd = () => setTick(t => t + 1)

    runFinalRef.current = (step = 0) => {
      if (step >= 6) { f.state = 'idle'; f.ledOn = true; upd(); return }
      f.ledOn = step % 2 === 0
      upd()
      f.timer = setTimeout(() => runFinalRef.current(step + 1), step % 2 === 0 ? 250 : 200)
    }

    runActiveRef.current = () => {
      if (f.state !== 'active') return
      if (performance.now() - f.lastEvent > 500) {
        f.state = 'final'
        runFinalRef.current(0)
        return
      }
      f.ledOn = !f.ledOn
      upd()
      f.timer = setTimeout(runActiveRef.current, 110)
    }
  }, [])

  // Cancel flash if unmuted
  useEffect(() => {
    if (!muted) {
      clearTimeout(flash.current.timer)
      flash.current.state = 'idle'
      flash.current.ledOn = true
    }
  }, [muted])

  // New muted-turn event → update timestamp; start thread if idle
  useEffect(() => {
    if (!flashMuted || !muted) return
    const f = flash.current
    f.lastEvent = performance.now()
    if (f.state === 'idle') {
      f.state = 'active'
      clearTimeout(f.timer)
      runActiveRef.current()
    }
  }, [flashMuted, muted])

  useEffect(() => () => clearTimeout(flash.current.timer), [])

  useEffect(() => {
    if (volume < 0 || muted) return
    setShowVol(true)
    clearTimeout(volTimer.current)
    volTimer.current = setTimeout(() => setShowVol(false), 2000)
    return () => clearTimeout(volTimer.current)
  }, [volume, muted])

  useEffect(() => {
    const animated = effect !== 'Off' && !showVol && !muted
    if (!animated) { cancelAnimationFrame(rafRef.current); startRef.current = null; return }
    const step = ts => {
      if (!startRef.current) startRef.current = ts
      tRef.current = ts - startRef.current
      setTick(n => n + 1)
      rafRef.current = requestAnimationFrame(step)
    }
    rafRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(rafRef.current)
  }, [effect, showVol, muted])

  const CX=50, CY=50, R=37, START_DEG=-135, SPAN=270
  const positions = Array.from({length:N},(_,i)=>{
    const rad=((START_DEG+(SPAN/(N-1))*i)*Math.PI)/180
    return {x:CX+R*Math.sin(rad), y:CY-R*Math.cos(rad)}
  })

  let ledColors
  if (muted) {
    const on = flash.current.state === 'idle' ? true : flash.current.ledOn
    ledColors = positions.map(() => ({ color: on ? css([220,0,0]) : css([18,0,0]), glow: on }))
  } else if (showVol && volume >= 0) {
    const lit = Math.round((volume/100)*N)
    ledColors = positions.map((_,i) => i < lit
      ? { color: css(baseRgb(i,mode,color,color2)), glow: true }
      : { color: css([20,30,45]), glow: false })
  } else {
    const states = computeEffect(effect,mode,color,color2,tRef.current)
    ledColors = states.map(({rgb,br})=>({ color:css(rgb.map(c=>c*br)), glow:br>.5 }))
  }

  const label = muted ? 'muted' : showVol && volume >= 0 ? `${volume}%` : effect === 'Off' ? 'off' : '~'

  return (
    <svg viewBox="0 0 100 100" width={128} height={128} style={{ display:'block', margin:'0 auto 6px' }}>
      {positions.map((pos,i)=>{
        const {color:fill,glow}=ledColors[i]
        return (
          <g key={i}>
            {glow && <circle cx={pos.x} cy={pos.y} r={7} fill={fill} opacity={0.2}/>}
            <circle cx={pos.x} cy={pos.y} r={3.8} fill={fill}/>
          </g>
        )
      })}
      <circle cx={CX} cy={CY} r={21} fill="#1c2438" stroke="#253040" strokeWidth="1.5"/>
      <circle cx={CX} cy={CY} r={15} fill="#161c2a" stroke="#1e2a3a" strokeWidth="1"/>
      <text x={CX} y={CY+4} textAnchor="middle"
        fontSize={label.length>4?7:9} fontFamily="monospace" fontWeight="700"
        fill={muted?'#ef4444':showVol&&volume>=0?'#94a3b8':'#4b5675'}>
        {label}
      </text>
    </svg>
  )
}

// ── button macro row ──────────────────────────────────────────────────────────
function BtnMacroRow({ t, label, macro, onClick }) {
  return (
    <button onClick={onClick} style={{
      display:'flex', alignItems:'center', justifyContent:'space-between',
      width:'100%', padding:'6px 8px', marginBottom:4,
      background:t.elevated, border:`1px solid ${t.border}`,
      borderRadius:5, cursor:'pointer', textAlign:'left',
      transition:'border-color 0.1s',
    }}
      onMouseEnter={e=>e.currentTarget.style.borderColor=t.accent}
      onMouseLeave={e=>e.currentTarget.style.borderColor=t.border}>
      <span style={{ fontSize:10, fontWeight:700, color:t.dim, minWidth:30, textTransform:'uppercase' }}>{label}</span>
      <span style={{ fontSize:11, color:macro?t.text:t.dim, flex:1, marginLeft:8, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
        {macro ? macroLabel(macro) : '— empty —'}
      </span>
      <span style={{ fontSize:10, color:t.accent, marginLeft:6, flexShrink:0 }}>edit</span>
    </button>
  )
}

// ── encoder card ──────────────────────────────────────────────────────────────
function EncoderCard({ t, idx, encoder, audioApps, usedApps, volume, muted, flashMuted, macros, api, onRefresh, onChange }) {
  const [local,   setLocal]   = useState({...encoder})
  const [dirty,   setDirty]   = useState(false)
  const [editBtn, setEditBtn] = useState(null)  // 'press' | 'hold' | null

  useEffect(() => { setLocal({...encoder}); setDirty(false) }, [encoder])
  const upd = (k,v) => { setLocal(p=>({...p,[k]:v})); setDirty(true) }

  const btnKey  = BTN_KEYS[idx]
  const pressM  = macros?.[`KP:${btnKey}`]
  const holdM   = macros?.[`KP:${btnKey}:HOLD`]

  const saveBtnMacro = async (press, hold) => {
    setEditBtn(null)
    await (press ? api?.set_macro(`KP:${btnKey}`,      press.type, press.action) : api?.delete_macro(`KP:${btnKey}`))
    await (hold  ? api?.set_macro(`KP:${btnKey}:HOLD`, hold.type,  hold.action)  : api?.delete_macro(`KP:${btnKey}:HOLD`))
    onRefresh?.()
  }

  const fld = {
    width:'100%', padding:'6px 8px', borderRadius:5,
    border:`1px solid ${t.border}`, background:t.elevated,
    color:t.text, fontSize:12, cursor:'pointer',
  }
  const rowSt = { marginBottom:12 }
  const lblSt = { fontSize:11, fontWeight:600, color:t.muted, textTransform:'uppercase', letterSpacing:'0.07em', marginBottom:5, display:'block' }

  return (
    <div style={{
      background:t.card,
      border:`1px solid ${dirty?t.accent:muted?'#ef444466':t.border}`,
      borderRadius:10, padding:'16px 16px 14px',
      transition:'border-color 0.2s',
    }}>
      <div style={{ fontSize:13, fontWeight:700, marginBottom:10, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        Encoder {idx+1}
        {muted && <span style={{ fontSize:10, color:'#ef4444', fontWeight:600, letterSpacing:'0.05em' }}>MUTED</span>}
      </div>

      <LEDRing
        mode={local.mode||'default'} color={local.color||[6,182,212]} color2={local.color2||[255,100,0]}
        effect={local.effect||'Off'} volume={volume??-1} muted={muted} flashMuted={flashMuted}
      />

      {/* Volume app */}
      <div style={rowSt}>
        <label style={lblSt}>Volume App</label>
        <select value={local.app||''} onChange={e=>upd('app',e.target.value)} style={fld}>
          <option value="">— None —</option>
          {audioApps.map(a => {
            const takenBy = usedApps?.[a]
            const conflict = takenBy !== undefined && takenBy !== idx
            return <option key={a} value={a}>{conflict ? `${a}  ← Enc ${takenBy+1}` : a}</option>
          })}
        </select>
        {local.app && usedApps?.[local.app] !== undefined && usedApps[local.app] !== idx && (
          <div style={{ fontSize:11, color:'#f59e0b', marginTop:4 }}>
            ⚠ Will be removed from Encoder {usedApps[local.app]+1} on save
          </div>
        )}
      </div>

      {/* LED mode */}
      <div style={rowSt}>
        <label style={lblSt}>LED Mode</label>
        <select value={local.mode||'default'} onChange={e=>upd('mode',e.target.value)} style={fld}>
          {LED_MODES.map(m=><option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      {/* Colors — hidden for default mode */}
      {local.mode!=='default' && (
        <div style={{ display:'flex', gap:12, marginBottom:12 }}>
          <div style={{flex:1}}>
            <label style={lblSt}>Color 1</label>
            <div style={{ display:'flex', gap:6, alignItems:'center' }}>
              <input type="color" value={rgbToHex(local.color||[6,182,212])} onChange={e=>upd('color',hexToRgb(e.target.value))}
                style={{ width:32, height:28, padding:0, border:'none', cursor:'pointer', background:'none' }}/>
              <span style={{ fontSize:11, color:t.muted, fontFamily:'monospace' }}>{rgbToHex(local.color||[6,182,212])}</span>
            </div>
          </div>
          {local.mode==='fade' && (
            <div style={{flex:1}}>
              <label style={lblSt}>Color 2</label>
              <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                <input type="color" value={rgbToHex(local.color2||[255,100,0])} onChange={e=>upd('color2',hexToRgb(e.target.value))}
                  style={{ width:32, height:28, padding:0, border:'none', cursor:'pointer', background:'none' }}/>
                <span style={{ fontSize:11, color:t.muted, fontFamily:'monospace' }}>{rgbToHex(local.color2||[255,100,0])}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Idle effect */}
      <div style={rowSt}>
        <label style={lblSt}>Idle Effect</label>
        <select value={local.effect||'Off'} onChange={e=>upd('effect',e.target.value)} style={fld}>
          {EFFECTS.map(e=><option key={e} value={e}>{e}</option>)}
        </select>
      </div>

      {/* Encoder button macros */}
      <div style={{ borderTop:`1px solid ${t.border}`, marginTop:4, paddingTop:12, marginBottom:12 }}>
        <div style={{ fontSize:10, fontWeight:600, color:t.dim, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:8 }}>
          Button ({btnKey})
        </div>
        <BtnMacroRow t={t} label="Press" macro={pressM} onClick={()=>setEditBtn('press')} />
        <BtnMacroRow t={t} label="Hold"  macro={holdM}  onClick={()=>setEditBtn('hold')} />
      </div>

      <button onClick={()=>{ onChange(idx,local); setDirty(false) }} disabled={!dirty}
        style={{
          width:'100%', padding:'7px', borderRadius:6, border:'none',
          background:dirty?t.accent:t.border, color:dirty?'#fff':t.dim,
          fontSize:12, fontWeight:600, cursor:dirty?'pointer':'not-allowed', transition:'background 0.15s',
        }}>
        {dirty?'Apply Changes':'Saved'}
      </button>

      {editBtn && (
        <MacroModal
          t={t} api={api}
          title={`Encoder ${idx+1} Button`}
          pressData={pressM}
          holdData={holdM}
          onSave={saveBtnMacro}
          onClose={()=>setEditBtn(null)}
        />
      )}
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────
const DEFAULT_ENC = {app:'',mode:'default',color:[6,182,212],color2:[255,100,0],blend_start:0,effect:'Off'}

export default function EncodersPage({ t, encoders, volumes, muted, flashMuted, macros, api, onEncoderChange, onEncodersReset, onRefresh }) {
  const [audioApps, setAudioApps] = useState([])

  useEffect(() => {
    api?.get_audio_apps().then(apps => {
      if (Array.isArray(apps)) setAudioApps(apps)
    }).catch(()=>{})
  }, [api])

  // Map app → encoder index for conflict detection
  const usedApps = {}
  encoders?.forEach((enc, i) => { if (enc?.app) usedApps[enc.app] = i })

  const handleChange = useCallback(async (idx, config) => {
    const r = await api?.set_encoder(idx, config)
    if (r?.encoders) {
      // API resolved a conflict — refresh all encoder states at once
      onEncodersReset?.(r.encoders)
    } else {
      onEncoderChange?.(idx, config)
    }
  }, [api, onEncoderChange, onEncodersReset])

  return (
    <div>
      <div style={{ marginBottom:24 }}>
        <h1 style={{ fontSize:20, fontWeight:700, marginBottom:4 }}>Encoders</h1>
        <p style={{ fontSize:13, color:t.muted }}>Configure LED, volume app, and button macros per encoder.</p>
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:16, maxWidth:680 }}>
        {Array.from({length:4},(_,i)=>(
          <EncoderCard
            key={i} t={t} idx={i}
            encoder={encoders?.[i]??DEFAULT_ENC}
            audioApps={audioApps}
            usedApps={usedApps}
            volume={volumes?.[i]??-1}
            muted={muted?.[i]??false}
            flashMuted={flashMuted?.[i]??0}
            macros={macros}
            api={api}
            onRefresh={onRefresh}
            onChange={handleChange}
          />
        ))}
      </div>
    </div>
  )
}
