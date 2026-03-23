"""
Retraining logic. Called by the /retrain API endpoint.
Uses the existing saved model as a pretrained base and
fine-tunes it on newly uploaded images.
"""

import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

IMG_SIZE = (224, 224)


def retrain(
    new_data_dir: str,
    model_path: str,
    class_names_path: str,
    epochs: int = 5,
    batch_size: int = 16,
) -> dict:
    """
    Fine-tune the existing model on newly uploaded images.

    Args:
        new_data_dir     : directory with subfolders per class
        model_path       : path to the .keras model file (used as pretrained base)
        class_names_path : path to class_names.json
        epochs           : number of retraining epochs
        batch_size       : batch size

    Returns:
        dict with retraining results and timestamp
    """
    print(f"[Retrain] Loading model from {model_path}")
    model = keras.models.load_model(model_path)

    # Unfreeze top 20 layers for fine-tuning
    for layer in model.layers[-20:]:
        layer.trainable = True

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-5),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    gen = ImageDataGenerator(
        preprocessing_function=preprocess_input,
        validation_split=0.2,
        horizontal_flip=True,
        rotation_range=15,
        zoom_range=0.1,
    )

    train_gen = gen.flow_from_directory(
        new_data_dir,
        target_size=IMG_SIZE,
        batch_size=batch_size,
        class_mode="categorical",
        subset="training",
        shuffle=True,
    )
    val_gen = gen.flow_from_directory(
        new_data_dir,
        target_size=IMG_SIZE,
        batch_size=batch_size,
        class_mode="categorical",
        subset="validation",
        shuffle=False,
    )

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=2, restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.3, patience=1, verbose=1
        ),
    ]

    history = model.fit(
        train_gen,
        epochs=epochs,
        validation_data=val_gen,
        callbacks=callbacks,
        verbose=1,
    )

    # Save updated model back to same path
    model.save(model_path)
    print(f"[Retrain] Model saved to {model_path}")

    # Update class names if new classes were introduced
    new_class_indices = train_gen.class_indices
    idx_to_class = {str(v): k for k, v in new_class_indices.items()}
    with open(class_names_path, "w") as f:
        json.dump(idx_to_class, f, indent=2)

    return {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "epochs_run": len(history.history["accuracy"]),
        "final_train_accuracy": round(history.history["accuracy"][-1], 4),
        "final_val_accuracy": round(history.history["val_accuracy"][-1], 4),
        "final_train_loss": round(history.history["loss"][-1], 4),
        "final_val_loss": round(history.history["val_loss"][-1], 4),
    }