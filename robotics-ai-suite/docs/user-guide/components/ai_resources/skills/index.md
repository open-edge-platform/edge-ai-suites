# Agentic Skills

Find the right skills to accelerate your development project, from proof-of-concept generators to interactive optimizers to find the right algorithm for your use case.

> **Note** These skills are used by AI agents. AI may produce undesired results. These are offered as learning and experimental tools only. Always verify your robotics solution follows acceptable guidance for safety and reliability.

## robotics-ai-suite focus

For the robotics-ai-suite repository, open the repository root in VS Code so the coding agent can discover the local skill definitions in `.github/skills/`.

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/robotics-ai-suite
code . # if using VS Code
```

This repo currently includes a Wandering-specific skill at `.github/skills/wandering-sample/SKILL.md`. The agent picks it up from the repository root and matches it by its `name` and `description`, which include Wandering launch files, Nav2 wiring, RTAB-Map, RealSense, and robot bring-up paths.

For direct invocation, use a prompt such as `@wandering-sample <describe your change>`. The agent may also auto-select the skill when your request matches the Wandering sample context.

These robotics-ai-suite skills are intended for the repository's robotics examples and tutorials, especially changes under `components/` and the related tutorial packages.

| Skill | Description | Usage | Link |
|-|-|-|-|
| `wandering` | Review-first workflow for changes in components/wandering and tutorial packages. Use when editing Wandering launch files, docs, tests, Nav2 wiring, RTAB-Map, RealSense, or robot bring-up paths. | Deployment | [link](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/components/wandering/README.md#agent-workflow) |