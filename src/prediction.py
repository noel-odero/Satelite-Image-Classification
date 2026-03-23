"""
Wraps model loading and single-image prediction.
Loaded once at API startup and reused across all requests
to avoid reloading the model on every call (expensive).
"""

import json
import numpy as np
from pathlib import Path
import tensorflow as tf
from src.preprocessing import preprocess_for_inference


class SatelliteClassifier:
    """
    Singleton-style wrapper around the trained model.
    Handles loading, warm-up, and inference.
    """

    def __init__(self, model_path: str, class_names_path: str):
        self.model_path = model_path
        self.model = None
        self.idx_to_class = None
        self._load(class_names_path)

    def _load(self, class_names_path: str):
        """Load model and class name mapping from disk."""
        print(f"Loading model from: {self.model_path}")
        self.model = tf.keras.models.load_model(self.model_path)

        with open(class_names_path, "r") as f:
            # class_names.json stores {index: class_name}
            raw = json.load(f)
            self.idx_to_class = {int(k): v for k, v in raw.items()}

        # Warm-up pass — prevents cold-start latency on first real request
        dummy = np.zeros((1, 224, 224, 3), dtype=np.float32)
        self.model.predict(dummy, verbose=0)
        print("Model loaded and warmed up.")
        print("Classes:", self.idx_to_class)

    def predict(self, file_bytes: bytes) -> dict:
        """
        Run inference on raw image bytes.
        Returns predicted class, confidence, and all class probabilities.
        """
        img_array = preprocess_for_inference(file_bytes)
        probs = self.model.predict(img_array, verbose=0)[0]
        pred_idx = int(np.argmax(probs))
        pred_class = self.idx_to_class[pred_idx]
        confidence = float(probs[pred_idx])

        return {
            "predicted_class": pred_class,
            "confidence": round(confidence, 4),
            "all_probabilities": {
                self.idx_to_class[i]: round(float(p), 4)
                for i, p in enumerate(probs)
            },
        }