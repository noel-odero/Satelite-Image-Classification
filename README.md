# Satellite Image Classification

End-to-end machine learning system for classifying satellite images into 4 terrain classes, with a full-stack web app, retraining workflow, deployment, and load testing support.

## Essential Links

- YouTube Demo: `ADD_YOUTUBE_DEMO_LINK_HERE`
- Live Railway URL: `ADD_RAILWAY_URL_HERE`
- [Live Frontend](https://satelite-image-classification-3.onrender.com) (Render): 
- [Live Backend API](https://satelite-image-classification.onrender.com) (Render): 
- Hugging Face [Model Endpoint](https://missnoel-satellite-classifier-api.hf.space/predict): 

## Project Description

This project classifies satellite imagery into the following 4 classes:

- `cloudy`
- `desert`
- `green_area`
- `water`

It provides:

- Single-image prediction (`/predict`)
- Bulk upload for retraining (`/upload`)
- Background retraining trigger and status polling (`/retrain`, `/retrain/status`)
- Dataset and prediction analytics (`/stats`)
- Visualization gallery (`/visualizations` + `/static/visualizations/*.png`)

### Dataset

- Dataset Name: **RSI-CB256 Satellite Image Classification**
- Source: **Kaggle**
- Kaggle Path used in notebook: `datasets/mahmoudreda55/satellite-image-classification`
- Image size noted in notebook intro: `256x256`
- Total images noted in notebook intro: `5,631`

[Kaggle link](https://www.kaggle.com/datasets/mahmoudreda55/satellite-image-classification) 


### Model Architecture Summary

- Transfer learning with **MobileNetV2** backbone
- Two-phase training strategy (frozen base then fine-tuning)
- Data augmentation applied for robustness
- Final exported artifacts:
	- `models/satellite_classifier.keras`
	- `models/satellite_classifier.h5`
	- `models/class_names.json`

## Repository Structure

```text
Satelite-Image-Classification/
├── api/                              # FastAPI backend service
│   └── main.py                       # API routes, CORS, DB setup, retraining orchestration
├── src/                              # ML core logic used by the backend
│   ├── model.py                      # Retraining logic and model fine-tuning
│   ├── prediction.py                 # Inference wrapper/classifier runtime
│   └── preprocessing.py              # Image validation and preprocessing helpers
├── frontend/                         # React + Vite frontend
│   ├── package.json                  # Frontend dependencies and scripts
│   ├── vite.config.js                # Dev proxy and build config
│   ├── netlify.toml                  # Static hosting config for frontend-only deployments
│   ├── index.html                    # Vite HTML entrypoint
│   ├── public/
│   │   └── _redirects                # Rewrite rules
│   └── src/
│       ├── main.jsx                  # React bootstrap
│       ├── App.jsx                   # Main app shell
│       ├── api.js                    # Frontend API client and URL resolution
│       └── components/
│           ├── StatusMonitor.jsx     # Health and status panel
│           ├── Predict.jsx           # Single image prediction UI
│           ├── Upload.jsx            # Bulk image upload UI for retraining data
│           ├── RetrainPanel.jsx      # Retraining trigger and status polling UI
│           ├── RecentPredictions.jsx # Recent prediction history panel
│           └── Visualizations.jsx    # Visualization gallery panel
├── notebook/
│   └── satelite-image-classification.ipynb  # Full ML workflow notebook
├── data/                             # Dataset and runtime data folders
│   ├── train/                        # Training data split
│   ├── test/                         # Test data split
│   ├── retrain/                      # Uploaded class folders used for retraining
│   └── uploads/                      # Raw uploaded files
├── models/                           # Saved model artifacts for inference/retraining
│   ├── best_model.keras              # Best checkpoint from training workflow
│   ├── satellite_classifier.keras    # Main model artifact
│   ├── satellite_classifier.h5       # API-serving compatible model artifact
│   └── class_names.json              # Class index/label mapping
├── static/
│   └── visualizations/               # PNG outputs shown in frontend visualization tab
│       ├── class_distribution.png
│       ├── mean_intensity.png
│       └── sample_images.png
├── docker-compose.yml                # Multi-container local stack (API + Postgres)
├── Dockerfile                        # Container build (backend + built frontend static assets)
├── requirements.txt                  # Python dependencies
├── locustfile.py                     # Locust load-testing scenarios
├── initialize_training_data.py       # Utility script for generating sample retrain images
├── DEPLOYMENT_GUIDE.md               # Deployment notes and troubleshooting
└── README.md                         # Project documentation
```

## Local Setup Instructions

### 1. Prerequisites

- Python `3.11+`
- Node.js `18+` and npm
- Docker + Docker Compose
- Git

### 2. Clone Repository

```bash
git clone <YOUR_REPO_URL>
cd Satelite-Image-Classification
```

### 3. Create and Activate Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure `.env`

Create a `.env` in the project root:

```env
DATABASE_URL=postgresq....

USE_HF_INFERENCE=true
HF_MODEL_URL=https://missnoel-satellite-classifier-api.hf.space/predict
HF_TOKEN=
HF_TIMEOUT_SECONDS=60
HF_MAX_RETRIES=2
HF_RETRY_BACKOFF_SECONDS=1.0
HF_RETRY_BACKOFF_MULTIPLIER=2.0
ENABLE_LOCAL_INFERENCE=false
ENABLE_WEB_RETRAIN=false
ENABLE_RETRAIN_QUEUE=true
RETRAIN_WORKER_STALE_SECONDS=45

DB_CONNECT_RETRIES=60
DB_CONNECT_DELAY_SECONDS=2

# Optional for persistent disk deployments
UPLOAD_DATA_DIR=data/uploads
RETRAIN_DATA_DIR=data/retrain
```

Frontend Render env (backend-only API flow):

```env
VITE_API_BASE_URL=https://satelite-image-classification.onrender.com
# Leave VITE_HF_MODEL_URL and VITE_HF_TOKEN unset
```

### 5. Start Database

```bash
docker compose up -d db
```

Database port is mapped as `5434 -> 5432` in this repository.

### 6. Start API

From project root:

```bash
uvicorn api.main:app --reload --port 8001
```

API docs available at:

- `http://localhost:8001/docs`

### 7. Start Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:

- `http://localhost:5173`

## Docker Instructions

Run full stack (API + Postgres) with one command:

```bash
docker compose up --build
```

API will be exposed at:

- `http://localhost:8001`

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check, inference mode, retrain running flag |
| POST | `/predict` | Predict class for one image file |
| POST | `/upload` | Bulk upload files for a given class label |
| POST | `/retrain` | Trigger asynchronous model retraining |
| GET | `/retrain/status` | Poll current retraining status/result |
| GET | `/stats` | Fetch upload/prediction/retrain stats |
| GET | `/visualizations` | Return available visualization image URLs |
| GET | `/static/*` | Serve static assets (visualization PNGs, built frontend assets) |

## Load Test Results (Locust)

Use `locustfile.py` to benchmark `/health`, `/predict`, and `/stats`.

### Run Command Example

```bash
locust -f locustfile.py --host http://localhost:8001
```

### Results Table

Fill with your measured values from the Locust run report.

| Concurrent Users | Requests/sec | Median Response Time (ms) | 95th Percentile (ms) | Failure Rate |
|---|---:|---:|---:|---:|
| 10 | `TBD` | `TBD` | `TBD` | `TBD` |
| 50 | `TBD` | `TBD` | `TBD` | `TBD` |
| 100 | `TBD` | `TBD` | `TBD` | `TBD` |

### Locust Screenshots

Add screenshots and update paths below:

- `docs/load-tests/locust-10-users.png` (add file)
- `docs/load-tests/locust-50-users.png` (add file)
- `docs/load-tests/locust-100-users.png` (add file)

## Model Evaluation Results (Notebook)

Extracted from notebook output (`notebook/satelite-image-classification.ipynb`):

| Metric | Value |
|---|---:|
| Test Accuracy | `0.9870` |
| Test Loss | `0.0560` |
| Precision (weighted) | `0.9874` |
| Recall (weighted) | `0.9870` |
| F1-Score (weighted) | `0.9870` |
