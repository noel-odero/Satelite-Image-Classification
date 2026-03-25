"""
main.py
FastAPI application — exposes all endpoints needed by the UI:
  POST /predict         — single image prediction
  POST /upload          — bulk image upload (saved to DB + disk for retraining)
  POST /retrain         — trigger retraining on uploaded data
  GET  /health          — uptime / health check
  GET  /stats           — dataset stats from DB for visualizations
  GET  /visualizations  — paths to precomputed visualization images
"""

import os
import io
import uuid
import json
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.prediction import SatelliteClassifier
from src.preprocessing import validate_image
from src.model import retrain

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent
MODEL_PATH    = BASE_DIR / "models" / "satellite_classifier.h5"
RETRAIN_MODEL = BASE_DIR / "models" / "best_model.keras"
CLASS_NAMES   = BASE_DIR / "models" / "class_names.json"
UPLOAD_DIR    = BASE_DIR / "data" / "uploads"
RETRAIN_DIR   = BASE_DIR / "data" / "retrain"
STATIC_DIR    = BASE_DIR / "static"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RETRAIN_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ── DB ────────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")

# ── Global state ──────────────────────────────────────────────────────────────
classifier: Optional[SatelliteClassifier] = None
db_pool: Optional[asyncpg.Pool] = None
retrain_status = {"running": False, "last_result": None}


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, db_pool

    # Load model
    classifier = SatelliteClassifier(str(MODEL_PATH), str(CLASS_NAMES))

    # Connect to PostgreSQL
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_images (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename    TEXT NOT NULL,
                class_label TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                uploaded_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename         TEXT,
                predicted_class  TEXT NOT NULL,
                confidence       FLOAT NOT NULL,
                all_probs        JSONB,
                predicted_at     TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS retrain_logs (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                triggered_at TIMESTAMPTZ DEFAULT NOW(),
                result       JSONB
            );
        """)
    print("Database tables ready.")
    yield

    await db_pool.close()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Satellite Image Classifier API",
    description="ML Pipeline API — predict terrain type from satellite images",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets (visualizations, etc.)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Uptime check — UI uses this to show model status."""
    return {
        "status": "online",
        "model": "satellite_classifier",
        "timestamp": datetime.utcnow().isoformat(),
        "retrain_running": retrain_status["running"],
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    """
    Accept a single satellite image and return terrain classification.
    Also logs the prediction to the database.
    """
    file_bytes = await file.read()

    if not validate_image(file_bytes, file.filename):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    result = classifier.predict(file_bytes)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO predictions (filename, predicted_class, confidence, all_probs)
               VALUES ($1, $2, $3, $4)""",
            file.filename,
            result["predicted_class"],
            result["confidence"],
            json.dumps(result["all_probabilities"]),
        )

    return JSONResponse(content={"filename": file.filename, **result})


@app.post("/upload")
async def upload_images(
    files: list[UploadFile] = File(...),
    class_label: str = Form(...),
):
    """
    Bulk upload images for a given class label.
    Images are saved to disk and recorded in the database.
    """
    if class_label.strip() == "":
        raise HTTPException(status_code=400, detail="class_label is required.")

    class_dir = RETRAIN_DIR / class_label
    class_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    async with db_pool.acquire() as conn:
        for file in files:
            file_bytes = await file.read()
            if not validate_image(file_bytes, file.filename):
                continue

            unique_name = f"{uuid.uuid4().hex}_{file.filename}"
            save_path = class_dir / unique_name
            save_path.write_bytes(file_bytes)

            await conn.execute(
                """INSERT INTO uploaded_images (filename, class_label, file_path)
                   VALUES ($1, $2, $3)""",
                file.filename,
                class_label,
                str(save_path),
            )
            saved.append(unique_name)

    return {
        "uploaded": len(saved),
        "class_label": class_label,
        "skipped": len(files) - len(saved),
    }


async def _run_retrain():
    """Background task — runs retraining without blocking the API."""
    global retrain_status, classifier
    retrain_status["running"] = True
    try:
        result = retrain(
            new_data_dir=str(RETRAIN_DIR),
            model_path=str(RETRAIN_MODEL),
            class_names_path=str(CLASS_NAMES),
            epochs=5,
        )
        retrain_status["last_result"] = result

        # Reload classifier with updated model
        classifier = SatelliteClassifier(str(MODEL_PATH), str(CLASS_NAMES))

        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO retrain_logs (result) VALUES ($1)",
                json.dumps(result),
            )
    except Exception as e:
        retrain_status["last_result"] = {"status": "error", "message": str(e)}
    finally:
        retrain_status["running"] = False


@app.post("/retrain")
async def trigger_retrain(background_tasks: BackgroundTasks):
    """
    Trigger model retraining on all uploaded images.
    Runs as a background task so the API stays responsive.
    """
    if retrain_status["running"]:
        raise HTTPException(status_code=409, detail="Retraining already in progress.")

    class_dirs = [d for d in RETRAIN_DIR.iterdir() if d.is_dir()]
    if not class_dirs:
        raise HTTPException(status_code=400, detail="No uploaded data found for retraining.")

    background_tasks.add_task(_run_retrain)
    return {"message": "Retraining started in background.", "status": "running"}


@app.get("/retrain/status")
async def get_retrain_status():
    """Poll this endpoint to check if retraining is still running."""
    return retrain_status


@app.get("/stats")
async def get_stats():
    """Returns dataset and prediction statistics for UI visualizations."""
    async with db_pool.acquire() as conn:
        upload_counts = await conn.fetch(
            "SELECT class_label, COUNT(*) as count FROM uploaded_images GROUP BY class_label"
        )
        prediction_counts = await conn.fetch(
            "SELECT predicted_class, COUNT(*) as count FROM predictions GROUP BY predicted_class"
        )
        recent_predictions = await conn.fetch(
            """SELECT filename, predicted_class, confidence, predicted_at
               FROM predictions ORDER BY predicted_at DESC LIMIT 10"""
        )
        total_predictions = await conn.fetchval("SELECT COUNT(*) FROM predictions")
        retrain_count = await conn.fetchval("SELECT COUNT(*) FROM retrain_logs")

    return {
        "upload_counts": [dict(r) for r in upload_counts],
        "prediction_counts": [dict(r) for r in prediction_counts],
        "recent_predictions": [
            {**dict(r), "predicted_at": r["predicted_at"].isoformat()}
            for r in recent_predictions
        ],
        "total_predictions": total_predictions,
        "total_retrains": retrain_count,
    }


@app.get("/visualizations")
async def get_visualizations():
    """Returns URLs of precomputed visualization images."""
    vis_dir = STATIC_DIR / "visualizations"
    available = []
    if vis_dir.exists():
        available = [
            f"/static/visualizations/{f.name}"
            for f in vis_dir.iterdir()
            if f.suffix == ".png"
        ]
    return {"visualizations": available}


# ── Frontend catch-all — must be LAST ─────────────────────────────────────────
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """Serve the React app for all non-API routes."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse(
        status_code=503,
        content={"detail": "Frontend not built yet. Run: cd frontend && npm run build"}
    )