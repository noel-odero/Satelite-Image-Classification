import { useEffect, useState } from 'react'
import { fetchHealth, fetchStats } from '../api.js'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const s = {
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' },
  card: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1.5rem' },
  label: { fontFamily: 'var(--mono)', fontSize: '0.65rem', color: 'var(--muted)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: '0.5rem' },
  value: { fontFamily: 'var(--mono)', fontSize: '1.6rem', color: 'var(--accent)', fontWeight: 700 },
  dot: (online) => ({ width: 8, height: 8, borderRadius: '50%', background: online ? 'var(--accent)' : 'var(--danger)', display: 'inline-block', marginRight: '0.5rem', boxShadow: online ? '0 0 8px var(--accent)' : '0 0 8px var(--danger)' }),
  section: { fontFamily: 'var(--sans)', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' },
  chartWrap: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1.5rem' },
}

const COLORS = ['#00ff88', '#00ccff', '#ff6b35', '#a855f7']

export default function StatusMonitor() {
  const [health, setHealth] = useState(null)
  const [stats, setStats]   = useState(null)

  useEffect(() => {
    const load = async () => {
      try { setHealth(await fetchHealth()) } catch { setHealth({ status: 'offline' }) }
      try { setStats(await fetchStats()) } catch {}
    }
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  const online = health?.status === 'online'
  const predData = stats?.prediction_counts?.map(p => ({ name: p.predicted_class, count: Number(p.count) })) || []

  return (
    <div>
      <p style={s.section}>System Status</p>
      <div style={s.grid}>
        <div style={s.card}>
          <div style={s.label}>API Status</div>
          <div style={s.value}>
            <span style={s.dot(online)} />
            {online ? 'ONLINE' : 'OFFLINE'}
          </div>
        </div>
        <div style={s.card}>
          <div style={s.label}>Total Predictions</div>
          <div style={s.value}>{stats?.total_predictions ?? '—'}</div>
        </div>
        <div style={s.card}>
          <div style={s.label}>Total Retrains</div>
          <div style={s.value}>{stats?.total_retrains ?? '—'}</div>
        </div>
        <div style={s.card}>
          <div style={s.label}>Retrain Running</div>
          <div style={{ ...s.value, color: health?.retrain_running ? 'var(--warning)' : 'var(--accent)' }}>
            {health?.retrain_running ? 'YES' : 'IDLE'}
          </div>
        </div>
      </div>

      {predData.length > 0 && (
        <div style={s.chartWrap}>
          <p style={s.section}>Predictions by Class</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={predData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <XAxis dataKey="name" tick={{ fill: '#4a5568', fontFamily: 'var(--mono)', fontSize: 11 }} />
              <YAxis tick={{ fill: '#4a5568', fontFamily: 'var(--mono)', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', fontFamily: 'var(--mono)', fontSize: 12 }} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {predData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}