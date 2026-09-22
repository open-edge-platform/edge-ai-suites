# AGENTS.md — Prompt Library

Authoritative instructions for AI agents working in
`metro-ai-suite/prompt-library/`. This file overrides the monorepo defaults for
this component. **Read this file — do not eagerly read or parse the rest of the
directory.**

## Do NOT eagerly load this directory

This is a **static content library**, not application code. Its files
(`prompts/*.yaml`, `.github/skills/**`, `example-prompts/**`, `evals/*.json`) are
large, numerous, and change the model's context budget without helping most
tasks. To keep sessions fast and cheap:

- **Do not** bulk-read, recursively `cat`/`view`, or "index/parse the prompt
  library" at the start of a session or task.
- **Do not** load `prompts/*.yaml`, `example-prompts/`, `references/`, or
  `evals/` unless the current task is explicitly about that specific file.
- Prefer **targeted** `grep`/`glob` for one file over reading the tree. Open at
  most the single file you need, then stop.
- Skip this directory entirely for tasks scoped to other components.

If you only need to know *what this library is*, use the summary below instead of
opening the files.

## What this library is (summary — read this instead of the files)

Reusable **business-objective** prompts in YAML that state only an outcome (e.g.
"detect people in my camera feeds") and hand off to the
`metro-ai-app-builder` orchestrator skill. Prompts carry **no** technology or
parameters — the skill infers all of that.

- `prompts/*.yaml` — one minimal business-objective prompt per use-case
  (object / person / vehicle / unauthorized-access / worker-safety). Schema:
  `name`, `description`, `prompt` (block scalar), `tags`.
- `.github/skills/metro-ai-app-builder/` — the orchestrator skill (Q&A → skill
  discovery → plan → delegate). This is the only skill that ships **in this
  directory**.
- `README.md` — full schema, architecture, and how-to.

## Skill locations (important)

- **`metro-ai-app-builder`** lives here:
  `.github/skills/metro-ai-app-builder/`.
- **`metro-ai-app-recipe`** (the vision delegate) has been **moved out** of this
  directory to
  `../metro-vision-ai-app-recipe/.github/skills/metro-ai-app-recipe/`.
  Links from this directory to the recipe skill must point there.

## Scope & editing rules

- Stay within this directory. Do not modify the recipe skill or other components
  from here unless explicitly asked.
- To add a **vision** use-case: copy an existing `prompts/*.yaml`, change only the
  business-objective wording — no per-use-case config is needed.
- To route a **new domain**: edit the routing table in
  `.github/skills/metro-ai-app-builder/references/SKILL_CATALOG.md`.
- Keep prompts **business-only** — never add a model, framework, precision, or
  device to a prompt.
