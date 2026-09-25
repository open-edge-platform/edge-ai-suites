# Discovering & installing skills at runtime

How the `manufacturing-ai-app-builder` orchestrator confirms a delegate is
available locally, and adds one on demand if it isn't. Load this in Step 2
only when [`SKILL_CATALOG.md`](SKILL_CATALOG.md) doesn't resolve the
objective or a chosen delegate's availability is unclear.

## 1. Prefer the curated catalog first

[`SKILL_CATALOG.md`](SKILL_CATALOG.md) is the fast path — it already maps
manufacturing business objectives to skills. Only fall through to discovery
below when it does not resolve the objective or you need to confirm a skill
still exists in this workspace.

## 2. Check what is already installed locally — usually everything is

All six delegates this catalog can route to already ship in this workspace:

```bash
ls .agents/skills/manufacturing-timeseries-app-recipe \
   .agents/skills/manufacturing-multimodal-app-recipe \
   .agents/skills/metro-ai-app-recipe \
   .agents/skills/dlsps-user \
   .agents/skills/dlstreamer-coding-agent \
   .agents/skills/time-series-analytics-user 2>/dev/null
```

If all six are present (the common case in this workspace), skip straight to
Step 5 of `SKILL.md` — no install step is needed at all.

## 3. Add a delegate skill on demand (only if missing, Step 5, after confirmation)

Do not install anything during discovery/planning. After the user approves
the plan, add any not-yet-installed delegate. `manufacturing-timeseries-app-recipe`
and `manufacturing-multimodal-app-recipe` are **not yet published upstream** —
if a target environment is missing them, copy the folder from this workspace
rather than trying to fetch them via `npx skills`. The other four are
published upstream:

```bash
# metro-ai-app-recipe, dlsps-user, time-series-analytics-user
npx skills@1.5.23 add open-edge-platform/skills --skill <skill-name>

# dlstreamer-coding-agent lives in its own repo
npx skills@1.5.23 add open-edge-platform/dlstreamer --skill dlstreamer-coding-agent
```

## 4. Refresh the live index (rarely needed)

If a delegate's own `SKILL.md` looks stale (parameters/tables don't match
what this catalog describes), re-read it directly rather than trusting a
cached mental model — delegate skills evolve independently of this
orchestrator:

```bash
sed -n '1,60p' .agents/skills/<skill-name>/SKILL.md
```

## 5. Fallbacks

- **A manufacturing recipe is missing and can't be copied** → tell the user
  plainly; offer to build the equivalent scaffold manually from the recipe's
  own `references/` design (slower, but the recipe's SKILL.md documents the
  full file layout) rather than fabricating a different skill.
- **`npx` unavailable** for one of the four upstream delegates → read its
  `SKILL.md` directly from GitHub raw and follow it in-context.
- **No match anywhere** → say so; suggest the closest catalog entry or a
  custom path. Never fabricate a skill name.

## 6. Keeping the catalog in sync

When any of the three manufacturing-domain skills' parameter tables change
(new `{{VAR}}`, new mode, new alert channel), update the corresponding row in
[`SKILL_CATALOG.md`](SKILL_CATALOG.md) so Step 3's technology inference stays
accurate.
