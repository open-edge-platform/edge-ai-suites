# Release Notes: Smart NVR

- [Version 2026.1.0](#version-202610)
- [Version 1.2.4](#version-124)

## Current Release

<!--### Version 2026.2.0-->

<!--date TBD-->

### Version 2026.1.0

**June 17, 2026**

**Improved**

- Documentation updates to improve clarity and accuracy.

**Fixed**

- Fixed Dependabot security vulnerabilities in dependencies.
- Minor bug fixes.

**Known Issues**

- Scenescape integration is currently not supported when deploying with Helm charts.
- Smart NVR will not work on either Standalone or Developer Node versions of
  Edge Microvisor Toolkit due to its incompatibility with Frigate.
- The AI-Powered Event Viewer feature relies on Frigate GenAI features, which may exhibit
  instability or bugs, impacting event data processing reliability.

## Previous Releases

### Version 1.2.4

**Release Date**: 17 Feb 2026

**New Features**:

- Dependabot fixes for security vulnerabilities in dependencies.
- Documentation updates for clarity and accuracy.
- Minor bug fixes.

<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025.md>

:::
hide_directive-->

