# Multi-Camera Scenescape Spatial Analysis Stack

Build an end-to-end stack in `./intersection-scene-stack/` for the smart-city /
ITS vertical. Object of interest: `vehicle`. Sources are three live RTSP camera
URLs covering the same intersection from different angles. Enable the **opt-in
Scenescape multi-camera spatial-analysis path** (`SCENESCAPE=yes`) to fuse the
three views into one scene named `intersection-1`, with camera IDs `cam-north`,
`cam-east`, and `cam-south` (one per input stream, same order). Keep the DLSPS
detection pipeline, but branch off the default recipe: delegate the multi-camera
scene fusion to the external `scenescape-setup` skill instead of hand-rolling it,
and load `references/SCENESCAPE.md` only on this branch. Follow the
Scenescape-branch completion criteria.
