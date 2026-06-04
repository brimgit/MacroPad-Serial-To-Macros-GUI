const pyapi = () => window.pywebview?.api ?? null

export default function TitleBar({ t }) {
  const btn = (onClick, label, hoverColor) => (
    <button
      onClick={onClick}
      style={{
        width: 46, height: 32, border: 'none', background: 'transparent',
        color: t.muted, fontSize: 12, cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        WebkitAppRegion: 'no-drag',
        transition: 'background 0.1s, color 0.1s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = hoverColor; if (hoverColor !== '#e81123') e.currentTarget.style.color = t.text }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = t.muted }}
    >
      {label}
    </button>
  )

  return (
    <div style={{
      height: 32, flexShrink: 0,
      background: t.sidebar,
      borderBottom: `1px solid ${t.border}`,
      display: 'flex', alignItems: 'center',
      WebkitAppRegion: 'drag',
      userSelect: 'none',
    }}>
      {/* Drag area fills the space */}
      <div style={{ flex: 1, height: '100%' }} />

      {/* Window controls — no-drag so clicks register */}
      <div style={{ display: 'flex', WebkitAppRegion: 'no-drag' }}>
        {btn(() => pyapi()?.minimize_window(),      '—',  t.hover)}
        {btn(() => pyapi()?.toggle_maximize_window(), '□', t.hover)}
        {btn(() => pyapi()?.close_window(),          '✕',  '#e81123')}
      </div>
    </div>
  )
}
