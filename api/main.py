"""
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
from typing import Optional, TYPE_CHECKING

import asyncpg
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.preprocessing import validate_image

if TYPE_CHECKING:
    from src.prediction import SatelliteClassifier

# Paths 
BASE_DIR      = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

MODEL_PATH    = BASE_DIR / "models" / "satellite_classifier.h5"
RETRAIN_MODEL = BASE_DIR / "models" / "best_model.keras"
CLASS_NAMES   = BASE_DIR / "models" / "class_names.json"
UPLOAD_DIR    = Path(os.environ.get("UPLOAD_DATA_DIR", str(BASE_DIR / "data" / "uploads")))
RETRAIN_DIR   = Path(os.environ.get("RETRAIN_DATA_DIR", str(BASE_DIR / "data" / "retrain")))
STATIC_DIR    = BASE_DIR / "static"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RETRAIN_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# DB 
DATABASE_URL = os.environ.get("DATABASE_URL")
DB_CONNECT_RETRIES = int(os.environ.get("DB_CONNECT_RETRIES", "30"))
DB_CONNECT_DELAY_SECONDS = float(os.environ.get("DB_CONNECT_DELAY_SECONDS", "2"))
HF_MODEL_URL = os.environ.get("HF_MODEL_URL", "").strip()
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
HF_TIMEOUT_SECONDS = float(os.environ.get("HF_TIMEOUT_SECONDS", "60"))
HF_MAX_RETRIES = int(os.environ.get("HF_MAX_RETRIES", "2"))
HF_RETRY_BACKOFF_SECONDS = float(os.environ.get("HF_RETRY_BACKOFF_SECONDS", "1.0"))
HF_RETRY_BACKOFF_MULTIPLIER = float(os.environ.get("HF_RETRY_BACKOFF_MULTIPLIER", "2.0"))
USE_HF_INFERENCE = os.environ.get("USE_HF_INFERENCE", "false").lower() == "true" or bool(HF_MODEL_URL)

# Global state 
classifier: Optional["SatelliteClassifier"] = None
db_pool: Optional[asyncpg.Pool] = None
db_init_lock = asyncio.Lock()
retrain_status = {"running": False, "last_result": None}


async def _init_db_pool_and_schema() -> None:
    """Initialize DB connection pool and required tables."""
    global db_pool

    if db_pool is not None:
        return

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")

    async with db_init_lock:
        if db_pool is not None:
            return

        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        async with db_pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_images (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    filename    TEXT NOT NULL,
                    class_label TEXT NOT NULL,
                    file_path   TEXT NOT NULL,
                    file_bytes  BYTEA,
                    uploaded_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            await conn.execute(
                "ALTER TABLE uploaded_images ADD COLUMN IF NOT EXISTS file_bytes BYTEA;"
            )
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


async def _ensure_db_pool_available(retries: int = 2, delay_seconds: float = 1.0) -> None:
    """Ensure DB pool is ready for request handlers, with short retries."""
    if db_pool is not None:
        return

    last_error = None
    for attempt in range(1, retries + 2):
        try:
            await _init_db_pool_and_schema()
            return
        except Exception as exc:
            last_error = exc
            if attempt <= retries:
                await asyncio.sleep(delay_seconds)

    raise HTTPException(status_code=503, detail=f"Database unavailable: {last_error}")


async def _restore_retrain_files_from_db() -> int:
    """Rehydrate retraining image files from DB when container disk is empty."""
    if db_pool is None:
        return 0

    restored = 0
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, filename, class_label, file_bytes
            FROM uploaded_images
            WHERE file_bytes IS NOT NULL
            """
        )

    for row in rows:
        class_dir = RETRAIN_DIR / row["class_label"]
        class_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(row["filename"]).name
        unique_name = f"{str(row['id']).replace('-', '')}_{safe_filename}"
        file_path = class_dir / unique_name

        if file_path.exists():
            continue

        file_bytes = bytes(row["file_bytes"])
        file_path.write_bytes(file_bytes)
        restored += 1

    return restored


def _normalize_label(label: str) -> str:
    return str(label).strip().lower().replace(" ", "_")


def _normalize_hf_output(payload) -> dict:
    rows = []
    if isinstance(payload, list):
        rows = payload[0] if payload and isinstance(payload[0], list) else payload
    elif isinstance(payload, dict) and isinstance(payload.get("labels"), list) and isinstance(payload.get("scores"), list):
        rows = [
            {"label": label, "score": payload["scores"][idx]}
            for idx, label in enumerate(payload["labels"])
        ]

    if not rows:
        raise ValueError("Unexpected Hugging Face response format")

    normalized = sorted(
        [
            {
                "label": _normalize_label(item.get("label", "unknown")),
                "score": float(item.get("score", 0.0)),
            }
            for item in rows
        ],
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "predicted_class": normalized[0]["label"],
        "confidence": normalized[0]["score"],
        "all_probabilities": {
            item["label"]: item["score"]
            for item in normalized
        },
    }


async def _predict_with_hf(file_bytes: bytes) -> dict:
    if not HF_MODEL_URL:
        raise HTTPException(status_code=500, detail="HF_MODEL_URL is not configured")

    headers = {"Content-Type": "application/octet-stream"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    def _post_request():
        return requests.post(
            HF_MODEL_URL,
            headers=headers,
            data=file_bytes,
            timeout=HF_TIMEOUT_SECONDS,
        )

    last_error: Optional[str] = None
    backoff_seconds = HF_RETRY_BACKOFF_SECONDS
    retryable_statuses = {429, 502, 503, 504}

    for attempt in range(1, HF_MAX_RETRIES + 2):
        request_started = datetime.utcnow()
        try:
            response = await asyncio.to_thread(_post_request)
        except requests.RequestException as exc:
            last_error = f"Hugging Face request failed: {exc}"
            should_retry = attempt <= HF_MAX_RETRIES
            print(
                f"HF request exception on attempt {attempt}/{HF_MAX_RETRIES + 1}: {exc}"
            )
            if should_retry:
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= HF_RETRY_BACKOFF_MULTIPLIER
                continue
            raise HTTPException(status_code=503, detail=last_error)

        duration_seconds = (datetime.utcnow() - request_started).total_seconds()

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}

        if response.status_code < 400:
            try:
                return _normalize_hf_output(payload)
            except ValueError as exc:
                raise HTTPException(status_code=502, detail=str(exc))

        detail = payload.get("error") if isinstance(payload, dict) else str(payload)
        last_error = f"Hugging Face error (HTTP {response.status_code}): {detail}"
        should_retry = attempt <= HF_MAX_RETRIES and response.status_code in retryable_statuses
        print(
            "HF upstream error "
            f"attempt={attempt}/{HF_MAX_RETRIES + 1} "
            f"status={response.status_code} duration={duration_seconds:.2f}s "
            f"retry={should_retry}"
        )

        if should_retry:
            await asyncio.sleep(backoff_seconds)
            backoff_seconds *= HF_RETRY_BACKOFF_MULTIPLIER
            continue

        raise HTTPException(status_code=503, detail=last_error)

    raise HTTPException(
        status_code=503,
        detail=last_error or "Hugging Face inference failed after retries.",
    )


# Startup / Shutdown 
@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, db_pool

    # Load local model only when local inference is enabled.
    if USE_HF_INFERENCE:
        print(f"Using Hugging Face inference endpoint: {HF_MODEL_URL}")
        classifier = None
    else:
        from src.prediction import SatelliteClassifier

        classifier = SatelliteClassifier(str(MODEL_PATH), str(CLASS_NAMES))

    # Initialize DB on startup, but don't block service health forever if DB is slow.
    if not DATABASE_URL:
        print("DATABASE_URL is not set; DB-backed endpoints will return 503.")
    else:
        try:
            await asyncio.wait_for(_init_db_pool_and_schema(), timeout=4.0)
        except Exception as exc:
            print(f"Startup DB init skipped: {exc}")

    yield

    if db_pool is not None:
        await db_pool.close()


# App 
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


# API Endpoints 

@app.get("/health")
async def health():
    """Uptime check — UI uses this to show model status."""
    db_ready = db_pool is not None
    return {
        "status": "online",
        "model": "satellite_classifier",
        "inference_provider": "huggingface" if USE_HF_INFERENCE else "local",
        "timestamp": datetime.utcnow().isoformat(),
        "retrain_running": retrain_status["running"],
        "db_ready": db_ready,
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    """
    Accept a single satellite image and return terrain classification.
    Also logs the prediction to the database.
    """
    await _ensure_db_pool_available()

    file_bytes = await file.read()

    if not validate_image(file_bytes, file.filename):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    if USE_HF_INFERENCE:
        result = await _predict_with_hf(file_bytes)
    else:
        if classifier is None:
            raise HTTPException(status_code=503, detail="Local model not initialized")
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

    await _ensure_db_pool_available()

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
                     """INSERT INTO uploaded_images (filename, class_label, file_path, file_bytes)
                         VALUES ($1, $2, $3, $4)""",
                file.filename,
                class_label,
                str(save_path),
                     file_bytes,
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
        await _ensure_db_pool_available()

        from src.model import retrain

        result = retrain(
            new_data_dir=str(RETRAIN_DIR),
            model_path=str(MODEL_PATH),
            class_names_path=str(CLASS_NAMES),
            epochs=5,
        )
        retrain_status["last_result"] = result

        # Reload classifier with updated model only for local inference mode.
        if not USE_HF_INFERENCE:
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

    await _ensure_db_pool_available()

    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    disk_image_count = sum(
        1
        for p in RETRAIN_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in image_exts
    )

    db_uploaded_count = 0
    async with db_pool.acquire() as conn:
        db_uploaded_count = await conn.fetchval("SELECT COUNT(*) FROM uploaded_images")

    # For ephemeral container filesystems, rebuild retrain files from DB blobs.
    if disk_image_count == 0 and db_uploaded_count > 0:
        restored_count = await _restore_retrain_files_from_db()
        if restored_count > 0:
            disk_image_count = sum(
                1
                for p in RETRAIN_DIR.rglob("*")
                if p.is_file() and p.suffix.lower() in image_exts
            )

    if disk_image_count == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No retraining image files found on server disk. "
                f"Database has {db_uploaded_count} uploaded image record(s). "
                "Some older rows may not include binary image data. "
                "If this service restarted/redeployed on Render, local disk data may have been cleared. "
                "Upload images again and retrain immediately, or mount a persistent disk and set RETRAIN_DATA_DIR."
            ),
        )

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
    await _ensure_db_pool_available()

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


# Frontend catch-all — must be LAST ─────────────────────────────────────────
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