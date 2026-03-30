# Deployment Guide - What Was Actually Done

This document records the exact deployment path used for this project.

## Current Deployment Setup

- Backend service: satelite-image-classification.onrender.com (FastAPI)
- Frontend service: satelite-image-classification-3.onrender.com (React + Vite)
- Frontend and backend are deployed as separate Render services.

## Hugging Face Model Deployment

- The trained model is also deployed on Hugging Face.
- Hugging Face endpoint in use: https://missnoel-satellite-classifier-api.hf.space/predict
- Backend inference is configured to use Hugging Face by setting `USE_HF_INFERENCE=true`.
- Requests flow is: Frontend -> Render backend API -> Hugging Face model endpoint.

## Problem That Was Seen

- Retrain requests from the frontend failed.
- Browser showed CORS-related errors and failed fetches.
- Retrain endpoint also returned 400 when no retraining folders/data existed.

## Root Cause

- Frontend build was using the default API base `/api` from `frontend/src/api.js`.
- With separate domains, `/api` does not point to the backend service.

## What Was Changed

Only Render environment configuration was changed (no backend code change required for this fix).

### Frontend Render Environment

Set this variable on the frontend service:

```env
VITE_API_BASE_URL=https://satelite-image-classification.onrender.com
```

Then redeploy the frontend service so Vite rebuilds with the value.

### Backend Render Environment

Backend environment values in use:

```env
DATABASE_URL=postgresql://...
USE_HF_INFERENCE=true
HF_MODEL_URL=https://missnoel-satellite-classifier-api.hf.space/predict
HF_TOKEN=
HF_TIMEOUT_SECONDS=60
HF_MAX_RETRIES=2
HF_RETRY_BACKOFF_SECONDS=1.0
HF_RETRY_BACKOFF_MULTIPLIER=2.0
ENABLE_WEB_RETRAIN=false
DB_CONNECT_RETRIES=60
DB_CONNECT_DELAY_SECONDS=2
```

This confirms production inference is routed through Hugging Face (not local model loading).

Retraining on the web service is intentionally disabled by default to prevent CPU/RAM spikes causing 502 downtime on free-tier instances. If needed, run retraining in a separate worker/job service.

## Fallback Behavior

- Current setup has no automatic runtime failover from Hugging Face to local model.
- If Hugging Face is unavailable or times out, prediction requests return an API error.
- To switch to local inference, set `USE_HF_INFERENCE=false` and redeploy backend with local model files available.

## Retraining Data Source Used

Training data was uploaded through the Upload tab in the frontend UI.

Expected folder structure created by uploads:

```text
data/retrain/cloudy/
data/retrain/desert/
data/retrain/green_area/
data/retrain/water/
```

If these folders are empty/missing, `POST /retrain` returns 400.

## Quick Verification

1. Confirm frontend calls backend domain (not `/api`) in browser Network tab.
2. Check backend health:

```bash
curl https://satelite-image-classification.onrender.com/health
```

3. Trigger retrain:

```bash
curl -X POST https://satelite-image-classification.onrender.com/retrain
```

4. Poll retrain status:

```bash
curl https://satelite-image-classification.onrender.com/retrain/status
```

## Notes

- `VITE_` environment variables are baked in at build time.
- Changing `VITE_API_BASE_URL` requires a frontend redeploy.
