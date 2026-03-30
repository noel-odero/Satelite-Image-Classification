const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const HF_MODEL_URL = (import.meta.env.VITE_HF_MODEL_URL || '').trim()
const HF_TOKEN = (import.meta.env.VITE_HF_TOKEN || '').trim()

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

function normalizeLabel(label) {
  return String(label || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
}

function normalizeHfOutput(payload) {
  let rows = []

  if (Array.isArray(payload)) {
    rows = Array.isArray(payload[0]) ? payload[0] : payload
  } else if (payload && Array.isArray(payload.labels) && Array.isArray(payload.scores)) {
    rows = payload.labels.map((label, i) => ({ label, score: payload.scores[i] }))
  }

  if (!rows.length) {
    throw new Error('Unexpected Hugging Face response format.')
  }

  const sorted = rows
    .map((r) => ({ label: normalizeLabel(r.label), score: Number(r.score) || 0 }))
    .sort((a, b) => b.score - a.score)

  const allProbabilities = Object.fromEntries(
    sorted.map((r) => [r.label, r.score])
  )

  return {
    predicted_class: sorted[0].label,
    confidence: sorted[0].score,
    all_probabilities: allProbabilities,
  }
}

async function inferWithHuggingFace(file, retries = 2) {
  if (!HF_MODEL_URL) {
    throw new Error('VITE_HF_MODEL_URL is not configured.')
  }

  const headers = { 'Content-Type': file.type || 'application/octet-stream' }
  if (HF_TOKEN) headers.Authorization = `Bearer ${HF_TOKEN}`

  const response = await fetch(HF_MODEL_URL, {
    method: 'POST',
    headers,
    body: file,
  })

  const text = await response.text()
  let payload
  try {
    payload = JSON.parse(text)
  } catch {
    payload = text
  }

  if (!response.ok) {
    const message = payload?.error || text || 'Hugging Face inference failed.'

    if (
      retries > 0 &&
      typeof message === 'string' &&
      message.toLowerCase().includes('loading')
    ) {
      const waitMs = Math.ceil((Number(payload?.estimated_time) || 2) * 1000)
      await new Promise((resolve) => setTimeout(resolve, waitMs))
      return inferWithHuggingFace(file, retries - 1)
    }

    throw new Error(message)
  }

  return {
    filename: file.name,
    ...normalizeHfOutput(payload),
  }
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
  if (HF_MODEL_URL) {
    return inferWithHuggingFace(file)
  }

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