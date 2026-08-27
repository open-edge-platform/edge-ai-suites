# Ambiguous objective — discovery + clarify + route

**User (business objective):**
> I want to use AI with my cameras. Not sure where to start.

**Orchestrator (Step 1 — clarify before routing):**
The objective is under-specified, so ask a **business** disambiguation (still no
technology):
1. What do you want the cameras to help you *do*? Options in plain terms:
   - **Spot / count things** in the live feed and alert on them (e.g. people,
     vehicles, PPE, empty shelves).
   - **Search or summarize recorded video** ("find the clip where…").
   - **Track something across several cameras** as it moves through a space.
2. Live cameras now, or recorded footage?
3. Quick demo, a single-host solution, or a cluster?

**Discovery (Step 2):** route on the answer using
[`../references/SKILL_CATALOG.md`](../references/SKILL_CATALOG.md):
- spot/count/alert on live feed → **`metro-ai-apps-recipe`**
- search/summarize recordings → **`vss-deploy`** (+ `vss-search-index` /
  `vss-summarize-video`)
- cross-camera tracking → **`scenescape-setup`** via the recipe's Scenescape path

If still unclear, load [`../references/DISCOVERY.md`](../references/DISCOVERY.md)
to confirm the live catalog, then present **two** candidate plans and let the
user pick.

**Plan (Step 4):** once the branch is chosen, propose the concrete deliverable +
skill + inferred technology and **wait for confirmation** before building.

**Key behavior:** never guess a full build from a vague prompt — clarify the
business intent first, route deterministically, then confirm.
