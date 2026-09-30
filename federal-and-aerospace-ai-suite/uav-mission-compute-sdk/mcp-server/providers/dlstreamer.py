# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""DL Streamer tool handlers."""

import os
import subprocess
from pathlib import Path

# Default to workspace root, override with WORKSPACE_DIR env var
WORKSPACE = Path(os.getenv("WORKSPACE_DIR", "/home/user/nathsudi"))
REPO = WORKSPACE / "dlstreamer"
SKILL_DIR = REPO / ".github/skills/dlstreamer-coding-agent"


def build_pipeline(arguments: dict) -> str:
    skill_path = SKILL_DIR / "SKILL.md"
    refs = SKILL_DIR / "references"

    return f"""## DL Streamer Pipeline Builder

**Request:** {arguments.get('description', '')}
**Video source:** {arguments.get('video_source', 'Not specified — ask user')}
**Model:** {arguments.get('model', 'Not specified — ask user')}
**App type:** {arguments.get('app_type', 'python')}
**Device:** {arguments.get('device', 'AUTO')}

### Procedure

Follow the full skill at: `{skill_path}`

**Step 0 — Gather requirements** (if missing above):
  See: `{refs}/questionnaire.md`

**Step 1 — Pull Docker image** (async):
  ```bash
  WEEKLY_TAG=$(curl -s "https://hub.docker.com/v2/repositories/intel/dlstreamer/tags?name=weekly-ubuntu24&page_size=25&ordering=-last_updated" | python3 -c "import sys,json; print(sorted([r['name'] for r in json.load(sys.stdin)['results']])[-1])")
  docker pull "intel/dlstreamer:${{WEEKLY_TAG}}"
  ```

**Step 2 — Prepare models**:
  See: `{refs}/model-preparation.md`

**Step 3 — Design pipeline**:
  See: `{refs}/pipeline-construction.md` and `{refs}/sample-index.md`

**Step 4 — Generate application**:
  See: `{refs}/design-patterns.md`

**Step 5 — Run & validate in Docker**:
  See: `{refs}/debugging-hints.md`

### Examples
  `{SKILL_DIR}/examples/`
"""


def list_samples(arguments: dict) -> str:
    sample_index = SKILL_DIR / "references/sample-index.md"
    filter_term = arguments.get("filter", "").lower()
    sample_type = arguments.get("type", "all")

    if not sample_index.exists():
        return "DLStreamer sample index not found. Run setup.sh first."

    content = sample_index.read_text()

    if filter_term:
        lines = content.split("\n")
        filtered = [l for l in lines if filter_term in l.lower() or l.startswith("#") or l.startswith("|--")]
        content = "\n".join(filtered)

    if sample_type == "python":
        sections = content.split("## Command Line Samples")
        content = sections[0]
    elif sample_type == "cli":
        sections = content.split("## Command Line Samples")
        content = "## Command Line Samples" + sections[1] if len(sections) > 1 else content

    return content


def run_sample(arguments: dict) -> str:
    sample_path = arguments.get("sample_path", "")
    video_input = arguments.get("video_input", "")
    device = arguments.get("device", "CPU")

    full_path = REPO / sample_path
    if not full_path.exists():
        return f"Sample not found: {full_path}"

    return f"""## Run DL Streamer Sample

**Path:** {full_path}
**Video:** {video_input or 'No input specified'}
**Device:** {device}

### Command
```bash
docker run --init --rm \\
  -u "$(id -u):$(id -g)" \\
  -v "{full_path}":/app -w /app \\
  --device /dev/dri \\
  intel/dlstreamer:<WEEKLY_TAG> \\
  python3 *.py --input {video_input} --device {device}
```

Read the sample README for specific instructions:
  `{full_path}/README.md`
"""


def download_models(arguments: dict) -> str:
    model_name = arguments.get("model_name", "")
    source = arguments.get("source", "openvino")
    output_dir = arguments.get("output_dir", "models/")

    scripts = {
        "openvino": f"bash {REPO}/samples/download_public_models.sh",
        "huggingface": f"python3 {REPO}/scripts/download_models/download_hf_models.py --model {model_name}",
        "ultralytics": f"python3 {REPO}/scripts/download_models/download_ultralytics_models.py --model {model_name}",
    }

    cmd = scripts.get(source, scripts["openvino"])

    return f"""## Download Model

**Model:** {model_name}
**Source:** {source}
**Output:** {output_dir}

### Command
```bash
{cmd} --output_dir {output_dir}
```
"""


HANDLERS = {
    "build_pipeline": build_pipeline,
    "list_samples": list_samples,
    "run_sample": run_sample,
    "download_models": download_models,
}
