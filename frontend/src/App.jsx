import { useState } from 'react'
import StatusMonitor from './components/StatusMonitor.jsx'
import Predict from './components/Predict.jsx'
import Visualizations from './components/Visualizations.jsx'
import Upload from './components/Upload.jsx'
import RecentPredictions from './components/RecentPredictions.jsx'
import RetrainPanel from './components/RetrainPanel.jsx'

const TABS = ['Monitor', 'Predict', 'Visualize', 'Upload', 'Retrain', 'History']

const styles = {
  shell: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    borderBottom: '1px solid var(--border)',
    padding: '0 2rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '60px',
    position: 'sticky',
    top: 0,
    background: 'var(--bg)',
    zIndex: 100,
  },
  logo: {
    fontFamily: 'var(--mono)',
    fontSize: '0.85rem',
    color: 'var(--accent)',
    letterSpacing: '0.15em',
    textTransform: 'uppercase',
  },
  nav: {
    display: 'flex',
    gap: '0.25rem',
  },
  tab: (active) => ({
    background: active ? 'var(--accent-dim)' : 'transparent',
    border: active ? '1px solid var(--accent)' : '1px solid transparent',
    color: active ? 'var(--accent)' : 'var(--muted)',
    fontFamily: 'var(--mono)',
    fontSize: '0.7rem',
    letterSpacing: '0.1em',
    padding: '0.4rem 0.9rem',
    cursor: 'pointer',
    borderRadius: '2px',
    textTransform: 'uppercase',
    transition: 'all 0.15s ease',
  }),
  main: {
    flex: 1,
    padding: '2rem',
    maxWidth: '1200px',
    width: '100%',
    margin: '0 auto',
  },
}

export default function App() {
  const [tab, setTab] = useState('Monitor')

  return (
    <div style={styles.shell}>
      <header style={styles.header}>
        <span style={styles.logo}>⬡ SatelliteAI // Terrain Classifier</span>
        <nav style={styles.nav}>
          {TABS.map(t => (
            <button key={t} style={styles.tab(tab === t)} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
      </header>
      <main style={styles.main}>
        {tab === 'Monitor'    && <StatusMonitor />}
        {tab === 'Predict'    && <Predict />}
        {tab === 'Visualize'  && <Visualizations />}
        {tab === 'Upload'     && <Upload />}
        {tab === 'Retrain'    && <RetrainPanel />}
        {tab === 'History'    && <RecentPredictions />}
      </main>
    </div>
  )
}