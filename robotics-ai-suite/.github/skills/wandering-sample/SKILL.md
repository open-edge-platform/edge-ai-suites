---
name: wandering-sample
description: "Review-first workflow for changes in components/wandering and tutorial packages. Use when editing Wandering launch files, docs, tests, Nav2 wiring, RTAB-Map, RealSense, or robot bring-up paths."
license: Apache-2.0
---

# Wandering Sample Agent Skill

This skill defines the review-first workflow for the Wandering Sample.

## When to Use

Use this skill only for the Wandering Sample under `components/wandering` and its tutorial packages:

- `wandering`
- `wandering_gazebo_tutorial`
- `wandering_aaeon_tutorial`
- `wandering_irobot_tutorial`
- `wandering_jackal_tutorial`
- `wandering_tutorials`
- `wandering_agentic_tutorial`

## Required Behavior

Any coding companion using this skill must:

1. Review the repository before editing.
2. Propose a plan and show the intended diff before making changes.
3. Wait for explicit user approval before applying edits.
4. Keep changes scoped to the Wandering Sample unless the user asks otherwise.
5. Prefer Intel-packaged and Intel-aligned paths already used by the sample.
6. Explain tradeoffs if a non-Intel path is suggested, and do not switch to it when an Intel path already exists.
7. Produce a clear ASCII pipeline diagram when asked to explain the app.

## What The Sample Uses

The Wandering Sample is not an OpenVINO inference demo. Its Intel-specific runtime path is the sensor and robotics stack already present in the repo:

- Intel RealSense camera support via `realsense2_camera` and `realsense2_description`
- RTAB-Map SLAM via `rtabmap_ros`
- Nav2 navigation via the tutorial packages and Nav2 plugins already wired in the sample
- `depthimage_to_laserscan` and `imu_filter_madgwick` in the Jackal integration path
- `tf2_ros` for the camera and robot frame wiring

Use those names when explaining the pipeline. Do not claim OpenVINO acceleration unless the user explicitly asks for a different sample.

## Canonical Review-First Workflow

When a user asks for a change, the assistant should do the following:

1. Read the nearest launch file, README, package metadata, and the tests that cover the touched behavior.
2. State a falsifiable local hypothesis about how the Wandering Sample currently works or why it fails.
3. State one cheap check that could disconfirm that hypothesis.
4. Propose a minimal edit plan and show the expected diff summary.
5. Wait for review approval before editing.
6. After approval, apply the change, run the narrowest relevant validation, and fix only what the validation disconfirms.

## Canonical Example Prompt

Paste this prompt into your coding assistant after opening the Wandering Sample folder in VS Code:

```text
You are working only in the Wandering Sample under components/wandering.

First, inspect the nearest launch files, README, and tests. Do not edit anything yet.
Then respond with:
1) a short plan,
2) the exact files you expect to change,
3) a brief diff summary,
4) one ASCII pipeline diagram of the current app,
5) a plain-English explanation of which Intel-aligned libraries or packages the sample uses and what each part of the pipeline does.

Do not make edits until I approve the plan and diff.

If I approve, make the smallest safe change needed for the requested feature.
Keep the change scoped to Wandering Sample code, docs, or tests.
Do not introduce non-Intel alternatives when an Intel-aligned path already exists.

When you are ready to propose the change, include both simulation and real-robot considerations:
- simulation mode with the Gazebo tutorial,
- real-robot mode with the AAEON, Jackal, or iRobot tutorial when supported.

If you propose a modification, also provide the exact validation command or commands I should run after the change.
```

## Recommended Assistant Instructions

Use the following steps in your coding companion UI:

1. Enable Chat or Plan mode in your coding assistant window.
2. Paste the canonical prompt from this file.
3. Review the assistant's plan, ASCII diagram, and proposed diff before allowing edits.
4. Once reviewed, enable Agent mode and let the assistant apply the change.
5. Verify the result in simulation first, then in real-robot mode if the feature supports it.

Supported examples include Copilot, Continue, and Gemini Assist.

## Current Pipeline Diagram

```text
Simulation path:

  [Gazebo / simulated robot]
             |
             v
  [Nav2 + wandering_app]
             |
             v
  [robot motion / map updates]

Real-robot path:

  [Intel RealSense camera] -----> [realsense2_camera]
             |                           |
             |                           v
             |                    [rtabmap_ros]
             |                           |
  [IMU / base_link / tf2_ros] --> [Nav2 + wandering_app]
                                         |
                                         v
                                [depthimage_to_laserscan]
                                         |
                                         v
                                [robot cmd_vel / navigation]
```

## Validation Expectations

When the assistant makes changes, it should validate with the narrowest command that covers the touched behavior. Typical checks include:

- `make test`
- `make lint`
- the tutorial launch command for the selected platform
- the real-robot launch script when the change touches hardware bring-up

If the change affects simulation, it must be runnable in the Gazebo tutorial before it is considered complete.
If the change affects a supported robot, it must also work with the documented real-robot workflow.

## Troubleshooting

- If the assistant starts editing before showing a plan and diff, stop it and rerun the prompt.
- If the assistant suggests a non-Intel camera or SLAM path, keep the Intel-aligned stack already used by the sample unless you explicitly want a redesign.
- If the build fails, check that the correct ROS distro has been sourced and that the tutorial package is built before launch.
- If the real-robot workflow fails, verify the robot namespace, camera topic names, and calibration assumptions in the tutorial script.
- If the assistant output does not include an ASCII diagram, ask it again before approving edits.