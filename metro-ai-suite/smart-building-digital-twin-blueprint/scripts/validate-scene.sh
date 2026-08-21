#!/bin/bash
# Validate camera and sensor ID consistency for a scene

SCENE_NAME="$1"
DATASET_DIR="$2"

if [ -z "$SCENE_NAME" ] || [ -z "$DATASET_DIR" ]; then
  echo "Usage: $0 <scene-name> <dataset-dir>"
  exit 1
fi

SCENE_ZIP="scenes/${SCENE_NAME}.zip"
DATASET_PATH="datasets/$DATASET_DIR"
SENSOR_FILE="scenes/${SCENE_NAME}-sensors.json"

# Extract scene metadata
temp_dir=$(mktemp -d)
unzip -q "$SCENE_ZIP" -d "$temp_dir" 2>/dev/null

scene_json=$(find "$temp_dir" -name "*.json" -type f | head -1)

if [ -z "$scene_json" ]; then
  echo "ERROR: No JSON found in $SCENE_ZIP"
  rm -rf "$temp_dir"
  exit 1
fi

# === Validate Camera IDs ===
scene_cameras=$(jq -r '.cameras[]?.uid // .cameras[]?.id // .cameras[]?.cam_id // empty' "$scene_json" 2>/dev/null | sort | tr '\n' ' ')
dataset_cameras=$(ls "$DATASET_PATH"/cam-*.ts 2>/dev/null | xargs -n1 basename | sed 's/.ts$//' | sort | tr '\n' ' ')

scene_cameras_trimmed=$(echo "$scene_cameras" | xargs)
dataset_cameras_trimmed=$(echo "$dataset_cameras" | xargs)

echo "Camera IDs:"
echo "  Scene JSON:  $scene_cameras_trimmed"
echo "  Dataset:     $dataset_cameras_trimmed"

if [ "$scene_cameras_trimmed" != "$dataset_cameras_trimmed" ]; then
  echo "❌ ERROR: Camera ID mismatch!"
  echo
  echo "Scene export expects: $scene_cameras_trimmed"
  echo "Dataset provides:     $dataset_cameras_trimmed"
  rm -rf "$temp_dir"
  exit 1
fi

echo "  ✓ Camera IDs match"

# === Validate Sensor IDs (if sensor data exists) ===
if [ -f "$SENSOR_FILE" ]; then
  echo
  echo "Sensor IDs:"
  
  scene_sensors=$(jq -r '.sensors[]?.sensor_id // .sensors[]?.uid // .sensors[]?.id // empty' "$scene_json" 2>/dev/null | sort | tr '\n' ' ')
  sensor_data_sensors=$(jq -r '.messages[].payload.id' "$SENSOR_FILE" 2>/dev/null | sort -u | tr '\n' ' ')
  
  scene_sensors_trimmed=$(echo "$scene_sensors" | xargs)
  sensor_data_sensors_trimmed=$(echo "$sensor_data_sensors" | xargs)
  
  echo "  Scene JSON:  $scene_sensors_trimmed"
  echo "  Sensor data: $sensor_data_sensors_trimmed"
  
  if [ -n "$scene_sensors_trimmed" ] && [ -n "$sensor_data_sensors_trimmed" ]; then
    if [ "$scene_sensors_trimmed" != "$sensor_data_sensors_trimmed" ]; then
      echo "  ⚠ WARNING: Sensor ID mismatch (non-fatal)"
      echo "    Scene expects:  $scene_sensors_trimmed"
      echo "    Data provides:  $sensor_data_sensors_trimmed"
    else
      echo "  ✓ Sensor IDs match"
    fi
  elif [ -n "$sensor_data_sensors_trimmed" ]; then
    echo "  ℹ Sensor data available: $sensor_data_sensors_trimmed"
  fi
  
  sensor_topics=$(jq -r '.messages[].topic' "$SENSOR_FILE" 2>/dev/null | sort -u | tr '\n' ' ')
  if [ -n "$sensor_topics" ]; then
    echo "  Topics: $sensor_topics"
    if echo "$sensor_topics" | grep -qv "scenescape/data/sensor/"; then
      echo "  ⚠ WARNING: Some sensor topics don't follow convention"
    fi
  fi
fi

rm -rf "$temp_dir"

# Return success with camera list
echo
echo "✓ Validation complete"
echo "Cameras: $scene_cameras_trimmed"
[ -n "$scene_sensors_trimmed" ] && echo "Sensors: $scene_sensors_trimmed"
exit 0
