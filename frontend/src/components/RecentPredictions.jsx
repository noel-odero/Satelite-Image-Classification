import { useEffect, useState } from 'react'
import { fetchStats } from '../api.js'

const s = {
  section: { fontFamily: 'var(--sans)', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { fontFamily: 'var(--mono)', fontSize: '0.65rem', color: 'var(--muted)', letterSpacing: '0.15em', textTransform: 'uppercase', padding: '0.6rem 1rem', textAlign: 'left', borderBottom: '1px solid var(--border)', background: 'var(--surface)' },
  td: { fontFamily: 'var(--mono)', fontSize: '0.72rem', color: 'var(--text)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)' },
  badge: (cls) => {
    const colors = { cloudy: '#00ccff', desert: '#ffa502', green_area: '#00ff88', water: '#a855f7' }
    return { background: `${colors[cls] || '#fff'}22`, color: colors[cls] || '#fff', padding: '0.2rem 0.6rem', borderRadius: '2px', fontFamily: 'var(--mono)', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase' }
  },
  empty: { fontFamily: 'var(--mono)', fontSize: '0.75rem', color: 'var(--muted)', textAlign: 'center', padding: '3rem' },
  wrap: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', overflow: 'hidden' },
}

export default function RecentPredictions() {
  const [rows, setRows]     = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats()
      .then(d => setRows(d.recent_predictions || []))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <p style={s.section}>Recent Predictions</p>
      <div style={s.wrap}>
        {loading
          ? <p style={s.empty}>Loading...</p>
          : rows.length === 0
          ? <p style={s.empty}>No predictions yet. Run a prediction first.</p>
          : (
            <table style={s.table}>
              <thead>
                <tr>
                  {['Filename', 'Predicted Class', 'Confidence', 'Timestamp'].map(h => (
                    <th key={h} style={s.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td style={s.td}>{r.filename || '—'}</td>
                    <td style={s.td}><span style={s.badge(r.predicted_class)}>{r.predicted_class}</span></td>
                    <td style={s.td}>{(r.confidence * 100).toFixed(1)}%</td>
                    <td style={s.td}>{new Date(r.predicted_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>
    </div>
  )
}