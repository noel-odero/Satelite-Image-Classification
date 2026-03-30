import { useState, useRef, useEffect } from 'react'
import { uploadImages, fetchStats } from '../api.js'

const CLASSES = ['cloudy', 'desert', 'green_area', 'water']

const s = {
  section: { fontFamily: 'var(--sans)', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' },
  row: { display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' },
  classBtn: (active) => ({
    padding: '0.5rem 1.2rem', fontFamily: 'var(--mono)', fontSize: '0.7rem',
    letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer', borderRadius: '2px',
    background: active ? 'var(--accent)' : 'var(--surface)',
    color: active ? '#000' : 'var(--muted)',
    border: active ? '1px solid var(--accent)' : '1px solid var(--border)',
    transition: 'all 0.15s',
  }),
  dropzone: (drag) => ({
    border: `2px dashed ${drag ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '4px', padding: '2.5rem 2rem', textAlign: 'center',
    cursor: 'pointer', background: drag ? 'var(--accent-dim)' : 'var(--surface)',
    transition: 'all 0.2s ease', marginBottom: '1.5rem',
  }),
  fileList: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1rem', marginBottom: '1.5rem', maxHeight: 160, overflowY: 'auto' },
  fileItem: { fontFamily: 'var(--mono)', fontSize: '0.7rem', color: 'var(--muted)', padding: '0.2rem 0', borderBottom: '1px solid var(--border)' },
  btn: (disabled) => ({
    width: '100%', padding: '0.85rem',
    background: disabled ? 'var(--border)' : 'var(--accent)',
    color: disabled ? 'var(--muted)' : '#000', border: 'none', borderRadius: '3px',
    fontFamily: 'var(--mono)', fontSize: '0.8rem', fontWeight: 700,
    letterSpacing: '0.1em', cursor: disabled ? 'not-allowed' : 'pointer', textTransform: 'uppercase',
  }),
  result: { marginTop: '1rem', fontFamily: 'var(--mono)', fontSize: '0.75rem', color: 'var(--accent)', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1rem' },
  error: { color: 'var(--danger)', fontFamily: 'var(--mono)', fontSize: '0.75rem', marginTop: '1rem' },
}

export default function Upload() {
  const [classLabel, setClassLabel] = useState(() => {
    const persisted = localStorage.getItem('retrain.classLabel')
    return CLASSES.includes(persisted) ? persisted : CLASSES[0]
  })
  const [files, setFiles]           = useState([])
  const [drag, setDrag]             = useState(false)
  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState(null)
  const [error, setError]           = useState(null)
  const [uploadCounts, setUploadCounts] = useState({})
  const inputRef = useRef()

  const loadUploadCounts = async () => {
    try {
      const stats = await fetchStats()
      const counts = Object.fromEntries(
        (stats.upload_counts || []).map((row) => [row.class_label, Number(row.count) || 0])
      )
      setUploadCounts(counts)
    } catch {
      setUploadCounts({})
    }
  }

  useEffect(() => {
    localStorage.setItem('retrain.classLabel', classLabel)
  }, [classLabel])

  useEffect(() => {
    loadUploadCounts()
  }, [])

  const addFiles = (newFiles) => {
    setFiles(prev => [...prev, ...Array.from(newFiles)])
    setResult(null); setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault(); setDrag(false)
    addFiles(e.dataTransfer.files)
  }

  const handleUpload = async () => {
    if (!files.length) return
    setLoading(true); setError(null)
    try {
      const res = await uploadImages(files, classLabel)
      setResult(res); setFiles([])
      loadUploadCounts()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p style={s.section}>Upload Images for Retraining</p>

      <p style={{ fontFamily: 'var(--mono)', fontSize: '0.7rem', color: 'var(--muted)', marginBottom: '0.75rem', letterSpacing: '0.05em' }}>SELECT CLASS LABEL</p>
      <div style={s.row}>
        {CLASSES.map(c => (
          <button key={c} style={s.classBtn(classLabel === c)} onClick={() => setClassLabel(c)}>{c}</button>
        ))}
      </div>

      <div style={{ ...s.fileList, marginTop: '-0.3rem' }}>
        {CLASSES.map((c) => (
          <div key={c} style={s.fileItem}>
            {c.toUpperCase()} STORED ON SERVER: {uploadCounts[c] ?? 0}
          </div>
        ))}
      </div>

      <div
        style={s.dropzone(drag)}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
      >
        <input ref={inputRef} type="file" accept="image/*" multiple style={{ display: 'none' }}
          onChange={(e) => addFiles(e.target.files)} />
        <p style={{ fontFamily: 'var(--mono)', fontSize: '0.75rem', color: 'var(--muted)' }}>
          DROP IMAGES HERE OR CLICK TO BROWSE
        </p>
        <p style={{ fontFamily: 'var(--mono)', fontSize: '0.65rem', color: 'var(--muted)', marginTop: '0.5rem' }}>
          Multiple files supported
        </p>
      </div>

      {files.length > 0 && (
        <div style={s.fileList}>
          {files.map((f, i) => <div key={i} style={s.fileItem}>↳ {f.name}</div>)}
        </div>
      )}

      <p style={{ fontFamily: 'var(--mono)', fontSize: '0.66rem', color: 'var(--muted)', marginBottom: '1rem' }}>
        Note: selected local files clear on browser refresh, but uploaded files remain persisted on the server/database.
      </p>

      <button style={s.btn(!files.length || loading)} disabled={!files.length || loading} onClick={handleUpload}>
        {loading ? 'UPLOADING...' : `UPLOAD ${files.length || ''} IMAGES TO ${classLabel.toUpperCase()}`}
      </button>

      {error && <p style={s.error}>ERROR: {error}</p>}
      {result && (
        <div style={s.result}>
          ✓ UPLOADED: {result.uploaded} &nbsp;|&nbsp; SKIPPED: {result.skipped} &nbsp;|&nbsp; CLASS: {result.class_label}
        </div>
      )}
    </div>
  )
}