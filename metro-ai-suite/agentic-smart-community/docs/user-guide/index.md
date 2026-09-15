# Agentic Smart Community

<!--hide_directive
::::{container} component_header_row
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/agentic-smart-community">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/README.md">
     Readme
  </a>
</div>
hide_directive-->

> Note:
> This is a sample application **intended for evaluation and development purposes only**.
  For more information, refer to
  [Intended Use](https://docs.openedgeplatform.intel.com/dev/OEP-articles/notes-on-usage.html#intended-use)

<!--hide_directive :::: hide_directive-->

An AI-agent-native video analysis platform built on the **MCP (Model Context Protocol)**.
It hands AI agents a universal, framework-agnostic toolkit for video surveillance and analysis,
so they can autonomously create, manage, and respond to custom use cases — with no changes to
core components.

For example, an agent can remind you when the fridge is running low on groceries, alert a
parent when a child climbs onto a window sill, or flag when an elderly family member has
not got up on time — and you can add a brand-new use case just by describing it in a chat.

> **New here?** Bring the stack up in a few commands with the **[Get Started Guide](./get-started.md)**.


## Example Use Cases

These demos are validated end-to-end. They are only a starting point — describe a new scenario in chat and trigger a new use case monitoring by following [Register a New Use Case](./how-to-guides/register-new-use-case.md).

| Use Case | Description | Proactive Alerts |
| -------- | ----------- | ---------------- |
| Fridge Monitor | Refrigerator monitoring — regular reports (food shortage alerts, diet adjustment suggestions, lifestyle/fitness recommendations) + interactive chat with agents for personalized Q&A | No |
| Child Safety | Child danger alert notification — real-time detection of risky behaviors (jumping from heights, playing with knives/fire, etc.), immediate alerts to parents, daily summaries, and follow-up conversations | Yes |
| Elder Wakeup | Elder care (wake-up tracking) — monitor daily wake-up times, alert caregivers on significant deviations, weekly summary reports, and follow-up reminders | Yes |

## Supporting Resources

- [Get Started Guide](./get-started.md) — Step-by-step instructions to set up the MCP server and run the bundled use cases.
  - [Ready-to-Run Demo](./get-started/ready-to-run-demo.md) — Optional reference demo using user-provided video inputs.
- [System Requirements](./get-started/system-requirements.md) — Hardware and software requirements for running the sample application.
- [How It Works](./how-it-works.md) — Overview of the platform architecture, data flow, and the role of AI agents in orchestrating video analysis pipelines.
- [API Reference](./api-reference.md) — Comprehensive reference for the available API endpoints.
- [Release Notes](./release-notes.md) — Information on the latest release, improvements, and bug fixes.

## License

See [LICENSE](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/LICENSE).

<!--hide_directive
:::{toctree}
:hidden:

Get Started <./get-started.md>
How It Works <./how-it-works.md>
How-To Guides <./how-to-guides.md>
API Reference <./api-reference.md>
Release Notes <./release-notes.md>

:::
hide_directive-->
