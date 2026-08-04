# Grading Config Reference

Configuration for the grading component lives in `components/grading/config.yaml`.
All values are read fresh from disk at task time, so edits take effect on the next
task without restarting the service. Every key listed here is actively read by the
code — there are no unused entries.

---

## `image`

Controls PDF-to-image rendering (the first pipeline step).

| Key | Type | Default | Description |
|---|---|---|---|
| `dpi` | int | 50 | Render resolution. Higher = sharper but slower and larger images. |
| `contrast_enhance` | bool | true | Apply contrast enhancement to rendered pages. |
| `contrast_factor` | float | 1.5 | Contrast multiplier when `contrast_enhance` is on. |
| `page_columns` | int | 1 | Page layout: `1` = single column, `2` = two columns. When `2`, each page is cut vertically into left/right, emitted as consecutive pages (left then right). |
| `column_split_ratio` | float | 0.55 | For `page_columns=2`, the left-column width fraction. `0.5` = split at the middle; `0.4` = left 40% / right 60%. |

Read by `services/vlm_grading_pipeline.py` → `pdf_render.py`.

---

## `vlm`

Parameters for the VLM grading calls.

| Key | Type | Default | Description |
|---|---|---|---|
| `max_tokens` | int | 4096 | Max completion tokens per VLM request (sent as `max_completion_tokens`). |
| `temperature` | float | 0.1 | VLM sampling temperature. |
| `max_image_pixels` | int | 4000000 | Section images larger than this are downscaled before being sent to the VLM. |

Read by `services/vlm_grading_pipeline.py` → `services/vlm_client.py`.

---

## `grading`

Top-level grading behaviour.

| Key | Type | Default | Description |
|---|---|---|---|
| `force_regrade` | bool | true | Re-grade a student even if a result already exists. When false, completed students are skipped. |
| `debug_mode` | bool | false | Save intermediate artifacts (rendered pages, section images, OCR crops) and emit item-level tracebacks. Off in production. |

Read by `services/grading_service_impl.py` and `services/vlm_grading_pipeline.py`.

---

## `watch`

Pacing for directory-type tasks (a task that watches a folder and grades papers as they arrive).

| Key | Type | Default | Description |
|---|---|---|---|
| `poll_interval` | int (s) | 5 | Seconds between directory scans. |
| `stable_checks` | int | 2 | Consecutive unchanged polls before a PDF is considered stable and graded. |
| `idle_timeout` | int (s) | 100 | Seconds with no new paper before a directory task auto-completes. |

Read by `services/dir_scan.py`.

> These are the defaults for directory-type grading tasks; a `POST /grading/tasks` targeting a directory inherits them.

---

## `detection_service`

Layout-detection filtering and post-processing (consumed by the layout step).

| Key | Type | Default | Description |
|---|---|---|---|
| `target_labels` | list | see config | Which detected region labels to keep (text, table, title, etc.). |
| `min_score` | float (0–1) | 0.5 | Minimum confidence to keep a detected box. |
| `sort_boxes` | bool | true | Sort boxes top-to-bottom. |
| `expand_margin` | int (px) | 10 | Expand each kept box by this margin. `0` disables expansion. |
| `merge_overlapping` | bool | false | Merge overlapping boxes. When false, `iou_threshold` has no effect. |
| `iou_threshold` | float (0–1) | 0.7 | IoU cutoff for merging — **only applied when `merge_overlapping: true`**. |

Read by `services/layout_detection.py`.

---

## `section_split`

Splits a paper into sections and stitches cross-page pieces.

| Key | Type | Default | Description |
|---|---|---|---|
| `title_labels` | list | `[paragraph_title, title]` | Detected labels that are OCR'd to find section titles. |
| `title_patterns` | map `{zh, en}` → list (regex) | see config | Patterns that identify a section heading, keyed by language. The active list is chosen from the root `app.language`. `zh` matches `一、二、`; `en` matches `SECTION I`. |
| `stitch_direction` | str | `vertical` | How to join cross-page section pieces. |
| `compress_whitespace` | bool | true | Collapse large vertical gaps in stitched images. |
| `gap_threshold` | int (px) | 120 | Only gaps larger than this are compressed. |
| `keep_margin` | int (px) | 50 | Margin left between content blocks after compression. |
| `content_pad` | int (px) | 20 | Padding added above/below each content block. |

Read by `services/section_split.py`.

### `section_split.rubric_markers`

Named markers that structure a rubric file into typed blocks, keyed by language
(`zh` / `en`, chosen from `app.language`). The slicer cuts the rubric by these
markers instead of guessing by `=====` position. Each value is a regex matching
the marker line.

| Marker | Purpose |
|---|---|
| `context` | Scenario/intro block (`[场景]` / `[CONTEXT]`) — always included in every section slice. |
| `section` | Per-section rubric block (`[章节]` / `[SECTION]`) — the block matching the current section is included. |
| `exam_info` | Paper/student header info block (`[考试信息]` / `[EXAM_INFO]`) — used by header extraction. |
| `output` | Output-format block (`[输出格式]` / `[OUTPUT_FORMAT]`) — always included. |
| `ignore` | Fill-in instructions block (`[填写注意事项]` / `[INSTRUCTIONS]`) — dropped from every slice. |

A section slice = `context` + matching `section` + `output`; `exam_info` and
`ignore` are excluded.

Read by `services/prompt_slicer.py`.

### `section_split.prompt_slicing`

Slices the rubric so each section is graded with only its relevant rubric block.

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | true | Enable rubric slicing. When false, the whole rubric is sent per section. |
| `separator` | str (regex) | `^\s*={5,}\s*$` | Lines separating rubric blocks. |
| `keep_first_block` | bool | true | Always include the first block (scenario/intro). |
| `keep_last_block` | bool | true | Always include the last block (output-format). |
| `ordinal_pattern` | map `{zh, en}` → str (regex) | see config | Extracts the leading ordinal from a heading, keyed by language; group 1 is used to match a section to its rubric block. The active pattern is chosen from `app.language`. |

Read by `services/prompt_slicer.py`.

### `section_split.header_extract`

Extracts the paper/student header info block from the rubric.

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | true | Enable header extraction. |
| `marker_pattern` | str (regex) | see config | Marks the header block in the rubric. Matches the exam-info markers (`[考试信息]` / `[EXAM_INFO]`, plus legacy `[HEADER]` / `【卷头信息】`). |
| `separator` | str (regex) | (falls back to `prompt_slicing.separator`) | Block separator; omit to reuse the slicing separator. |

Read by `services/prompt_slicer.py`.

### `section_split.header_aliases`

Maps canonical header fields to the aliases the VLM might emit (multilingual). The
code iterates the whole map, so each canonical field name and its alias list drives
what can be parsed from VLM output. Removing a field disables parsing for it.

| Canonical field | Aliases (examples) |
|---|---|
| `paper_title` | paper_title, title, paper, exam_title, 试卷标题, 标题 |
| `subject` | subject, 科目, 学科 |
| `student_name` | student_name, name, 姓名 |
| `class_name` | class_name, class, 班级 |
| `exam_number` | exam_number, exam_id, admission_number, student_id, 准考证号, 考号 |

Read by `services/result_parser.py`.

---

## UI-editable subset

The right-panel Grading Configuration surfaces and writes back a subset of these
via `GET`/`PUT /grading/config`:

- **Image / Render**: `image.dpi`, `image.page_columns`, `image.column_split_ratio`, `image.contrast_enhance`, `image.contrast_factor`
- **VLM Parameters**: `vlm.max_tokens`, `vlm.temperature`, `vlm.max_image_pixels`
- **Grading Pace**: `watch.poll_interval`, `watch.stable_checks`, `watch.idle_timeout`
- **Layout Detection**: `detection_service.min_score`, `detection_service.sort_boxes`, `detection_service.expand_margin`, `detection_service.merge_overlapping`, `detection_service.iou_threshold`

`GET /grading/config` additionally returns read-only model names — `vlm_model`,
`ocr_model`, `layout_model` — resolved from the smart-classroom config; these are
not writable through this endpoint.

Regex-heavy keys (`title_patterns`, `rubric_markers`, `ordinal_pattern`,
`header_*`) and `target_labels` are edited directly in `config.yaml`.

---

## Notes

- `idle_timeout` code fallback differs from the config value (code default 180 vs config 100). The config value wins; the fallback only applies if the key is missing.
- `iou_threshold` is inert unless `merge_overlapping` is `true`.
