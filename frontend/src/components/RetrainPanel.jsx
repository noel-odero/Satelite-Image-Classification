import { useState, useEffect, useRef } from 'react'
import { triggerRetrain, fetchRetrainStatus } from '../api.js'

const s = {
  section: { fontFamily: 'var(--sans)', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' },
  wrap: { maxWidth: 560, margin: '0 auto' },
  info: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1.5rem', marginBottom: '1.5rem', fontFamily: 'var(--mono)', fontSize: '0.72rem', color: 'var(--muted)', lineHeight: 1.8 },
  btn: (disabled) => ({
    width: '100%', padding: '1rem',
    background: disabled ? 'var(--border)' : 'var(--accent)',
    color: disabled ? 'var(--muted)' : '#000', border: 'none', borderRadius: '3px',
    fontFamily: 'var(--mono)', fontSize: '0.85rem', fontWeight: 700,
    letterSpacing: '0.15em', cursor: disabled ? 'not-allowed' : 'pointer',
    textTransform: 'uppercase', marginBottom: '1.5rem',
  }),
  status: (running) => ({
    background: 'var(--surface)', border: `1px solid ${running ? 'var(--warning)' : 'var(--border)'}`,
    borderRadius: '4px', padding: '1.5rem',
  }),
  statusLabel: { fontFamily: 'var(--mono)', fontSize: '0.65rem', color: 'var(--muted)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: '0.5rem' },
  statusValue: (running) => ({ fontFamily: 'var(--mono)', fontSize: '1.2rem', color: running ? 'var(--warning)' : 'var(--accent)', fontWeight: 700, marginBottom: '1rem' }),
  metric: { display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--mono)', fontSize: '0.72rem', padding: '0.3rem 0', borderBottom: '1px solid var(--border)', color: 'var(--muted)' },
  metricVal: { color: 'var(--accent)' },
  error: { color: 'var(--danger)', fontFamily: 'var(--mono)', fontSize: '0.75rem', marginTop: '1rem' },
}

export default function RetrainPanel() {
  const [status, setStatus]   = useState({ running: false, last_result: null })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const pollRef = useRef(null)

  const poll = async () => {
    try {
      const s = await fetchRetrainStatus()
      setStatus(s)
      if (!s.running && pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch {}
  }

  useEffect(() => { poll(); return () => { if (pollRef.current) clearInterval(pollRef.current) } }, [])

  const handleRetrain = async () => {
    setLoading(true); setError(null)
    try {
      await triggerRetrain()
      pollRef.current = setInterval(poll, 3000)
      poll()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const result = status.last_result

  return (
    <div style={s.wrap}>
      <p style={s.section}>Model Retraining</p>

      <div style={s.info}>
        → Retraining uses images uploaded via the Upload tab as new training data.<br />
        → The existing model is used as a pretrained base and fine-tuned for 5 epochs.<br />
        → Retraining runs in the background — the API stays responsive.<br />
        → In production, retraining may be disabled on web instances to avoid service outages.<br />
        → Poll status updates every 3 seconds automatically.
      </div>

      <button
        style={s.btn(loading || status.running)}
        disabled={loading || status.running}
        onClick={handleRetrain}
      >
        {status.running ? '⟳ RETRAINING IN PROGRESS...' : 'TRIGGER RETRAINING'}
      </button>

      {error && <p style={s.error}>ERROR: {error}</p>}

      <div style={s.status(status.running)}>
        <div style={s.statusLabel}>Current Status</div>
        <div style={s.statusValue(status.running)}>
          {status.running ? 'RUNNING' : result?.status === 'error' ? 'FAILED' : result ? 'COMPLETED' : 'IDLE'}
        </div>

        {result && result.status === 'success' && (
          <>
            {[
              ['Timestamp',        result.timestamp],
              ['Epochs Run',       result.epochs_run],
              ['Train Accuracy',   `${(result.final_train_accuracy * 100).toFixed(2)}%`],
              ['Val Accuracy',     `${(result.final_val_accuracy * 100).toFixed(2)}%`],
              ['Train Loss',       result.final_train_loss],
              ['Val Loss',         result.final_val_loss],
            ].map(([k, v]) => (
              <div key={k} style={s.metric}>
                <span>{k}</span><span style={s.metricVal}>{v}</span>
              </div>
            ))}
          </>
        )}

        {result && result.status === 'error' && (
          <p style={s.error}>RETRAIN ERROR: {result.message}</p>
        )}
      </div>
    </div>
  )
}