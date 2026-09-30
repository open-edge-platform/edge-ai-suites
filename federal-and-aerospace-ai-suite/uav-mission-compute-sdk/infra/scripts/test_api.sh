#!/usr/bin/env bash

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

BASE="${1:-http://localhost:8080}"
PASS=0; FAIL=0

pass() { echo "[PASS] $*"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $*"; FAIL=$((FAIL + 1)); }

check() {
  local label="$1" path="$2" want="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$path")
  if [[ "$code" == "$want" ]]; then
    pass "$label (HTTP $code)"
  else
    fail "$label (HTTP $code, expected $want)"
  fi
}

echo "=== PX4 MAVLink Bridge — API smoke test ==="
echo "Target: $BASE"
echo ""

check "Health"    /health
check "Telemetry" /telemetry

echo ""
curl -s "$BASE/health"    | python3 -m json.tool
echo ""
curl -s "$BASE/telemetry" | python3 -m json.tool

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
