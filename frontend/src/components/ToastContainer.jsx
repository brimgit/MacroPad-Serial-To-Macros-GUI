import { useState, useEffect, useCallback } from 'react'

const TYPE_COLOR = {
  success: '#10b981',
  error:   '#ef4444',
  warning: '#f59e0b',
  info:    '#06b6d4',
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t))
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 280)
  }, [])

  useEffect(() => {
    const handler = (e) => {
      const { id, message, type = 'info' } = e.detail
      const duration = type === 'error' || type === 'warning' ? 5000 : 3000
      setToasts(prev => [...prev.slice(-3), { id, message, type, exiting: false }])
      setTimeout(() => dismiss(id), duration)
    }
    window.addEventListener('app:toast', handler)
    return () => window.removeEventListener('app:toast', handler)
  }, [dismiss])

  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20,
      display: 'flex', flexDirection: 'column', gap: 8,
      zIndex: 9999, pointerEvents: 'none',
    }}>
      {toasts.map(t => (
        <div key={t.id}
          className={t.exiting ? 'toast-exit' : 'toast-enter'}
          onClick={() => dismiss(t.id)}
          style={{
            display: 'flex', alignItems: 'center',
            background: '#161c2a',
            border: '1px solid #1e2a3a',
            borderLeft: `3px solid ${TYPE_COLOR[t.type] ?? TYPE_COLOR.info}`,
            borderRadius: 6,
            padding: '9px 14px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.45)',
            maxWidth: 300, minWidth: 160,
            cursor: 'pointer', pointerEvents: 'auto',
          }}
        >
          <span style={{ fontSize: 13, color: '#f1f5f9', lineHeight: 1.4 }}>{t.message}</span>
        </div>
      ))}
    </div>
  )
}
