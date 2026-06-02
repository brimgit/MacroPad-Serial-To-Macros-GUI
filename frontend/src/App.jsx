import { useState, useEffect, useCallback, useRef } from 'react'
import Sidebar      from './components/Sidebar'
import MacrosPage   from './pages/MacrosPage'
import EncodersPage from './pages/EncodersPage'
import SettingsPage from './pages/SettingsPage'
import UploadPage   from './pages/UploadPage'
import TestPage     from './pages/TestPage'

// Receive events pushed from Python via evaluate_js
window.__macropadEvent = (event, payload) => {
  window.dispatchEvent(new CustomEvent('macropad:' + event, { detail: payload }))
}

const pyapi = () => window.pywebview?.api ?? null

const DARK_THEME = {
  bg: '#0d1117', sidebar: '#090e1a', card: '#161c2a', elevated: '#1c2438',
  hover: '#222d42', border: '#1e2a3a', borderLight: '#283548',
  text: '#f1f5f9', muted: '#94a3b8', dim: '#4b5675', accent: '#06b6d4',
  success: '#10b981', danger: '#ef4444',
}
const LIGHT_THEME = {
  bg: '#e8eaed', sidebar: '#dde0e5', card: '#f1f3f5', elevated: '#e0e3e8',
  hover: '#d4d8de', border: '#c4c8cf', borderLight: '#b8bcc4',
  text: '#111827', muted: '#4b5563', dim: '#9ca3af', accent: '#0284c7',
  success: '#16a34a', danger: '#dc2626',
}

const DEFAULT_ENCODERS = Array.from({ length: 4 }, () => ({
  app: '', mode: 'default', color: [6, 182, 212], color2: [255, 100, 0],
  blend_start: 0, effect: 'Off',
}))

export default function App() {
  const [page,          setPage]          = useState('Macros')
  const [dark,          setDark]          = useState(true)
  const [connected,     setConnected]     = useState(false)
  const [port,          setPort]          = useState('')
  const [macros,        setMacros]        = useState({})
  const [encoders,      setEncoders]      = useState(DEFAULT_ENCODERS)
  const [encVolumes,    setEncVolumes]    = useState([-1, -1, -1, -1])
  const [encMuted,      setEncMuted]      = useState([false, false, false, false])
  const [encFlash,      setEncFlash]      = useState([0, 0, 0, 0])   // inc to trigger flash
  const [profiles,      setProfiles]      = useState(['Default'])
  const [activeProfile, setActive]        = useState('Default')
  const [settings,      setSettings]      = useState({})
  const [ready,         setReady]         = useState(false)

  const t           = dark ? DARK_THEME : LIGHT_THEME
  const initDone    = useRef(false)

  // Init — guard against double-call (pywebviewready event + fallback timeout)
  useEffect(() => {
    const init = async () => {
      if (initDone.current) return
      initDone.current = true
      const api = pyapi()
      if (!api) { setReady(true); return }
      const data = await api.startup()
      setMacros(data.macros    ?? {})
      setEncoders(data.encoders ?? DEFAULT_ENCODERS)
      setProfiles(data.profiles ?? ['Default'])
      setActive(data.active    ?? 'Default')
      setSettings(data.settings ?? {})
      setReady(true)
    }
    if (window.pywebview) {
      init()
    } else {
      window.addEventListener('pywebviewready', init, { once: true })
      setTimeout(init, 800)   // fallback: only runs if event never fires
    }
  }, [])

  // Live events from Python
  useEffect(() => {
    const onConn = (e) => { setConnected(e.detail.connected); setPort(e.detail.port ?? '') }
    const onTurn = (e) => {
      const { id, pct, muted } = e.detail
      if (muted) {
        setEncFlash(prev => { const n=[...prev]; n[id]=n[id]+1; return n })
      } else if (pct >= 0) {
        setEncVolumes(prev => { const n=[...prev]; n[id]=pct; return n })
      }
    }
    const onMute = (e) => {
      const { id, muted } = e.detail
      setEncMuted(prev => { const n=[...prev]; n[id]=muted; return n })
    }
    window.addEventListener('macropad:connection',   onConn)
    window.addEventListener('macropad:encoder_turn', onTurn)
    window.addEventListener('macropad:mute_change',  onMute)
    return () => {
      window.removeEventListener('macropad:connection',   onConn)
      window.removeEventListener('macropad:encoder_turn', onTurn)
      window.removeEventListener('macropad:mute_change',  onMute)
    }
  }, [])

  const refreshMacros = useCallback(async () => {
    const m = await pyapi()?.get_macros()
    if (m) setMacros(m)
  }, [])

  const handleEncoderChange = useCallback((idx, config) => {
    setEncoders(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], ...config }
      return next
    })
  }, [])

  const handleEncodersReset = useCallback((newList) => {
    setEncoders(newList)
  }, [])

  if (!ready) return (
    <div style={{
      height: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#0d1117',
      color: '#94a3b8', fontFamily: 'Segoe UI,sans-serif', fontSize: 14,
    }}>
      Loading MacroPad…
    </div>
  )

  return (
    <div style={{
      display: 'flex', height: '100vh',
      background: t.bg, color: t.text,
      fontFamily: "'Segoe UI',system-ui,sans-serif", fontSize: 13,
      overflow: 'hidden',
    }}>
      <Sidebar
        t={t} page={page} setPage={setPage} dark={dark} setDark={setDark}
        connected={connected} port={port}
        profiles={profiles} activeProfile={activeProfile}
        onSwitch={async (name) => {
          const r = await pyapi()?.switch_profile(name)
          setActive(name)
          if (r?.macros)   setMacros(r.macros)
          if (r?.encoders) setEncoders(r.encoders)
        }}
        onNew={async (name) => {
          await pyapi()?.new_profile(name)
          const p = await pyapi()?.get_profiles()
          if (p) { setProfiles(p.names); setActive(p.active) }
        }}
        onDelete={async (name) => {
          await pyapi()?.delete_profile(name)
          const p = await pyapi()?.get_profiles()
          if (p) { setProfiles(p.names); setActive(p.active) }
        }}
      />

      <main style={{ flex: 1, overflowY: 'auto', padding: '32px 36px' }}>
        {page === 'Macros'   && <MacrosPage   t={t} macros={macros}     api={pyapi()} onRefresh={refreshMacros} />}
        {page === 'Encoders' && <EncodersPage t={t} encoders={encoders} volumes={encVolumes} muted={encMuted} flashMuted={encFlash} macros={macros} api={pyapi()} onEncoderChange={handleEncoderChange} onEncodersReset={handleEncodersReset} onRefresh={refreshMacros} />}
        {page === 'Settings' && <SettingsPage t={t} settings={settings} api={pyapi()} connected={connected} port={port} onSave={setSettings} />}
        {page === 'Upload'   && <UploadPage   t={t} api={pyapi()} />}
        {page === 'Test'     && <TestPage     t={t} />}
      </main>
    </div>
  )
}
