import { useState, useRef } from 'react'
import { predictImage } from '../api.js'

const s = {
  wrap: { maxWidth: 560, margin: '0 auto' },
  dropzone: (drag) => ({
    border: `2px dashed ${drag ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '4px',
    padding: '3rem 2rem',
    textAlign: 'center',
    cursor: 'pointer',
    background: drag ? 'var(--accent-dim)' : 'var(--surface)',
    transition: 'all 0.2s ease',
    marginBottom: '1.5rem',
  }),
  preview: { width: '100%', maxHeight: 280, objectFit: 'cover', borderRadius: '3px', marginBottom: '1.5rem', border: '1px solid var(--border)' },
  btn: (disabled) => ({
    width: '100%', padding: '0.85rem', background: disabled ? 'var(--border)' : 'var(--accent)',
    color: disabled ? 'var(--muted)' : '#000', border: 'none', borderRadius: '3px',
    fontFamily: 'var(--mono)', fontSize: '0.8rem', fontWeight: 700,
    letterSpacing: '0.1em', cursor: disabled ? 'not-allowed' : 'pointer',
    textTransform: 'uppercase', transition: 'all 0.15s ease',
  }),
  result: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1.5rem', marginTop: '1.5rem' },
  className: { fontFamily: 'var(--mono)', fontSize: '1.8rem', color: 'var(--accent)', fontWeight: 700, marginBottom: '0.5rem' },
  confidence: { fontFamily: 'var(--mono)', fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '1rem' },
  barWrap: { marginBottom: '0.5rem' },
  barLabel: { fontFamily: 'var(--mono)', fontSize: '0.7rem', color: 'var(--muted)', display: 'flex', justifyContent: 'space-between', marginBottom: '3px' },
  barTrack: { height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' },
  barFill: (pct) => ({ height: '100%', width: `${pct * 100}%`, background: 'var(--accent)', borderRadius: 3, transition: 'width 0.5s ease' }),
  error: { color: 'var(--danger)', fontFamily: 'var(--mono)', fontSize: '0.75rem', marginTop: '1rem' },
  section: { fontFamily: 'var(--sans)', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' },
}

export default function Predict() {
  const [file, setFile]       = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [drag, setDrag]       = useState(false)
  const inputRef = useRef()

  const handleFile = (f) => {
    setFile(f)
    setResult(null)
    setError(null)
    setPreview(URL.createObjectURL(f))
  }

  const handleDrop = (e) => {
    e.preventDefault(); setDrag(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handlePredict = async () => {
    if (!file) return
    setLoading(true); setError(null)
    try {
      const res = await predictImage(file)
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.wrap}>
      <p style={s.section}>Single Image Prediction</p>

      <div
        style={s.dropzone(drag)}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
      >
        <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }}
          onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])} />
        <p style={{ fontFamily: 'var(--mono)', fontSize: '0.75rem', color: 'var(--muted)' }}>
          {file ? file.name : 'DROP IMAGE HERE OR CLICK TO BROWSE'}
        </p>
      </div>

      {preview && <img src={preview} alt="preview" style={s.preview} />}

      <button style={s.btn(!file || loading)} disabled={!file || loading} onClick={handlePredict}>
        {loading ? 'ANALYZING...' : 'RUN PREDICTION'}
      </button>

      {error && <p style={s.error}>ERROR: {error}</p>}

      {result && (
        <div style={s.result}>
          <div style={s.className}>{result.predicted_class.toUpperCase()}</div>
          <div style={s.confidence}>CONFIDENCE: {(result.confidence * 100).toFixed(1)}%</div>
          {Object.entries(result.all_probabilities).map(([cls, prob]) => (
            <div key={cls} style={s.barWrap}>
              <div style={s.barLabel}><span>{cls}</span><span>{(prob * 100).toFixed(1)}%</span></div>
              <div style={s.barTrack}><div style={s.barFill(prob)} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}