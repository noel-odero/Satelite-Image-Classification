const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

function getBackendRoot() {
  if (!/^https?:\/\//i.test(API_BASE)) return ''
  return API_BASE
    .replace(/\/+$/, '')
    .replace(/\/api$/, '')
}

export function resolveVisualizationUrl(url) {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url

  const root = getBackendRoot()
  if (!root) return url

  if (url.startsWith('/')) return `${root}${url}`
  return `${root}/${url}`
}

export async function fetchHealth() {
  const r = await fetch(`${API_BASE}/health`)
  return r.json()
}

export async function fetchStats() {
  const r = await fetch(`${API_BASE}/stats`)
  return r.json()
}

export async function fetchVisualizations() {
  const r = await fetch(`${API_BASE}/visualizations`)
  return r.json()
}

export async function predictImage(file) {
  const form = new FormData()
  form.append('file', file)
  const r = await fetch(`${API_BASE}/predict`, { method: 'POST', body: form })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function uploadImages(files, classLabel) {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  form.append('class_label', classLabel)
  const r = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function triggerRetrain() {
  const r = await fetch(`${API_BASE}/retrain`, { method: 'POST' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function fetchRetrainStatus() {
  const r = await fetch(`${API_BASE}/retrain/status`)
  return r.json()
}