#!/bin/bash
set -e

API="https://localhost"
USER="admin"
if [ -z "${SUPASS:-}" ]; then
  echo "Error: SUPASS is not set. Please set SUPASS using export with your scenescape password."
  echo "Example: export SUPASS='your_password'"
  exit 1
fi
PASS="$SUPASS"

# 1. Get token
echo "[1/4] Authenticating..."
TOKEN=$(curl -sf -X POST "$API/api/v1/auth" \
  --insecure \
  -d "username=$USER&password=$PASS" | jq -r '.token')
echo "      Token: ${TOKEN:0:10}..."

# 2. Create scene
echo "[2/4] Creating scene: hota-scene"
SCENE_UID=$(curl -sf -X POST "$API/api/v1/scene" \
  --insecure \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"hota-scene","use_tracker":true,"output_lla":false}' \
  | jq -r '.uid')
echo "      Scene UID: $SCENE_UID"

# 3. Add Cam_x1_0
echo "[3/4] Adding camera: Cam_x1_0  (rtsp://localhost:8554/Cam_x1_0)"
CAM1_UID=$(curl -sf -X POST "$API/api/v1/camera" \
  --insecure \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Cam_x1_0\",\"scene\":\"$SCENE_UID\",
       \"intrinsics\":{\"fx\":905,\"fy\":905,\"cx\":960,\"cy\":540}}" \
  | jq -r '.uid')
echo "      Camera 1 UID: $CAM1_UID"

# 4. Add Cam_x2_0
echo "[4/4] Adding camera: Cam_x2_0  (rtsp://localhost:8554/Cam_x2_0)"
CAM2_UID=$(curl -sf -X POST "$API/api/v1/camera" \
  --insecure \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Cam_x2_0\",\"scene\":\"$SCENE_UID\",
       \"intrinsics\":{\"fx\":905,\"fy\":905,\"cx\":960,\"cy\":540}}" \
  | jq -r '.uid')
echo "      Camera 2 UID: $CAM2_UID"

echo ""
echo "=== Done ==="
echo "  Scene UID  : $SCENE_UID"
echo "  Cam_x1_0   : $CAM1_UID"
echo "  Cam_x2_0   : $CAM2_UID"
