# Grading Component

## Notes

1. This grading workflow currently supports exam layouts commonly used in mainland China only.
2. Grading quality depends heavily on the model capability.
3. The same model may produce different grading results for the same question across runs.
4. Different models may produce noticeably different final scores.
5. Text recognition is not 100% accurate.
6. In tested Qwen3.5 9B scenarios, INT4 quantization performs noticeably worse than INT8, while INT8 takes longer to run.
7. The grading workflow assumes student papers are organized by directory, with each student separated by folder.

## Usage Guide

1. Prepare a rubric file for the target exam and place it under [rubrics].
2. The grading panel on the right side provides adjustable parameters.
3. Before starting grading, confirm whether the exam page layout is single-column or two-column.
4. For the rest of the configuration options, see [doc/config-reference.md].

## How to Start the Grading Service

The grading service is a thin orchestrator. To be fully functional it needs three
backend providers, all reachable through `config.yaml` under
`grading.provider`. Only `grading` is provided by this component; the VLM and
layout-detection providers are external services, and OCR is bundled in-process.

```yaml
# grading/config.yaml
grading:
  provider:
    layout_detection: http://127.0.0.1:9902
    vlm_provider:      http://127.0.0.1:8000
    ocr_provider:      openvino_local
```

### 1. Layout-detection provider

Splits each rendered page into layout regions (text / table / formula / title…)
used by section splitting.

```bash
cd providers/layout_detection_service
python layout_detection_server.py
```

### 2. VLM provider

Grades sections/text. This is an **external service**, not started by this
component. The grading client speaks **OpenAI-compatible chat-completions** —
see `services/vlm_client.py`. It POSTs a page image (as a base64
`image_url`) plus the grading prompt to:

```
{vlm_provider}/v1/chat/completions
```

So `vlm_provider` must point at an OpenAI-compatible endpoint (e.g. a local
vLLM / TGI server, or a cloud gateway exposing that route).

### 3. OCR provider

Reads text inside detected regions for the section-splitting step. It runs
**in-process inside the grading service** (no separate process), over
OpenVINO + PaddleOCR models.

### 4. Grading (main program)

The orchestrator that ties the pipeline together and exposes the API.

```bash
python grading_service.py
```

---

## Typical flow

```text
1. GET  /api/v1/health                                confirm backends green
2. POST /api/v1/grading/tasks                          create task -> task_id
3. GET  /api/v1/grading/tasks/{task_id}                poll until status=COMPLETED
4. GET  /api/v1/grading/tasks/{task_id}/summary        overall summary
5. GET  /api/v1/grading/tasks/{task_id}/students/{slot}/result   per-student detail
```

Results are also written under `components/grading/outputs/<task_id>/`
(`summary.json`, `<student>/grading_result.json`, and per-step intermediates).
