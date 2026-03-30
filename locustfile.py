import os
import random
from pathlib import Path

from locust import HttpUser, between, task
from locust.exception import StopUser


REPO_ROOT = Path(__file__).resolve().parent

# Primary directory for prediction samples.
SAMPLE_DIR = Path(os.getenv("LOCUST_IMAGE_DIR", REPO_ROOT / "data" / "test"))

# Optional fallback folders, comma-separated.
FALLBACK_DIRS = [
    Path(item.strip())
    for item in os.getenv("LOCUST_FALLBACK_DIRS", "").split(",")
    if item.strip()
]

# Default wait mimics user pacing and avoids unrealistic hammering.
WAIT_MIN = float(os.getenv("LOCUST_WAIT_MIN", "1"))
WAIT_MAX = float(os.getenv("LOCUST_WAIT_MAX", "3"))

REQUEST_TIMEOUT_SECONDS = float(os.getenv("LOCUST_REQUEST_TIMEOUT", "60"))
SAMPLE_EVERY_N_SUCCESS = int(os.getenv("LOCUST_SAMPLE_EVERY", "25"))

HEALTH_PATH = os.getenv("LOCUST_HEALTH_PATH", "/health")
PREDICT_PATH = os.getenv("LOCUST_PREDICT_PATH", "/predict")
STATS_PATH = os.getenv("LOCUST_STATS_PATH", "/stats")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def collect_sample_images() -> list[tuple[str, bytes, str]]:
    candidates = [SAMPLE_DIR] + FALLBACK_DIRS
    images: list[tuple[str, bytes, str]] = []

    for directory in candidates:
        if not directory.exists() or not directory.is_dir():
            continue

        for path in directory.rglob("*"):
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            try:
                images.append((path.name, path.read_bytes(), mime_type))
            except OSError:
                continue

    return images


class SatelliteAPIUser(HttpUser):
    host = os.getenv("LOCUST_HOST", "http://localhost:8001")
    wait_time = between(WAIT_MIN, WAIT_MAX)

    def on_start(self) -> None:
        self.images = collect_sample_images()
        self.predict_success_count = 0

        if not self.images:
            print(
                "[Locust] No images found. Add .jpg/.jpeg/.png files to "
                f"{SAMPLE_DIR} or set LOCUST_FALLBACK_DIRS."
            )
            raise StopUser()

        print(
            f"[Locust] Loaded {len(self.images)} images. "
            f"Primary image dir: {SAMPLE_DIR}"
        )

    @task(1)
    def health_check(self) -> None:
        with self.client.get(
            HEALTH_PATH,
            name=f"GET {HEALTH_PATH}",
            catch_response=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            if response.status_code == 200:
                response.success()
                return

            response.failure(
                f"Health check failed: HTTP {response.status_code}, body={response.text[:200]!r}"
            )

    @task(3)
    def predict(self) -> None:
        image_name, image_bytes, mime_type = random.choice(self.images)

        files = {"file": (image_name, image_bytes, mime_type)}
        with self.client.post(
            PREDICT_PATH,
            files=files,
            name=f"POST {PREDICT_PATH}",
            catch_response=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"HTTP {response.status_code} for {image_name}: {response.text[:200]}"
                )
                return

            try:
                body = response.json()
            except ValueError:
                content_type = response.headers.get("Content-Type", "unknown")
                body_preview = (response.text or "")[:200]
                response.failure(
                    "Non-JSON response "
                    f"(status={response.status_code}, content_type={content_type}) "
                    f"for {image_name}. Body preview: {body_preview!r}"
                )
                return

            if "predicted_class" not in body:
                response.failure(f"Missing predicted_class for {image_name}. Response: {body}")
                return

            confidence = body.get("confidence")
            if confidence is not None and not isinstance(confidence, (int, float)):
                response.failure(
                    f"Invalid confidence type for {image_name}: {type(confidence).__name__}"
                )
                return

            self.predict_success_count += 1
            if SAMPLE_EVERY_N_SUCCESS > 0 and self.predict_success_count % SAMPLE_EVERY_N_SUCCESS == 0:
                printable_conf = (
                    f"{float(confidence):.4f}" if isinstance(confidence, (int, float)) else "n/a"
                )
                print(
                    "[Sample Prediction] "
                    f"file={body.get('filename', image_name)} "
                    f"class={body.get('predicted_class')} "
                    f"confidence={printable_conf}"
                )

            response.success()

    @task(1)
    def get_stats(self) -> None:
        with self.client.get(
            STATS_PATH,
            name=f"GET {STATS_PATH}",
            catch_response=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            if response.status_code == 200:
                response.success()
                return

            response.failure(
                f"Stats failed: HTTP {response.status_code}, body={response.text[:200]!r}"
            )