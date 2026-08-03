# Wandering Sample Agent Guidance

Use this folder only for the Wandering Sample under `components/wandering`.

## Workflow

Before editing, inspect the nearest launch files, README, and tests.
Propose a plan and intended diff before making any change.
Wait for explicit user approval before editing.

## Local Reference

The canonical prompt, ASCII pipeline diagram, and review-first workflow live in [skills.md](skills.md).

## Scope Rules

- Keep changes scoped to Wandering Sample code, docs, and tests unless the user asks otherwise.
- Prefer the Intel-aligned stack already used by the sample.
- Do not introduce non-Intel alternatives when an Intel path already exists.
- Explain tradeoffs clearly if a different path is proposed.

## Validation

After any approved change, run the narrowest validation that covers the touched behavior.
For simulation changes, verify the Gazebo tutorial path.
For supported robot changes, verify the documented real-robot tutorial path.
