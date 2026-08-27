# Discovering & installing skills at runtime

How the `metro-ai-apps-builder` orchestrator confirms the live catalog, checks
what is already installed, and adds a delegate skill on demand. Load this in
Step 2 only when [`SKILL_CATALOG.md`](SKILL_CATALOG.md) looks stale, a mapping is
ambiguous, or a chosen delegate is not installed locally.

## 1. Prefer the curated catalog first

[`SKILL_CATALOG.md`](SKILL_CATALOG.md) is the fast path — it already maps
business objectives to skills. Only fall through to live discovery when it does
not resolve the objective or you need to confirm a skill still exists / its exact
name.

## 2. Check what is already installed in this session

A delegate may already be available (installed skills expose their own
`SKILL.md`). Look before adding:

```bash
# Skills the CLI has installed for the active agent(s)
npx skills@1.5.23 list 2>/dev/null || true

# Repos commonly used in these environments (adjust to your setup)
ls .github/skills 2>/dev/null                 # skills shipped in this repo
ls ~/.copilot/skills ~/.claude/skills 2>/dev/null   # agent skill homes
```

`metro-ai-apps-recipe` ships in **this** repo under `.github/skills/`, so it is
always available — no install needed to delegate to it.

## 3. Refresh the live index (when the catalog may be stale)

The authoritative index of open-edge-platform skills is the repo's
`skills-config.json` plus the `.agents/skills/` directory:

```bash
# Machine-readable product/skill index
curl -fsSL https://raw.githubusercontent.com/open-edge-platform/skills/main/skills-config.json

# Human index (README) and per-skill folders
gh api repos/open-edge-platform/skills/contents/.agents/skills --jq '.[].name' 2>/dev/null \
  || curl -fsSL https://api.github.com/repos/open-edge-platform/skills/contents/.agents/skills
```

Read a candidate skill's `description` (its `SKILL.md` frontmatter) to confirm it
fits the objective before you commit to it in the plan:

```bash
curl -fsSL https://raw.githubusercontent.com/open-edge-platform/skills/main/.agents/skills/<name>/SKILL.md \
  | sed -n '1,25p'
```

Match on the `description` "Use this skill when…" trigger phrases — that is what
each skill author wrote to signal relevance.

## 4. Add a delegate skill on demand (Step 5 only, after confirmation)

Do not install anything during discovery/planning. After the user approves the
plan, add each not-yet-installed delegate:

```bash
# Add one skill from the catalog repo
npx skills@1.5.23 add open-edge-platform/skills --skill <skill-name>

# Some products live in their own repos (see skills-config.json "repo"/"path"),
# e.g. DL Streamer's coding agent:
npx skills@1.5.23 add open-edge-platform/dlstreamer --skill dlstreamer-coding-agent
```

Use the `repo` + `path` fields from `skills-config.json` when a skill is **not**
in the main skills repo (chatqna, vss, multimodal-embedding, vdms, model-download
live in `open-edge-platform/edge-ai-libraries`; getitune/geti and physicalai in
their own repos).

## 5. Fallbacks

- **`npx` unavailable** → read the skill's `SKILL.md` directly from GitHub (raw
  URL above) and follow it in-context, or ask the user to install Node 20+.
- **Network blocked** → rely on [`SKILL_CATALOG.md`](SKILL_CATALOG.md) and any
  already-installed skills; state the limitation in the plan.
- **No match anywhere** → tell the user plainly; suggest the closest catalog
  entry or a custom-code path. Never fabricate a skill name.

## 6. Keeping the catalog in sync

When the upstream index changes, update the rows in
[`SKILL_CATALOG.md`](SKILL_CATALOG.md) to match `skills-config.json`. Keep the
mapping **business-objective-first** (what the user says → skill), not
technology-first.
