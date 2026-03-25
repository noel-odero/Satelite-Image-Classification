import { useEffect, useState } from 'react'
import { fetchVisualizations } from '../api.js'

const s = {
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.5rem' },
  card: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', overflow: 'hidden' },
  img: { width: '100%', display: 'block' },
  caption: { padding: '0.75rem 1rem', fontFamily: 'var(--mono)', fontSize: '0.65rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase' },
  section: { fontFamily: 'var(--sans)', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' },
  empty: { fontFamily: 'var(--mono)', fontSize: '0.75rem', color: 'var(--muted)', textAlign: 'center', padding: '3rem' },
}

const CAPTIONS = {
  'class_distribution': 'Feature 01 — Class distribution across terrain types reveals mild imbalance in Desert samples',
  'sample_images':      'Feature 02 — Visual texture patterns per class confirm CNN discriminability',
  'mean_intensity':     'Feature 03 — Mean pixel intensity separates Desert (bright) from Water (dark)',
  'training_curves':    'Training & validation accuracy/loss across epochs — two-phase fine-tuning visible',
  'confusion_matrix':   'Confusion matrix — per-class prediction breakdown on held-out test set',
}

function getCaption(url) {
  const key = Object.keys(CAPTIONS).find(k => url.includes(k))
  return key ? CAPTIONS[key] : url.split('/').pop()
}

export default function Visualizations() {
  const [urls, setUrls] = useState([])

  useEffect(() => {
    fetchVisualizations().then(d => setUrls(d.visualizations || []))
  }, [])

  return (
    <div>
      <p style={s.section}>Dataset & Model Visualizations</p>
      {urls.length === 0
        ? <p style={s.empty}>No visualizations found. Place PNG files in static/visualizations/</p>
        : (
          <div style={s.grid}>
            {urls.map(url => (
              <div key={url} style={s.card}>
                <img src={url} alt={url} style={s.img} />
                <div style={s.caption}>{getCaption(url)}</div>
              </div>
            ))}
          </div>
        )
      }
    </div>
  )
}