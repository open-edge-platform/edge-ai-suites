# Ambiguous modality — clarify before routing

**User (business objective):**
> I want to catch problems early on my production line before they become
> expensive failures.

**Orchestrator (Step 1 — clarify before routing):**
The objective doesn't say what feeds the decision, so ask a **business**
disambiguation (still no technology):
1. What kind of "problem" are you trying to catch — something you'd **see**
   (a visual defect, a misaligned part, a leak), something you'd **measure**
   (unusual vibration, pressure, temperature, power draw), or **both together**
   (e.g. a camera confirms what a sensor already flagged)?
2. Do you already have a camera pointed at the process, sensors wired up, or
   neither yet?
3. Quick demo, a single-host solution, or a cluster?

**Discovery (Step 2):** route on the answer using
[`../references/SKILL_CATALOG.md`](../references/SKILL_CATALOG.md):
- visual-only defect → **`metro-ai-app-recipe`**
- measurement-only anomaly → **`manufacturing-timeseries-app-recipe`**
  (or `time-series-analytics-user` if no dashboard/scaffold is wanted)
- both, correlated into one verdict → **`manufacturing-multimodal-app-recipe`**

If still unclear after question 1, present **two** candidate plans (e.g.
vision-only vs the full fusion stack) and let the user pick, rather than
guessing which modality matters more.

**Plan (Step 4):** once the branch is chosen, propose the concrete
deliverable + skill + inferred technology and **wait for confirmation**
before building.

**Key behavior:** never guess "fusion" just because both a camera and a
sensor exist somewhere in the process — only route to
`manufacturing-multimodal-app-recipe` when the user confirms both signals
must combine into **one** decision. Clarify the business intent first, route
deterministically, then confirm.
