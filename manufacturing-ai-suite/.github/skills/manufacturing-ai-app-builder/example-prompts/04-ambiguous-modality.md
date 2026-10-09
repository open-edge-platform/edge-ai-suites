# Ambiguous modality — clarify before routing

**User:**
> I want to catch problems early on my production line before they become
> expensive failures.

This doesn't say what feeds the decision, so the orchestrator asks one
clarifying question first: is this something you'd **see** (camera),
**measure** (sensor), or **both together**? It then routes on the answer,
using [`../references/SKILL_CATALOG.md`](../references/SKILL_CATALOG.md):

- Visual-only → **`metro-ai-app-recipe`**
- Measurement-only → **`manufacturing-app-recipe`** (`{{DEPLOYMENT}}=ts`)
- Both, correlated into one verdict → **`manufacturing-app-recipe`**
  (`{{DEPLOYMENT}}=multimodal`)

It never guesses "multimodal" just because a camera and a sensor both exist
somewhere in the process — only when the user confirms both signals must
combine into one decision.
