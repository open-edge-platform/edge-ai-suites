# Steps to Enable VDMS Re-ID for Smart Corridor (Fresh Repo)

All paths relative to `metro-vision-ai-app-recipe`.

---

## Step 1: Run install.sh

```bash
./install.sh smart-corridor
```

**Why:** Sets up `.env`, generates TLS certs, downloads videos, downloads vehicle-reid-0001 model, and creates `docker-compose.yml` from `compose-scenescape.yml`.

---

## Step 2: Add VDMS client cert generation to generate_secrets.sh

**File:** `smart-corridor/src/secrets/generate_secrets.sh`

Add this block after the VDMS server cert section (after the `scenescape-vdms-s.crt` generation):

```bash
# Generate VDMS client key and certificate
echo Generating vdms-c.key
openssl ecparam -name secp384r1 -genkey -noout -out $SECRETSDIR/certs/scenescape-vdms-c.key
echo Generating CSR for vdms-client.$CERTDOMAIN
openssl req -new -out $SECRETSDIR/certs/scenescape-vdms-c.csr -key $SECRETSDIR/certs/scenescape-vdms-c.key \
    -config <(sed -e "s/##CN##/vdms-client.$CERTDOMAIN/" -e "s/##SAN##/DNS.1=vdms.$CERTDOMAIN/" \
    -e "s/##KEYUSAGE##/clientAuth/" $EXEC_PATH/openssl.cnf)
echo Generating certificate for vdms-client.$CERTDOMAIN
openssl x509 -passin pass:$CERTPASS -req -in $SECRETSDIR/certs/scenescape-vdms-c.csr \
    -CA $SECRETSDIR/certs/scenescape-ca.pem -CAkey $SECRETSDIR/ca/scenescape-ca.key -CAcreateserial \
    -out $SECRETSDIR/certs/scenescape-vdms-c.crt -days 360 -extensions x509_ext -extfile \
    <(sed -e "s/##SAN##/DNS.1=vdms.$CERTDOMAIN/" -e "s/##KEYUSAGE##/clientAuth/" $EXEC_PATH/openssl.cnf)
# Fix permissions: scene container runs as UID 1001, key is created by UID 1000
chmod 644 $SECRETSDIR/certs/scenescape-vdms-c.key
```

**Why:** The scene controller needs TLS client certs to connect to VDMS. `generate_secrets.sh` creates server certs but not client certs. Additionally, the key is created with mode `600` (owner-only) by UID 1000, but the scene container runs as UID 1001 (scenescape user baked into the image) — without `chmod 644`, the container gets `PermissionError` reading the key.

---

## Step 3: Enable re-id in pipeline config

**File:** `smart-corridor/src/dlstreamer-pipeline-server/config.json`

Two changes per pipeline:

### 3a. Change metadatagenpolicy to reidPolicy

In every pipeline's `payload.parameters.camera_config`, change:

```json
"metadatagenpolicy": "detectionPolicy"
```

to:

```json
"metadatagenpolicy": "reidPolicy"
```

15 pipelines (5 CPU + 5 GPU + 5 NPU).

### 3b. Add gvainference for vehicle-reid-0001

Insert a `gvainference` element into each pipeline's GStreamer string, after the `! queue !` that follows `gvadetect`, and before `gvametaconvert`:

```
! queue ! gvainference model=/home/pipeline-server/models/vehicle_reid/FP16/vehicle-reid-0001.xml inference-region=roi-list ! gvametaconvert
```

**CPU pipelines** (`intersection-cam1` through `intersection2-cam5`) — insert after `! queue !`:

```
... openvino.xml ! queue ! gvainference model=/home/pipeline-server/models/vehicle_reid/FP16/vehicle-reid-0001.xml inference-region=roi-list ! gvametaconvert add-tensor-data=true ...
```

**GPU pipelines** (`intersection-cam*-gpu`) — insert after `! queue !`. **Important:** Do NOT add `device=GPU` to `gvainference` — reid inference must run on CPU to avoid `CL_OUT_OF_RESOURCES`:

```
... openvino.xml ! queue ! gvainference model=/home/pipeline-server/models/vehicle_reid/FP16/vehicle-reid-0001.xml inference-region=roi-list ! gvametaconvert add-tensor-data=true ...
```

**NPU pipelines** (`intersection-cam*-npu`) — same as GPU, insert after `! queue !` without any `device=` flag:

```
... openvino.xml ! queue ! gvainference model=/home/pipeline-server/models/vehicle_reid/FP16/vehicle-reid-0001.xml inference-region=roi-list ! gvametaconvert add-tensor-data=true ...
```

**Why:** `gvainference` runs the vehicle-reid-0001 model on each detected ROI to produce 512-dimensional embeddings. `reidPolicy` tells `sscape_adapter.py` to extract those embeddings and publish them. Reid inference runs on CPU regardless of the detection device — running it on GPU causes `CL_OUT_OF_RESOURCES` when multiple pipelines share the GPU.

---

## Step 4: Fix sscape_adapter.py — dynamic struct.pack + metadata format

**File:** `smart-corridor/src/dlstreamer-pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py`

In the `reidPolicy()` function (~line 114), replace:

```python
  v = struct.pack("256f",*reid_vector)
  pobj['reid'] = base64.b64encode(v).decode('utf-8')
```

with:

```python
  n = len(reid_vector)
  v = struct.pack(f"{n}f",*reid_vector)
  reid_b64 = base64.b64encode(v).decode('utf-8')
  if 'metadata' not in pobj:
    pobj['metadata'] = {}
  pobj['metadata']['reid'] = {
    'embedding_vector': reid_b64,
    'model_name': 'vehicle-reid-0001'
  }
```

**Why:** Two bugs in the original:

- `"256f"` hardcoded but vehicle-reid-0001 outputs 512 floats — causes `struct.pack` crash
- `pobj['reid']` at top level — SceneScape schema expects `metadata.reid` as a dict with `embedding_vector` and `model_name`

---

## Step 5: Create patched vdms_adapter_patched.py

**File:** `smart-corridor/src/vdms_adapter_patched.py` (new file)

Copy the original from inside the container image and apply these changes:

- Line 17: `DIMENSIONS = 256` → `DIMENSIONS = int(os.getenv("VDMS_DIMENSIONS", "512"))`
- Line 150: `if vec_array.shape[0] != 256:` → `if vec_array.shape[0] != self.dimensions:`
- Line 151: Update the warning message to use `self.dimensions` instead of hardcoded `(256,)`

**Why:** The original hardcodes 256 dimensions and silently drops all 512-dim vectors from vehicle-reid-0001.

---

## Step 6: Create patched moving_object_patched.py

**File:** `smart-corridor/src/moving_object_patched.py` (new file)

Copy the original from inside the container image and fix three lines:

**Line 146** (`_decodeReIDVector`):

```python
# Original:
self.reid['embedding_vector'] = np.array(struct.unpack("256f", vector)).reshape(1, -1)
# Fixed:
n = len(vector) // 4
self.reid['embedding_vector'] = np.array(struct.unpack(f"{n}f", vector)).reshape(1, -1)
```

**Line 377** (`dump`):

```python
# Original:
vector = struct.pack("256f", *vector)
# Fixed:
n = len(vector)
vector = struct.pack(f"{n}f", *vector)
```

**Line 393** (`load`):

```python
# Original:
self.reid['embedding_vector'] = np.array(struct.unpack("256f", vector)).reshape(1, -1)
# Fixed:
n = len(vector) // 4
self.reid['embedding_vector'] = np.array(struct.unpack(f"{n}f", vector)).reshape(1, -1)
```

**Why:** Same 256-vs-512 dimension mismatch — `struct.pack/unpack("256f")` crashes on 512-float data.

---

## Step 7: Update compose-scenescape.yml

**File:** `compose-scenescape.yml`

**7a.** In `scene` service `volumes:`, add after `pgserver-media` line:

```yaml
      - ./${SAMPLE_APP}/src/vdms_adapter_patched.py:/usr/local/lib/python3.11/site-packages/controller/vdms_adapter.py:ro
      - ./${SAMPLE_APP}/src/moving_object_patched.py:/usr/local/lib/python3.11/site-packages/controller/moving_object.py:ro
```

**7b.** In `scene` service `secrets:`, add after `root-cert` entry:

```yaml
      - source: vdms-client-cert
        target: certs/scenescape-vdms-c.crt
      - source: vdms-client-key
        target: certs/scenescape-vdms-c.key
```

**7c.** In bottom-level `secrets:` definitions, add:

```yaml
  vdms-client-cert:
    file: ./${SAMPLE_APP}/src/secrets/certs/scenescape-vdms-c.crt
  vdms-client-key:
    file: ./${SAMPLE_APP}/src/secrets/certs/scenescape-vdms-c.key
```

**Why:** Volume mounts override the buggy 256-dim code inside the container image. Client cert secrets enable TLS to VDMS.

---

## Step 8: Regenerate docker-compose.yml and bring up

```bash
./install.sh smart-corridor
export SAMPLE_APP=smart-corridor GID=$(id -g) SUPASS=admin
docker compose up -d
```

**Why:** `install.sh` regenerates `docker-compose.yml` from the updated `compose-scenescape.yml`, ensuring all changes are included.

---

## Verification

After services are running, verify re-id is working:

```bash
# 1. Check VDMS descriptor set exists with 512 dimensions
cat > /tmp/vdms_check.py << 'EOF'
import vdms, json
db = vdms.vdms(
    use_tls=True,
    ca_cert_file='/run/secrets/certs/scenescape-ca.pem',
    client_cert_file='/run/secrets/certs/scenescape-vdms-c.crt',
    client_key_file='/run/secrets/certs/scenescape-vdms-c.key'
)
db.connect('vdms.scenescape.intel.com')
res, _ = db.query([{"FindDescriptorSet": {"set": "reid_vector"}}])
print(json.dumps(res, indent=2))
EOF
docker cp /tmp/vdms_check.py $(docker ps -qf name=scene):/tmp/vdms_check.py
docker exec $(docker ps -qf name=scene) python3 /tmp/vdms_check.py

# 2. KNN similarity search (run after vehicles have been detected)
cat > /tmp/vdms_knn.py << 'EOF'
import vdms, json, numpy as np, struct
db = vdms.vdms(
    use_tls=True,
    ca_cert_file='/run/secrets/certs/scenescape-ca.pem',
    client_cert_file='/run/secrets/certs/scenescape-vdms-c.crt',
    client_key_file='/run/secrets/certs/scenescape-vdms-c.key'
)
db.connect('vdms.scenescape.intel.com')
ref_vector = np.zeros(512, dtype='float32')
ref_blob = struct.pack('512f', *ref_vector)
q = [{"FindDescriptor": {
    "set": "reid_vector",
    "k_neighbors": 10,
    "results": {"list": ["rvid", "_id", "_distance"], "blob": False}
}}]
res, _ = db.query(q, [[ref_blob]])
print(json.dumps(res, indent=2))
EOF
docker cp /tmp/vdms_knn.py $(docker ps -qf name=scene):/tmp/vdms_knn.py
docker exec $(docker ps -qf name=scene) python3 /tmp/vdms_knn.py
```

---

## Summary: 8 changes, 5 root causes

| Root Cause | Steps | Files |
|---|---|---|
| Missing reid inference in pipelines | 3b | `config.json` |
| Reid on GPU crashes (CL_OUT_OF_RESOURCES) | 3b | `config.json` (use CPU for gvainference) |
| 256 vs 512 dimensions | 4, 5, 6 | `sscape_adapter.py`, `vdms_adapter_patched.py`, `moving_object_patched.py` |
| Wrong reid data format | 4 | `sscape_adapter.py` |
| Missing VDMS client certs | 2, 7b, 7c | `generate_secrets.sh`, `compose-scenescape.yml` |
| Client key permissions (UID 1000→1001) | 2 | `generate_secrets.sh` |
