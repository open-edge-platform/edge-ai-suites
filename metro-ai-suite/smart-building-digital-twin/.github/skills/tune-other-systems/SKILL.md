---
name: tune-other-systems
description: 'Tune or debug this Smart Building Digital Twin application on another machine. Use when results differ across systems, when setup works locally but not on a target host, or when analytics behavior changes due to GPU/CPU mode, CPU or platform performance differences, scene UUIDs, exported configuration, hostnames, proxies, or service health.'
argument-hint: 'Describe the target system difference or tuning goal'
---

# Tune Other Systems

Use this skill when the Smart Building Digital Twin application behaves differently on another workstation, NUC, or lab system.

## Focus Areas
- Deployment differences: GPU present vs absent, container health, proxy environment, hostname resolution
- Platform-performance differences: Arrow Lake vs Panther Lake class changes, faster or slower inference cadence, altered replay alignment, and timing-sensitive analytics outcomes
- Setup differences: local API access, auth readiness, scene import, asset restore, UUID resolution
- Analytics differences: different region hits, tripwire behavior, luggage ownership, door baselines, badge warnings, snapshot cadence
- Configuration drift: object classes, scene geometry, camera transforms, missing exported config, stale `.env`

## Procedure
1. Capture the machine delta first.
   - Record CPU/platform generation, GPU availability, OS version, hostname, proxy-related environment variables, and whether `.env` was reused from another host.
   - Compare `DETECTION_DEVICE`, `INFERENCE_DEVICE`, `PUBLIC_HOSTNAME`, `API_BASE_URL`, `SCENE_ID`, and `DASHBOARD_URL`.
   - Use the checklist in [system-delta-template.md](./assets/system-delta-template.md).

2. Treat performance-sensitive behavior as a likely cause when hardware differs.
   - Do not assume identical analytics output across platforms with different throughput.
   - A faster system can change frame timing, object association windows, replay ordering, and whether a transient condition lasts long enough to trigger an alert.
   - Compare timing-sensitive symptoms against regulated scene data and service throughput before retuning heuristics.

3. Verify setup-path invariants before tuning analytics.
   - Host-side helper scripts should use `https://localhost/api/v1` unless they are intentionally run from another machine.
   - Loopback API calls should bypass proxies.
   - Internal container networking should continue using the fixed Scenescape FQDN aliases.
   - Confirm `web`, `scene`, `broker`, `autocalibration`, and `analytics` are running before assuming an analytics regression.
   - If the browser can't reach `PUBLIC_HOSTNAME` even though `docker compose ps` and a `localhost` curl are healthy, suspect host DNS/proxy drift rather than the stack: compare `getent hosts $PUBLIC_HOSTNAME` against `hostname -I`, and check that `no_proxy`/`NO_PROXY` includes the internal domain (a later block in shell startup files can silently overwrite an inherited proxy exception list).

4. Confirm the deployment-specific scene wiring.
   - Check whether `setup.sh` resolved the live scene UUID and wrote `config/resolved-uuids.json`.
   - Verify the analytics container is subscribed to the correct regulated topic for the deployed scene UUID.
   - If the scene was edited in the UI on the target machine, export the current configuration before making code changes.

5. Separate scene/config drift from code drift.
   - If regions, tripwires, object classes, or transforms differ, prefer exporting and committing config changes instead of patching analytics heuristics.
   - If only one target system differs, inspect environment, hardware, service health, and replay timing before editing code.
   - Preserve upstream-compatible internal hostnames and localhost API usage unless the target architecture truly differs.

6. Gather the right evidence for tuning.
   - Review `docker compose ps` and targeted service logs.
   - Inspect `.env`, `config/resolved-uuids.json`, and the latest exported scene JSON.
   - Compare analytics output against the regulated scene feed rather than only the dashboard symptoms.
   - Note whether the faster or slower platform changes event timing, not just whether the final label differs.

7. Make durable changes.
   - Use exported config for scene/object-class tuning.
   - Use `setup.sh`, `cleanup.sh`, and helper scripts for deployment fixes that must work on fresh systems.
   - Prefer making timing assumptions explicit in docs or configuration when hardware-performance differences are known to matter.
   - Update docs or instructions when a new cross-system invariant is verified.

## Expected Outputs
- A short explanation of whether the issue is environment, setup, scene configuration, or analytics logic
- The smallest durable fix for the repo
- Exported configuration updates when tuning was done in the UI
- Any new cross-system invariant that should be added to workspace instructions or repo memory

## Useful Files
- `setup.sh`
- `docker-compose.yml`
- `cleanup.sh`
- `config/object-classes.json`
- `config/scenes/*.json`
- `config/resolved-uuids.json`
- `scripts/export-config.sh`
- `scripts/restore-assets.sh`
- `scripts/import-scenes.sh`
- `scripts/scene_config.py`
- `scripts/narrator.py`
