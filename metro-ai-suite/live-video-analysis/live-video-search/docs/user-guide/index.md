# Live Video Search

<!--hide_directive
<div class="component_card_widget">
	<a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/live-video-analysis/live-video-search">
		 GitHub project
	</a>
	<a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/live-video-analysis/live-video-search/README.md">
		 Readme
	</a>
</div>
hide_directive-->

Live Video Search is a Metro AI Suite sample that adapts the VSS pipeline for semantic search on live Frigate streams. It ingests live camera streams, indexes video segments with embeddings and timestamped camera metadata, and lets users select cameras, time ranges, and free‑text queries to retrieve ranked, playable clips with confidence scores while surfacing live system metrics.

## Documentation

- **Get Started**
  - [Get Started](./get-started.md): Deploy the full stack locally.
  - [System Requirements](./system-requirements.md): Hardware and software prerequisites.

- **Overview**
  - [Overview](./overview-live-video-search.md): What Live Video Search is and when to use it.
  - [Architecture](./overview-architecture-live-video-search.md): End‑to‑end architecture and data flow.

- **Deployment**
  - [Build from Source](./how-to-build-from-source.md): Build the required images.

- **Usage & API**
  - [API Reference](./api-reference.md): Key endpoints and references.

- **Release & Support**
  - [Release Notes](./release-notes.md): Updates and fixes.

<!--hide_directive
:::{toctree}
:maxdepth: 2
:hidden:

get-started
system-requirements
overview-live-video-search
overview-architecture-live-video-search
how-to-build-from-source
deploy-with-helm
how-to-use-application
api-reference
release-notes
troubleshooting
:::
hide_directive-->
