"""
Handles all image preprocessing logic — used during training,
retraining, and inference. Keeping this in a separate module
ensures consistent preprocessing across all pipeline stages.
"""

import os
import numpy as np
from pathlib import Path
from PIL import Image
import io

# Constants — must match what the model was trained with
IMG_SIZE = (224, 224)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image(file_bytes: bytes, filename: str) -> bool:
    """Check that the uploaded file is a valid image."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
        return True
    except Exception:
        return False


def preprocess_for_inference(file_bytes: bytes) -> np.ndarray:
    """
    Preprocess a single raw image (bytes) for model inference.
    Steps:
      1. Open image from bytes
      2. Convert to RGB (handles grayscale / RGBA uploads)
      3. Resize to 224x224
      4. Convert to float32 array
      5. Apply MobileNetV2 preprocess_input (scales to [-1, 1])
      6. Add batch dimension
    Returns: numpy array of shape (1, 224, 224, 3)
    """
    from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img = img.resize(IMG_SIZE, Image.LANCZOS)
    img_array = np.array(img, dtype=np.float32)
    img_array = preprocess_input(img_array)
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


def preprocess_for_retraining(image_dir: str) -> dict:
    """
    Validate and summarize images in a directory tree for retraining.
    Expects structure: image_dir/<class_name>/<image_files>
    Returns a summary dict with class counts and any invalid files found.
    """
    image_dir = Path(image_dir)
    summary = {"classes": {}, "invalid_files": [], "total_valid": 0}

    for class_dir in sorted(image_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        valid = 0
        for img_path in class_dir.iterdir():
            if img_path.suffix.lower() in ALLOWED_EXTENSIONS:
                try:
                    img = Image.open(img_path)
                    img.verify()
                    valid += 1
                except Exception:
                    summary["invalid_files"].append(str(img_path))
            else:
                summary["invalid_files"].append(str(img_path))
        summary["classes"][class_dir.name] = valid
        summary["total_valid"] += valid

    return summary