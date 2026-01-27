#!/usr/bin/env python3
"""
Convert rppg-web TensorFlow.js model to Keras HDF5 format.

Usage:
    python scripts/convert_rppg_web_model.py
"""

import os
import sys
import subprocess
from pathlib import Path

# Paths
RPPG_WEB_MODEL = Path.home() / "health-ai-suite/rppg-web/public/model.json"
OUTPUT_MODEL = Path(__file__).parent.parent / "models/mtts_can.hdf5"

def check_tensorflowjs_installed():
    """Check if tensorflowjs converter is installed."""
    try:
        result = subprocess.run(
            ["tensorflowjs_converter", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False

def install_tensorflowjs():
    """Install tensorflowjs converter."""
    print("Installing tensorflowjs converter...")
    subprocess.run([sys.executable, "-m", "pip", "install", "tensorflowjs"])

def convert_model():
    """Convert TensorFlow.js model to Keras HDF5."""
    
    # Check if source model exists
    if not RPPG_WEB_MODEL.exists():
        print(f"❌ Error: rppg-web model not found at {RPPG_WEB_MODEL}")
        print("\nPlease ensure rppg-web project exists at:")
        print(f"  {RPPG_WEB_MODEL.parent.parent}")
        return False
    
    # Check if converter is installed
    if not check_tensorflowjs_installed():
        print("tensorflowjs converter not found.")
        install_tensorflowjs()
    
    # Create output directory
    OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("Converting rppg-web Model to Keras HDF5")
    print("=" * 70)
    print(f"Source: {RPPG_WEB_MODEL}")
    print(f"Target: {OUTPUT_MODEL}")
    print()
    
    # Convert
    cmd = [
        "tensorflowjs_converter",
        "--input_format=tfjs_layers_model",
        "--output_format=keras",
        str(RPPG_WEB_MODEL),
        str(OUTPUT_MODEL)
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0 and OUTPUT_MODEL.exists():
        size_mb = OUTPUT_MODEL.stat().st_size / (1024 * 1024)
        print()
        print("=" * 70)
        print("✓ Conversion successful!")
        print("=" * 70)
        print(f"Model saved to: {OUTPUT_MODEL}")
        print(f"Size: {size_mb:.1f} MB")
        return True
    else:
        print()
        print("❌ Conversion failed!")
        return False

if __name__ == "__main__":
    success = convert_model()
    sys.exit(0 if success else 1)