# Metro Apps Builder

The Metro AI Suite **Metro Apps Builder** is a collection of reusable,
business-objective prompts that turn a plain-language goal (for example,
"I want to detect people in my camera feeds") into a running Intel® Edge AI
application. Each prompt states **only a business outcome**; no framework, model,
precision, or device and hands off to the `metro-ai-apps-builder` orchestrator
skill, which asks a few business questions, discovers the right
[open-edge-platform](https://github.com/open-edge-platform/skills) skill,
proposes a plan, and after you confirm builds the deliverable on Intel
hardware.

---

## How prompt-driven app development works

A Metro AI App development prompt is intentionally minimal. Instead of encoding
technology choices, it describes *what you want to achieve* and delegates every
technical decision to the orchestrator skill.

1. **State a business objective.** Point Copilot at the prompt matching the
   outcome you want (for example, "detect people", "count vehicles", or "flag PPE
   violations"), or simply describe your goal in your own words.
2. **The orchestrator takes over.** The
   [`metro-ai-apps-builder`](https://github.com/open-edge-platform/skills)
   skill runs a short **business** Q&A, what you want to achieve, your inputs,
   where it runs, and your hardware.
3. **Skill discovery.** From your answers the orchestrator discovers the relevant
   open-edge-platform skill(s) — vision analytics, multi-camera scene analysis,
   conversational Q&A/RAG, video search and summarization, multimodal embeddings,
   model download/convert, model training, or robotics.
4. **Plan and confirm.** It presents the deliverable, the skill(s) that will
   build it, and the inferred technology, and waits for your approval. Nothing is
   created before you confirm.
5. **Build by delegation.** After you approve, the orchestrator builds the
   deliverable by delegating to the chosen skill(s) — for a computer-vision
   analytics stack it hands off to the `metro-ai-apps-recipe` vision delegate.

---

## Writing your own prompt

You don't need to learn any special format. Just describe the outcome you want in
plain language and hand off to the `metro-ai-apps-builder` skill. Copy the
template below into Copilot (or your AI agent tool), replace the objective with
your own, and run it:

```text
I want to <state the business outcome in one or two sentences>.

Use the metro-ai-apps-builder skill to guide this process. Install and invoke it:

npx skills add open-edge-platform/skills --skill metro-ai-apps-builder
```

---

## Metro Prompt Library

Ready-to-use, business-objective prompts you can copy and paste directly into
Copilot or your AI agent tool. Each tile is loaded from a prompt file in the
`prompts/` directory — click one to view the full prompt, then copy it.

<link rel="stylesheet" href="../../_static/prompt-library-files/prompt-catalog.css">
<div id="prompt-catalog" class="prompt-catalog" data-prompts-path="../../_static/prompt-library-files/prompts/" data-prompts="smart-city-object-detection,crowd-safety-monitoring,traffic-flow-monitoring,unauthorized-access-detection,worker-safety-compliance">
  <p class="prompt-catalog-loading">Loading prompts…</p>
</div>
<script src="../../_static/prompt-library-files/prompt-catalog.js"></script>

