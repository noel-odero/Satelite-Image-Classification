# Deployment Guide - Option B: Separate Frontend & Backend

This guide covers deploying the frontend and backend as separate Render services while keeping them properly connected.

## Architecture

- **Backend Service**: `satelite-image-classification.onrender.com` (Python FastAPI)
- **Frontend Service**: `satelite-image-classification-3.onrender.com` (React + Vite)

## Setup Instructions

### 1. Backend Service (Existing)

Your backend is already deployed. Ensure it has:

**Environment Variables**:
- `DATABASE_URL` (PostgreSQL)
- `USE_HF_INFERENCE=true` (if using Hugging Face)
- `HF_MODEL_URL` (Hugging Face endpoint)
- `HF_TOKEN` (if required)

**Verification**:
```bash
curl https://satelite-image-classification.onrender.com/health
```

### 2. Frontend Service (New Configuration)

Create a new "Web Service" on Render pointing to the same repository.

**Build Command**:
```bash
npm install && npm run build
```

**Start Command** (optional, only if serving statically):
```bash
npm run preview
```

**Environment Variables** (CRITICAL):

When configuring the frontend service, set this environment variable during the build phase:

```
VITE_API_BASE_URL=https://satelite-image-classification.onrender.com
```

This tells Vite to embed the backend URL into the built application at build time.

**Important**: Without this, the frontend defaults to `/api` which only works when frontend and backend are on the same domain.

### 3. Initialization: Add Training Data

Before you can trigger retraining, the backend needs sample training data in:

```
data/retrain/{class_label}/image1.jpg
data/retrain/{class_label}/image2.jpg
```

The subdirectories must exist for each class: `cloudy`, `desert`, `green_area`, `water`

**Via API (Upload Tab)**:
1. Go to the Upload tab in the UI
2. Select images for each class (cloudy, desert, green_area, water)
3. Upload them
4. The directory structure will be created automatically

**OR Via Git** (included sample images):
```
data/retrain/
├── cloudy/
│   └── sample_cloudy.png
├── desert/
│   └── sample_desert.png
├── green_area/
│   └── sample_green.png
└── water/
    └── sample_water.png
```

Without data in these directories, the `/retrain` endpoint returns a 400 error.

## CORS Configuration

Your FastAPI backend already has CORS properly configured:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This allows requests from any origin. The frontend and backend can communicate freely.

## Testing the Setup

### 1. Verify Backend
```bash
curl https://satelite-image-classification.onrender.com/health
```

Should return:
```json
{
  "status": "online",
  "model": "satellite_classifier",
  "inference_provider": "huggingface",
  "timestamp": "2026-03-30T12:34:56.789012",
  "retrain_running": false
}
```

### 2. Test Predict Endpoint
```bash
curl -X POST https://satelite-image-classification.onrender.com/predict \
  -F "file=@sample_image.jpg"
```

### 3. Test Retrain (after uploading training data)
```bash
curl -X POST https://satelite-image-classification.onrender.com/retrain
```

### 4. Check Retrain Status
```bash
curl https://satelite-image-classification.onrender.com/retrain/status
```

## Troubleshooting

### Issue: "No uploaded data found for retraining" (400 error)

**Cause**: No subdirectories with training images in `data/retrain/`

**Fix**:
1. Use the Upload tab to upload training images for each class
2. Or commit sample images to git in `data/retrain/{class}/`

### Issue: CORS error on fetch requests

**Cause**: Usually means the API_BASE_URL is still `/api`

**Check**:
1. In browser DevTools, check the actual request URL
2. It should be `https://satelite-image-classification.onrender.com/retrain`
3. NOT `/api/retrain`

**Fix**: Ensure `VITE_API_BASE_URL` is set as an environment variable in Render frontend service

### Issue: Visualization images return 404

**Cause**: Static files haven't been generated

**Fix**: These are generated during model training. After successful retraining, they'll appear in:
```
static/visualizations/
├── class_distribution.png
├── mean_intensity.png
└── sample_images.png
```

## Local Development

For local testing with separate frontend/backend:

**Terminal 1 (Backend)**:
```bash
cd api
uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend)**:
```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Environment Variables Summary

| Variable | Service | Example | Purpose |
|----------|---------|---------|---------|
| `DATABASE_URL` | Backend | `postgresql://...` | PostgreSQL connection |
| `USE_HF_INFERENCE` | Backend | `true` | Use Hugging Face instead of local model |
| `HF_MODEL_URL` | Backend | `https://hf.space/...` | Hugging Face inference endpoint |
| `HF_TOKEN` | Backend | `hf_xxxxx` | Hugging Face API token (if required) |
| `VITE_API_BASE_URL` | Frontend | `https://satelite-image-classification.onrender.com` | Backend URL for API calls |

**Note**: The `VITE_` prefix variables are embedded at **build time** in Vite. They must be set before running `npm run build`.
