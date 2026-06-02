import { useState, useEffect, useRef } from 'react'

const BOARDS = [
  'esp32:esp32:esp32',
  'esp32:esp32:esp32wrover',
  'esp32:esp32:esp32da',
]

export default function UploadPage({ t, api }) {
  const [inoPath,   setInoPath]   = useState('')
  const [cliPath,   setCliPath]   = useState('C:\\Program Files\\Arduino CLI\\arduino-cli.exe')
  const [action,    setAction]    = useState('upload')
  const [board,     setBoard]     = useState(BOARDS[0])
  const [port,      setPort]      = useState('')
  const [ports,     setPorts]     = useState([])
  const [log,       setLog]       = useState([])
  const [running,   setRunning]   = useState(false)
  const logRef = useRef(null)

  useEffect(() => {
    api?.get_ports().then(p => {
      if (Array.isArray(p) && p.length > 0) { setPorts(p); setPort(p[0]) }
    }).catch(() => {})
  }, [api])

  useEffect(() => {
    const onLog  = e => setLog(prev => [...prev, { ...e.detail, ts: Date.now() }])
    const onDone = e => {
      setRunning(false)
      setLog(prev => [...prev, {
        line: e.detail.ok ? '✓ Done!' : `✗ Failed: ${e.detail.error ?? ''}`,
        ok: e.detail.ok, ts: Date.now(),
      }])
    }
    window.addEventListener('macropad:upload_log',  onLog)
    window.addEventListener('macropad:upload_done', onDone)
    return () => {
      window.removeEventListener('macropad:upload_log',  onLog)
      window.removeEventListener('macropad:upload_done', onDone)
    }
  }, [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  const handleExecute = async () => {
    if (!inoPath) { alert('Select a .ino file first.'); return }
    if (!port)    { alert('Select a port.'); return }
    setLog([])
    setRunning(true)
    await api?.upload_firmware(inoPath, cliPath, action, board, port)
  }

  const refreshPorts = async () => {
    const p = await api?.get_ports()
    if (Array.isArray(p)) { setPorts(p); if (p.length > 0 && !port) setPort(p[0]) }
  }

  const field = {
    width: '100%', padding: '7px 10px', borderRadius: 5,
    border: `1px solid ${t.border}`, background: t.elevated,
    color: t.text, fontSize: 13, boxSizing: 'border-box',
  }
  const lbl = { fontSize: 12, color: t.muted, display: 'block', marginBottom: 5 }

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Upload Firmware</h1>
        <p style={{ fontSize: 13, color: t.muted }}>Compile and flash firmware to your ESP32 MacroPad.</p>
      </div>

      <div style={{ background: t.card, border: `1px solid ${t.border}`, borderRadius: 10, padding: 20, marginBottom: 20 }}>

        {/* .ino file */}
        <div style={{ marginBottom: 14 }}>
          <label style={lbl}>.ino project file</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={inoPath} onChange={e => setInoPath(e.target.value)}
              placeholder="C:\path\to\sketch\sketch.ino"
              style={{ ...field, flex: 1 }}
            />
            <button
              onClick={() => {
                const input = document.createElement('input')
                input.type = 'file'; input.accept = '.ino'
                input.onchange = e => setInoPath(e.target.files[0]?.path ?? e.target.files[0]?.name ?? '')
                input.click()
              }}
              style={{ padding: '7px 12px', borderRadius: 5, border: `1px solid ${t.border}`, background: 'transparent', color: t.text, cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap' }}
            >
              Browse…
            </button>
          </div>
        </div>

        {/* Arduino CLI path */}
        <div style={{ marginBottom: 14 }}>
          <label style={lbl}>Arduino CLI path</label>
          <input value={cliPath} onChange={e => setCliPath(e.target.value)} style={field} />
        </div>

        {/* Action + Board + Port */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div>
            <label style={lbl}>Action</label>
            <select value={action} onChange={e => setAction(e.target.value)} style={field}>
              <option value="upload">Upload</option>
              <option value="verify">Verify only</option>
            </select>
          </div>
          <div>
            <label style={lbl}>Board</label>
            <select value={board} onChange={e => setBoard(e.target.value)} style={field}>
              {BOARDS.map(b => <option key={b} value={b}>{b.split(':').pop()}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Port</label>
            <div style={{ display: 'flex', gap: 4 }}>
              <select value={port} onChange={e => setPort(e.target.value)} style={{ ...field, flex: 1 }}>
                {ports.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <button onClick={refreshPorts} title="Refresh"
                style={{ padding: '7px 8px', borderRadius: 5, border: `1px solid ${t.border}`, background: 'transparent', color: t.muted, cursor: 'pointer' }}>
                ↺
              </button>
            </div>
          </div>
        </div>

        <button
          onClick={handleExecute}
          disabled={running}
          style={{
            width: '100%', padding: '9px', borderRadius: 7, border: 'none',
            background: running ? t.border : t.accent,
            color: running ? t.dim : '#fff',
            fontSize: 13, fontWeight: 600,
            cursor: running ? 'not-allowed' : 'pointer',
          }}
        >
          {running ? 'Running…' : action === 'upload' ? '⬆ Compile & Upload' : '✓ Verify'}
        </button>
      </div>

      {/* Log output */}
      {log.length > 0 && (
        <div
          ref={logRef}
          style={{
            background: '#0a0d14', border: `1px solid ${t.border}`,
            borderRadius: 8, padding: '12px 14px',
            fontFamily: 'Consolas, monospace', fontSize: 12,
            maxHeight: 240, overflowY: 'auto',
          }}
        >
          {log.map((entry, i) => (
            <div key={i} style={{ color: entry.ok === false ? '#ef4444' : '#94a3b8', marginBottom: 3, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {entry.line}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
