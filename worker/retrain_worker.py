import asyncio
import json
import os
import socket
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import asyncpg


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
MODEL_PATH = Path(os.environ.get("MODEL_PATH", str(BASE_DIR / "models" / "satellite_classifier.h5")))
CLASS_NAMES_PATH = Path(os.environ.get("CLASS_NAMES_PATH", str(BASE_DIR / "models" / "class_names.json")))
POLL_INTERVAL_SECONDS = float(os.environ.get("RETRAIN_WORKER_POLL_INTERVAL_SECONDS", "3"))
WORKER_HEARTBEAT_INTERVAL_SECONDS = float(os.environ.get("RETRAIN_WORKER_HEARTBEAT_INTERVAL_SECONDS", "10"))
WORKER_ID = os.environ.get("RETRAIN_WORKER_ID", socket.gethostname())


async def ensure_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS retrain_jobs (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                status        TEXT NOT NULL,
                queued_at     TIMESTAMPTZ DEFAULT NOW(),
                started_at    TIMESTAMPTZ,
                completed_at  TIMESTAMPTZ,
                requested_by  TEXT,
                result        JSONB,
                error_message TEXT,
                worker_id     TEXT,
                CONSTRAINT retrain_jobs_status_check CHECK (
                    status IN ('queued', 'running', 'success', 'failed')
                )
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS retrain_worker_heartbeats (
                worker_id      TEXT PRIMARY KEY,
                last_heartbeat TIMESTAMPTZ NOT NULL,
                status         TEXT,
                updated_at     TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )


async def update_heartbeat(pool: asyncpg.Pool, status: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO retrain_worker_heartbeats (worker_id, last_heartbeat, status, updated_at)
            VALUES ($1, NOW(), $2, NOW())
            ON CONFLICT (worker_id)
            DO UPDATE SET
                last_heartbeat = EXCLUDED.last_heartbeat,
                status = EXCLUDED.status,
                updated_at = NOW()
            """,
            WORKER_ID,
            status,
        )


async def heartbeat_loop(pool: asyncpg.Pool) -> None:
    while True:
        await update_heartbeat(pool, "alive")
        await asyncio.sleep(WORKER_HEARTBEAT_INTERVAL_SECONDS)


async def claim_next_job(pool: asyncpg.Pool) -> str | None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                WITH next_job AS (
                    SELECT id
                    FROM retrain_jobs
                    WHERE status = 'queued'
                    ORDER BY queued_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE retrain_jobs r
                SET status = 'running',
                    started_at = NOW(),
                    worker_id = $1,
                    error_message = NULL
                WHERE r.id = (SELECT id FROM next_job)
                RETURNING r.id
                """,
                WORKER_ID,
            )
            if row is None:
                return None
            return str(row["id"])


async def load_uploaded_images(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, filename, class_label, file_bytes
            FROM uploaded_images
            WHERE file_bytes IS NOT NULL
            """
        )
    return rows


def materialize_training_data(rows, root_dir: Path) -> int:
    count = 0
    for row in rows:
        class_label = str(row["class_label"]).strip()
        if not class_label:
            continue
        blob = row["file_bytes"]
        if blob is None:
            continue

        class_dir = root_dir / class_label
        class_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(str(row["filename"]).strip() or "image.bin").name
        unique_name = f"{str(row['id']).replace('-', '')}_{filename}"
        path = class_dir / unique_name
        path.write_bytes(bytes(blob))
        count += 1
    return count


async def mark_job_success(pool: asyncpg.Pool, job_id: str, result: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE retrain_jobs
            SET status = 'success',
                completed_at = NOW(),
                result = $2::jsonb,
                error_message = NULL
            WHERE id = $1::uuid
            """,
            job_id,
            json.dumps(result),
        )
        await conn.execute(
            "INSERT INTO retrain_logs (result) VALUES ($1::jsonb)",
            json.dumps(result),
        )


async def mark_job_failed(pool: asyncpg.Pool, job_id: str, message: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE retrain_jobs
            SET status = 'failed',
                completed_at = NOW(),
                error_message = $2
            WHERE id = $1::uuid
            """,
            job_id,
            message[:4000],
        )


def run_training(data_dir: Path) -> dict:
    from src.model import retrain

    return retrain(
        new_data_dir=str(data_dir),
        model_path=str(MODEL_PATH),
        class_names_path=str(CLASS_NAMES_PATH),
        epochs=5,
    )


async def process_job(pool: asyncpg.Pool, job_id: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Processing retrain job {job_id}")
    await update_heartbeat(pool, f"running:{job_id}")
    rows = await load_uploaded_images(pool)

    with tempfile.TemporaryDirectory(prefix="retrain-job-") as tmp:
        tmp_path = Path(tmp)
        image_count = materialize_training_data(rows, tmp_path)
        if image_count == 0:
            await mark_job_failed(pool, job_id, "No uploaded image blobs available for retraining.")
            return

        try:
            result = await asyncio.to_thread(run_training, tmp_path)
            await mark_job_success(pool, job_id, result)
            await update_heartbeat(pool, "idle")
            print(f"[{datetime.now(timezone.utc).isoformat()}] Retrain job {job_id} completed")
        except Exception as exc:
            await mark_job_failed(pool, job_id, f"{type(exc).__name__}: {exc}")
            await update_heartbeat(pool, f"error:{job_id}")
            print(f"[{datetime.now(timezone.utc).isoformat()}] Retrain job {job_id} failed: {exc}")


async def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for retrain worker")

    print(f"Starting retrain worker {WORKER_ID}")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4)
    await ensure_schema(pool)
    await update_heartbeat(pool, "idle")
    heartbeat_task = asyncio.create_task(heartbeat_loop(pool))

    try:
        while True:
            job_id = await claim_next_job(pool)
            if job_id is None:
                await update_heartbeat(pool, "idle")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            await process_job(pool, job_id)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
