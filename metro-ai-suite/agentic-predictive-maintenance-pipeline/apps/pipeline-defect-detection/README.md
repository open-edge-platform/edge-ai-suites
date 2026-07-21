# Pipeline Defect Detection — Agentic Predictive Maintenance

This directory contains the use-case-specific configuration for the
**Pipeline Defect Detection** sample application, built on the
Agentic Predictive Maintenance Blueprint from `edge-ai-libraries`.

## Quick Start

```bash
cd <edge-ai-libraries>/sample-applications/agentic-predictive-maintenance
./setup.sh --use-case pipeline-defect-detection \
  --use-case-dir <path-to-this-directory>
```

## Directory Structure

```
apps/pipeline-defect-detection/
├── configs/
│   ├── agents.yaml                    # Agent pipeline configuration
│   ├── pipeline-server-config.json    # DL Streamer pipeline definition
│   └── policy_fallback.json           # Rule-based fallback thresholds
├── models/
│   └── model_list.txt                 # Models to download at startup
├── prompts/
│   └── pipeline-defect-detection.txt  # LLM prompts (section-based)
└── .env_pipeline-defect-detection     # Environment variable overrides
```

## Defect Classes

| Class       | Description                     | Default Threshold |
|-------------|----------------------------------|-------------------|
| Rupture     | Pipeline wall rupture            | 0.60              |
| Deformation | Structural deformation           | 0.70              |
| Disconnect  | Pipeline segment disconnection   | 0.65              |
| Obstacle    | Foreign obstacle in pipeline     | 0.80              |

## Adapting to a New Use Case

To create a new use case (e.g., weld defect detection):

1. Copy this directory: `cp -r pipeline-defect-detection weld-defect-detection`
2. Update `configs/agents.yaml` — change `use_case_id` and defect classes
3. Update `configs/pipeline-server-config.json` — point to new model
4. Update `configs/policy_fallback.json` — set per-class thresholds
5. Update `prompts/weld-defect-detection.txt` — domain-specific prompts
6. Copy the model XML to `models/model_list.txt`
7. Run: `./setup.sh --use-case weld-defect-detection`

No code changes required.
