#!/usr/bin/env python3
"""
Generate sample training images for the retraining system.
This creates minimal placeholder satellite images for each class.

Usage:
    python initialize_training_data.py
"""

import io
from pathlib import Path
from PIL import Image, ImageDraw
import random

# Image classes
CLASSES = ['cloudy', 'desert', 'green_area', 'water']
RETRAIN_DIR = Path(__file__).parent / "data" / "retrain"
SAMPLES_PER_CLASS = 5
IMAGE_SIZE = (64, 64)

def create_sample_image(class_label: str) -> Image.Image:
    """Create a minimal sample satellite image for the given class."""
    img = Image.new('RGB', IMAGE_SIZE, color='white')
    draw = ImageDraw.Draw(img)
    
    # Generate class-specific patterns
    if class_label == 'cloudy':
        # White/gray cloudy pattern
        for _ in range(20):
            x = random.randint(0, IMAGE_SIZE[0])
            y = random.randint(0, IMAGE_SIZE[1])
            color = (random.randint(180, 255), random.randint(180, 255), random.randint(180, 255))
            draw.ellipse([x, y, x+10, y+10], fill=color)
    
    elif class_label == 'desert':
        # Tan/brown desert pattern
        for x in range(0, IMAGE_SIZE[0], 4):
            for y in range(0, IMAGE_SIZE[1], 4):
                color = (random.randint(180, 220), random.randint(140, 180), random.randint(60, 100))
                draw.rectangle([x, y, x+4, y+4], fill=color)
    
    elif class_label == 'green_area':
        # Green vegetation pattern
        for x in range(0, IMAGE_SIZE[0], 3):
            for y in range(0, IMAGE_SIZE[1], 3):
                color = (random.randint(34, 100), random.randint(100, 180), random.randint(34, 100))
                draw.rectangle([x, y, x+3, y+3], fill=color)
    
    elif class_label == 'water':
        # Blue water pattern
        for x in range(0, IMAGE_SIZE[0], 5):
            for y in range(0, IMAGE_SIZE[1], 5):
                color = (random.randint(30, 100), random.randint(100, 180), random.randint(180, 220))
                draw.rectangle([x, y, x+5, y+5], fill=color)
    
    return img

def main():
    """Generate sample images for all classes."""
    print("Initializing training data directories...")
    
    for class_label in CLASSES:
        class_dir = RETRAIN_DIR / class_label
        class_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nGenerating {SAMPLES_PER_CLASS} sample images for '{class_label}'...")
        
        for i in range(SAMPLES_PER_CLASS):
            img = create_sample_image(class_label)
            filename = f"sample_{class_label}_{i:02d}.png"
            filepath = class_dir / filename
            
            img.save(filepath)
            print(f"  ✓ Created {filename}")
    
    print(f"\n✓ Sample data initialized in: {RETRAIN_DIR}")
    print(f"  Classes: {', '.join(CLASSES)}")
    print(f"  Total images: {len(CLASSES) * SAMPLES_PER_CLASS}")
    print("\nYou can now trigger retraining via the API:")
    print("  POST /retrain")

if __name__ == "__main__":
    main()
