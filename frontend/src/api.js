const BASE = '/api'

export async function fetchHealth() {
  const r = await fetch(`${BASE}/health`)
  return r.json()
}

export async function fetchStats() {
  const r = await fetch(`${BASE}/stats`)
  return r.json()
}

export async function fetchVisualizations() {
  const r = await fetch(`${BASE}/visualizations`)
  return r.json()
}

export async function predictImage(file) {
  const form = new FormData()
  form.append('file', file)
  const r = await fetch(`${BASE}/predict`, { method: 'POST', body: form })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function uploadImages(files, classLabel) {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  form.append('class_label', classLabel)
  const r = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function triggerRetrain() {
  const r = await fetch(`${BASE}/retrain`, { method: 'POST' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function fetchRetrainStatus() {
  const r = await fetch(`${BASE}/retrain/status`)
  return r.json()
}