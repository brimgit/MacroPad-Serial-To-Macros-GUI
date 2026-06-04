import { useState, useEffect } from 'react'

export default function SettingsPage({ t, settings, api, connected, port, onSave }) {
  const [ports,          setPorts]          = useState([])
  const [selPort,        setSelPort]        = useState(settings.port ?? 'COM6')
  const [baud,           setBaud]           = useState(settings.baud_rate ?? '115200')
  const [brightness,     setBrightness]     = useState(settings.brightness_pct ?? 10)
  const [ledTimeout,     setLedTimeout]     = useState(settings.enc_led_timeout ?? 2)
  const [effectSpeed,    setEffectSpeed]    = useState(settings.effect_speed_ms ?? 10)
  const [saving,         setSaving]         = useState(false)
  const [status,         setStatus]         = useState('')
  const [updateInfo,     setUpdateInfo]     = useState(null)
  const [checking,       setChecking]       = useState(false)
  // New state
  const [startupEnabled, setStartupEnabled] = useState(false)
  const [shiftKey,       setShiftKey]       = useState('')
  const [activeProfile,  setActiveProfile]  = useState('')
  const [triggerApps,    setTriggerApps]    = useState([])
  const [availableApps,  setAvailableApps]  = useState([])
  const [newTriggerApp,  setNewTriggerApp]  = useState('')

  useEffect(() => {
    api?.get_ports().then(p => { if (Array.isArray(p)) setPorts(p) }).catch(() => {})
  }, [api])

  useEffect(() => {
    if (!api) return
    setChecking(true)
    api.check_for_update()
      .then(r => { setUpdateInfo(r); setChecking(false) })
      .catch(() => setChecking(false))
    // Load new settings
    api.get_startup?.().then(r => { if (r?.ok) setStartupEnabled(r.enabled) }).catch(() => {})
    api.get_shift_key?.().then(k => { if (k !== undefined) setShiftKey(k || '') }).catch(() => {})
    api.get_profiles?.().then(p => {
      if (!p?.active) return
      setActiveProfile(p.active)
      api.get_trigger_apps(p.active).then(apps => {
        if (Array.isArray(apps)) setTriggerApps(apps)
      }).catch(() => {})
    }).catch(() => {})
    api.get_audio_apps?.().then(apps => {
      if (Array.isArray(apps)) setAvailableApps(apps)
    }).catch(() => {})
  }, [api])

  const refreshPorts = async () => {
    const p = await api?.get_ports()
    if (Array.isArray(p)) setPorts(p)
  }

  const handleConnect = async () => {
    setStatus('Connecting…')
    await api?.connect(selPort, parseInt(baud))
    setStatus('')
  }

  const handleDisconnect = async () => {
    await api?.disconnect?.()
    setStatus('')
  }

  const handleBrightness = async (val) => {
    setBrightness(val)
    await api?.set_brightness(val)
  }

  const handleSaveSettings = async () => {
    setSaving(true)
    const s = { ...settings, port: selPort, baud_rate: baud, brightness_pct: brightness, enc_led_timeout: ledTimeout, effect_speed_ms: effectSpeed }
    await api?.save_settings(s)
    onSave?.(s)
    setStatus('Settings saved')
    setSaving(false)
    setTimeout(() => setStatus(''), 2000)
  }

  const handleExport = async () => {
    const data = await api?.export_profile?.(settings.active ?? 'Default')
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a'); a.href = url
    a.download = `${data.name ?? 'profile'}.json`; a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = async () => {
    const input = document.createElement('input')
    input.type = 'file'; input.accept = '.json'
    input.onchange = async (e) => {
      const file = e.target.files[0]
      if (!file) return
      const text = await file.text()
      try {
        const data = JSON.parse(text)
        const r = await api?.import_profile?.(data)
        if (r?.ok) setStatus(`Imported "${r.name}"`)
        else setStatus('Import failed')
        setTimeout(() => setStatus(''), 3000)
      } catch {
        setStatus('Invalid JSON file')
        setTimeout(() => setStatus(''), 3000)
      }
    }
    input.click()
  }

  // ── Trigger apps ─────────────────────────────────────────────────────────
  const addTriggerApp = async () => {
    const app = newTriggerApp.trim()
    if (!app || triggerApps.includes(app)) return
    const next = [...triggerApps, app]
    setTriggerApps(next)
    setNewTriggerApp('')
    await api?.set_trigger_apps?.(activeProfile, next)
  }

  const removeTriggerApp = async (app) => {
    const next = triggerApps.filter(a => a !== app)
    setTriggerApps(next)
    await api?.set_trigger_apps?.(activeProfile, next)
  }

  const handleToggleStartup = async () => {
    const r = await api?.set_startup?.(!startupEnabled)
    if (r?.ok) setStartupEnabled(r.enabled)
  }

  const handleShiftKey = async (key) => {
    setShiftKey(key)
    await api?.set_shift_key?.(key)
  }

  const section      = { marginBottom: 28 }
  const sectionTitle = { fontSize:11, fontWeight:600, color:t.dim, textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:12, paddingBottom:6, borderBottom:`1px solid ${t.border}` }
  const row          = { display:'flex', gap:10, alignItems:'center', marginBottom:10 }
  const lbl          = { fontSize:12, color:t.muted, width:100, flexShrink:0 }
  const sel          = { flex:1, padding:'6px 10px', borderRadius:5, border:`1px solid ${t.border}`, background:t.elevated, color:t.text, fontSize:13, cursor:'pointer' }

  return (
    <div style={{ maxWidth: 520 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize:20, fontWeight:700, marginBottom:4 }}>Settings</h1>
        {status && <p style={{ fontSize:12, color:t.success, marginTop:4 }}>{status}</p>}
      </div>

      {/* Serial */}
      <div style={section}>
        <div style={sectionTitle}>Serial Connection</div>
        <div style={row}>
          <span style={lbl}>Port</span>
          <select value={selPort} onChange={e => setSelPort(e.target.value)} style={sel}>
            {ports.length === 0 && <option value={selPort}>{selPort}</option>}
            {ports.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button onClick={refreshPorts} title="Refresh ports"
            style={{ padding:'6px 10px', borderRadius:5, border:`1px solid ${t.border}`, background:'transparent', color:t.muted, cursor:'pointer', fontSize:13 }}>↺</button>
        </div>
        <div style={row}>
          <span style={lbl}>Baud rate</span>
          <select value={baud} onChange={e => setBaud(e.target.value)} style={sel}>
            {['9600','19200','38400','57600','115200','230400'].map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:connected?t.success:t.danger, flexShrink:0 }} />
          <span style={{ fontSize:12, color:t.muted, flex:1 }}>{connected ? `Connected to ${port}` : 'Not connected'}</span>
          {connected
            ? <button onClick={handleDisconnect} style={{ padding:'6px 14px', borderRadius:6, border:`1px solid ${t.danger}`, background:'transparent', color:t.danger, cursor:'pointer', fontSize:13 }}>Disconnect</button>
            : <button onClick={handleConnect}    style={{ padding:'6px 14px', borderRadius:6, border:'none', background:t.accent, color:'#fff', cursor:'pointer', fontSize:13, fontWeight:600 }}>Connect</button>}
        </div>
      </div>

      {/* LED */}
      <div style={section}>
        <div style={sectionTitle}>LED</div>
        <div style={row}>
          <span style={lbl}>Brightness</span>
          <input type="range" min={0} max={100} value={brightness} onChange={e => setBrightness(Number(e.target.value))} onMouseUp={() => handleBrightness(brightness)} onTouchEnd={() => handleBrightness(brightness)} style={{ flex:1 }} />
          <span style={{ fontSize:12, color:t.muted, width:32, textAlign:'right' }}>{brightness}%</span>
        </div>
        <div style={row}>
          <span style={lbl}>Enc LED off</span>
          <select value={ledTimeout} onChange={e => { const v=Number(e.target.value); setLedTimeout(v); api?.set_enc_led_timeout?.(v) }} style={sel}>
            <option value={2}>2 seconds</option>
            <option value={5}>5 seconds</option>
            <option value={10}>10 seconds</option>
          </select>
        </div>
        <div style={row}>
          <span style={lbl}>Effect speed</span>
          <select value={effectSpeed} onChange={e => { const v=Number(e.target.value); setEffectSpeed(v); api?.set_effect_speed?.(v) }} style={sel}>
            <option value={5}>5 ms — Ultra</option>
            <option value={10}>10 ms — Smooth</option>
            <option value={20}>20 ms — Medium</option>
            <option value={33}>33 ms — Standard</option>
            <option value={50}>50 ms — Light</option>
          </select>
        </div>
      </div>

      {/* Profile import/export */}
      <div style={section}>
        <div style={sectionTitle}>Profile Import / Export</div>
        <div style={{ display:'flex', gap:10 }}>
          <button onClick={handleExport} style={{ flex:1, padding:'8px', borderRadius:6, border:`1px solid ${t.border}`, background:'transparent', color:t.text, cursor:'pointer', fontSize:13 }}>↓ Export current profile</button>
          <button onClick={handleImport} style={{ flex:1, padding:'8px', borderRadius:6, border:`1px solid ${t.border}`, background:'transparent', color:t.text, cursor:'pointer', fontSize:13 }}>↑ Import profile…</button>
        </div>
      </div>

      {/* Updates */}
      <div style={section}>
        <div style={sectionTitle}>Updates</div>
        <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
          <button onClick={async () => { setChecking(true); setUpdateInfo(null); const r = await api?.check_for_update().catch(() => null); setUpdateInfo(r); setChecking(false) }}
            disabled={checking}
            style={{ padding:'7px 16px', borderRadius:6, border:`1px solid ${t.border}`, background:'transparent', color:t.text, fontSize:13, cursor:checking?'not-allowed':'pointer', opacity:checking?0.6:1 }}>
            {checking ? 'Checking…' : '↻ Check for Updates'}
          </button>
          {updateInfo?.update_available && (
            <div style={{ display:'flex', alignItems:'center', gap:8 }}>
              <span style={{ fontSize:13, color:t.warning, fontWeight:600 }}>⚠ Update available — v{updateInfo.latest}</span>
              <span style={{ fontSize:12, color:t.muted }}>(current: v{updateInfo.current})</span>
              <a href={updateInfo.repo_url} target="_blank" rel="noreferrer"
                style={{ fontSize:12, color:t.accent, textDecoration:'none' }}
                onClick={e => { e.preventDefault(); window.open?.(updateInfo.repo_url) }}>
                View on GitHub ↗
              </a>
            </div>
          )}
          {updateInfo?.ok && !updateInfo.update_available && (
            <span style={{ fontSize:13, color:t.success }}>✓ Up to date — v{updateInfo.current}</span>
          )}
          {updateInfo?.ok === false && (
            <span style={{ fontSize:13, color:t.danger }}>✗ {updateInfo.error}</span>
          )}
        </div>
      </div>

      {/* Startup with Windows */}
      <div style={section}>
        <div style={sectionTitle}>System</div>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <div style={{ fontSize:13, color:t.text, marginBottom:2 }}>Start with Windows</div>
            <div style={{ fontSize:12, color:t.muted }}>Launch MacroPad automatically on login</div>
          </div>
          <button onClick={handleToggleStartup}
            style={{ width:44, height:24, borderRadius:12, border:'none', background:startupEnabled?t.accent:t.border, cursor:'pointer', position:'relative', padding:0, flexShrink:0 }}>
            <div style={{ width:18, height:18, borderRadius:'50%', background:'#fff', position:'absolute', top:3, left:startupEnabled?23:3, transition:'left 0.15s' }} />
          </button>
        </div>
      </div>

      <button onClick={handleSaveSettings} disabled={saving}
        style={{ padding:'9px 24px', borderRadius:7, border:'none', background:t.accent, color:'#fff', fontSize:13, fontWeight:600, cursor:'pointer' }}>
        {saving ? 'Saving…' : 'Save Settings'}
      </button>
    </div>
  )
}
