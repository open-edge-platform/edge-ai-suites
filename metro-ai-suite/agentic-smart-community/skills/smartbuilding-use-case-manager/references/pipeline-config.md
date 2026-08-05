# Pipeline config for monitor binding

Operational detail for building, displaying, and reporting a monitor's
`pipeline_config`. **All cross-turn gate semantics (when to stop, what does not
count as an answer/approval, fail-closed rules) are defined in `SKILL.md` under
"Monitor pipeline gates" and are authoritative — this file never relaxes them.**
Read this file at M0; use it inside M2 (assembling fields) and M3 (display) and
in the monitor report.

`pipeline_config` is forwarded verbatim to videostream-analytics
`/register_source`. Omitting it entirely leaves the monitor on server defaults
(`motion` on, `prefilter` off, `roi` off) **and writes no `pipeline_config` to
`monitors.yaml`** — so a deliberate "off" becomes indistinguishable from "never
configured". Only two blocks are decided in this dialog — `prefilter` and
`roi`; leave every other field at its server default unless the user explicitly
asks.

## P1 — prefilter (field detail)

Prefilter drops motion clips that contain none of the target classes before they
reach the VLM, cutting false positives and cost. Enable it when the use case is
about specific objects/people; skip it when any motion is worth reviewing.

If enabled, fetch the selectable classes from the deployed model — never
hard-code them:

```
smartbuilding_monitor_ctl action=prefilter_options
```

Returns `{ enabled, model_path, class_names, labels_source, available_devices }`.
Present `class_names` and let the user pick `target_classes`. Interpret
`labels_source`:

- `embedded` — the list is authoritative (it came from the model). A class the
  user picks that is not in the list is rejected server-side with 422 at
  registration, so only offer names from `class_names`.
- `fallback_coco` — the model has no embedded labels; the list is a COCO-80
  **guess**. Warn the user and have them confirm the names explicitly.
- `unavailable` — the model could not be read (empty/missing path). Tell the
  user prefilter classes cannot be listed; either skip prefilter or proceed with
  names they supply at their own risk.

Assemble as `prefilter: { enabled: true, target_classes: [<picked>] }`.

## P2 — ROI focus (field detail)

ROI helps scenes where the subject occupies a small, low-motion part of the
frame — e.g. child-safety, where a child covers little of the image and moves
subtly, so full-frame observation risks misdetection.

ROI is **trajectory-driven, not geometry-driven**: the prefilter's YOLO hits
accumulate a union bbox per segment, and the ROI crop is that trajectory region
expanded by `expand`. There is no geometry to collect from the user.

When the user answers `P2=yes`, apply the template defaults verbatim — no
further ROI questions:

```yaml
roi:
  enabled: true
  mode: crop            # zoomed-in view of the trajectory region
  expand: 0.25          # expand the trajectory bbox by 25% on each side
  auto_split_area: 0.35 # early-split the segment when the union bbox exceeds 35% of the frame
```

- `mode: crop` (default) — crop to the trajectory region only. Other modes
  (`highlight`, `crop_and_concat`) are advanced manual config; switch only when
  the user explicitly asks (e.g. the alert semantics depend on scene context
  that a crop would cut away).
- `expand` / `auto_split_area` tuning — advanced manual config only; change
  only when the user explicitly asks.

**Dependency:** the trajectory comes from prefilter hits, so ROI silently
no-ops when prefilter is disabled. If the user answers `P1=no, P2=yes`, warn
that ROI has no trajectory source without prefilter, and ask them to either
enable prefilter (recommended) or drop ROI. Never ship `roi.enabled=true` with
`prefilter.enabled=false`.

Assemble as `roi: { enabled: true, mode: crop, expand: 0.25, auto_split_area: 0.35 }`.

## Assemble the exact config

Build the block that will be passed verbatim to `register_source`.

Child-safety example (both features on):

```yaml
pipeline_config:
  prefilter:
    enabled: true
    target_classes: [person, knife, scissors, bottle]
  roi:
    enabled: true
    mode: crop
    expand: 0.25
    auto_split_area: 0.35
```

**Explicit-off** (user answered `P1=no, P2=no`) — assemble and display the
disabled config explicitly; never omit `pipeline_config` and never send `{}`:

```yaml
pipeline_config:
  prefilter:
    enabled: false
  roi:
    enabled: false
```

## M3 decision-summary template

Alongside the exact `pipeline_config`, display this human-readable summary so a
deliberate "off" is provable:

```text
Monitor Pipeline Decision
  Prefilter: enabled | disabled
  Target Classes: <classes> | not applicable
  Labels Source: <source> | not applicable
  ROI Focus: enabled | disabled
  ROI Parameters: defaults (mode=crop, expand=0.25, auto_split_area=0.35) | <custom parameters> | not applicable
```

## Monitor report template

For an operation that only created, rebound, or updated a monitor against an
already-registered use case (no new use case authored), use the monitor-scoped
report block instead of `New Use Case`:

```text
Monitor Created | Monitor Updated
  Monitor ID: <monitor_id>
  Use Case: <use_case>
  Source URL: <source_url>
  Prefilter: enabled | disabled
  Target Classes: <classes> | not applicable
  ROI Focus: enabled | disabled
  Pipeline Config: <exact approved config>
  Persistence: enabled
```
