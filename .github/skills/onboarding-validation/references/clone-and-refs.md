<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Clone and Ref Handling

This file is part of the `onboarding-validation` skill instructions.

## Branch/Tag checkout details

- Verify the docs instruct cloning/checking-out that exact ref.
- After clone, run `git log -1 --format='%H'` and record the full commit SHA. This value MUST appear in the report Summary table.
- **If the docs reference a different ref than the one under test, the agent still clones the prompt's `<ref>` and reports the mismatch — never Critical.** Because the agent *consciously* reproduces the correct version (from the prompt link) instead of blindly following the docs onto the wrong/undetermined commit, the run is never blocked, so this is **never Critical**. Two sub-cases:
  - **Moving ref** in the docs (`main`, a release **branch** like `--branch release-2026.1`, `latest`, or any non-pinned target): the documented path is non-deterministic — a user who copies it later gets a different, moving commit — so report a reproducibility FAIL (**rule 10.2**) at **Major** severity (also fail **rule 1.3** if no exact tag/commit is named at all). It is **Major**, not a cosmetic Minor (a real defect a real user hits), and **never Critical** (the agent reproduced the pinned ref).
  - **Different but fixed ref** — typically the docs already name the **final release tag/branch** while the prompt pins an **RC** (e.g. validating `…-rc2` against docs that point to the GA tag). The documented clone is itself deterministic (an exact tag), so the clone rules (1.3/10.2) may still PASS; this is an **expected, conscious** release-process discrepancy. The agent MUST clone the prompt's `<ref>` (the RC) and **note the mismatch in Execution Notes** for transparency. This is **not Critical** and is **not a reproducibility FAIL by itself**.
- **Submodule apps.** If the app folder is a git submodule of the base repo (it appears in the base repo's `.gitmodules`), the version under test is the commit the base ref pins for that submodule — its **gitlink SHA** — which is the ground truth **regardless of what the submodule's own documentation says to clone**. The agent MUST:
  - Resolve the pinned commit and reproduce exactly it (do NOT clone the submodule's own repository directly — that bypasses the suite pin):
    ```bash
    git clone --filter=blob:none --sparse --branch <ref> <base-repo> <base>
    cd <base>
    git ls-tree HEAD <submodule-path>                 # -> 160000 commit <PINNED_SHA> <path>
    git sparse-checkout set <submodule-path>
    git submodule update --init --recursive -- <submodule-path>
    git -C <submodule-path> rev-parse HEAD            # MUST equal <PINNED_SHA>
    ```
  - Record BOTH SHAs in the Summary: base `Commit` and `Commit (submodule)` = `<PINNED_SHA>`.
  - Evaluate the clone rules (1.x) against the **app's** documented get-started, which lives inside the submodule at `<PINNED_SHA>`.
  - If that documentation tells the user to clone the submodule repo at a moving ref (e.g., `main`) or at a commit other than `<PINNED_SHA>`, the documented path does NOT reproduce the released version — report it as a reproducibility FAIL (rule 10.2), exactly like the `main`-vs-tag discrepancy above.
