<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Advanced Image Customization (Using Image Composer Tool)

The [Image Composer Tool (ICT)](https://github.com/open-edge-platform/image-composer-tool/tree/2026.1-Release)
is a command-line tool for building custom Linux images from pre-built packages.
To get a bootable RAW or ISO image, you define the target OS, packages, kernel, and disk layout.
ICT supports multiple distributions including Ubuntu, Azure Linux, and Red Hat compatible
distros on x86_64.

> Note that this path is intended for advanced users who need fine-grained control over disk
> layout, installed packages, and package repositories. Most users can start with the simpler
> path, [using a Standard Ubuntu 24.04 image](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/get-started/build-from-source.html#option-1-build-from-a-standard-ubuntu-24-04-image).

This article will show you how to:

- [Build OS image using default template](#build-os-image-using-default-template)
- [Package the image into artifacts](#package-the-image-into-artifacts)
- [Package curation and template customization](#package-curation-and-template-customization)
- [Troubleshoot the process](#troubleshoot)

## Build OS image using default template

### Clone the repositories

```bash
# If edge-node-infrastructure-blueprint is not already cloned, uncomment the line below
# git clone https://github.com/open-edge-platform/edge-node-infrastructure-blueprint.git
git clone --branch 2026.1-Release https://github.com/open-edge-platform/image-composer-tool.git
```

Now, you should have the source code available in `edge-node-infrastructure-blueprint` and `image-composer-tool` directories in your workspace (for example, `/home/user`).

```bash
export ENIB_HOME=$(pwd)/edge-node-infrastructure-blueprint
export ICT_HOME=$(pwd)/image-composer-tool
```

### Build the tool

Produces `./image-composer-tool` in the repo root:

```bash
cd "$ICT_HOME"
go build -buildmode=pie -ldflags "-s -w" ./cmd/image-composer-tool
```

### Install image composition prerequisites

These packages are required before composing any image:

```bash
sudo apt install systemd-ukify mmdebstrap
```

Follow the instructions at [Image Composition Prerequisites](https://github.com/open-edge-platform/image-composer-tool/blob/2026.1-Release/docs/tutorial/installation.md#image-composition-prerequisites) if you face issues installing packages using apt.

> **Note:** `mmdebstrap` version 0.8.x (shipped with Ubuntu OS version 22.04) has known
> issues. Ensure you have version 1.4.3 or later. On Ubuntu OS version 23.04 or later, the
> repository version is sufficient.

### Configure the template

The default template location is `$ENIB_HOME/infrastructure/host-os/ict/generic-handheld-os-template.yml`.

```bash
export TEMPLATE="$ENIB_HOME/infrastructure/host-os/ict/generic-handheld-os-template.yml"
```

In `$TEMPLATE`, set the values for `users.name` and `users.password` as desired.
The password must contain a SHA-512 hash generated using one of the following tools:

```bash
# Using openssl (requires `openssl` to be installed)
openssl passwd -6 'your-password-here'

# Using mkpasswd (requires `whois` to be installed)
mkpasswd --method=sha-512 'your-password-here'
```

Adapt this template to suit your use case. The advanced customization options are discussed in the [Package curation and template customization](#package-curation-and-template-customization) section below.

### Validate the template

Check the template for syntax and schema errors before starting a full
build (fast, no root required):

```bash
./image-composer-tool validate "$TEMPLATE"
```
---
### Build the image

Run the build with elevated privileges so that the tool can manage loop devices
and chroot environments. Pass `-E` to preserve your proxy and environment variables:

```bash
sudo -E ./image-composer-tool build "$TEMPLATE"
```

### Build output

When the build completes, expect the following output on the console with build timings:

```bash
2026-04-09T15:10:22.705+0530    INFO    display/display.go:21   Checking for image artifacts in: /home/user/image-composer-tool/workspace/ubuntu-ubuntu24-x86_64/imagebuild/minimal
2026-04-09T15:10:22.705+0530    INFO    display/display.go:30   Found 2 total entries in directory
2026-04-09T15:10:22.705+0530    INFO    display/display.go:36   Checking file: minimal-desktop-ubuntu-24.04.raw.gz (isDir=false)
2026-04-09T15:10:22.705+0530    INFO    display/display.go:36   Checking file: spdx_manifest_deb_minimal-desktop-ubuntu_20260409_150520.json (isDir=false)
2026-04-09T15:10:22.706+0530    INFO    display/display.go:44   Found 2 artifacts after filtering
2026-04-09T15:10:22.706+0530    INFO    display/display.go:52
2026-04-09T15:10:22.706+0530    INFO    display/display.go:53   ╔════════════════════════════════════════════════════════════════════════════╗
2026-04-09T15:10:22.706+0530    INFO    display/display.go:54   ║                    ✓ IMAGE CREATED SUCCESSFULLY                            ║
2026-04-09T15:10:22.706+0530    INFO    display/display.go:55   ╚════════════════════════════════════════════════════════════════════════════╝
2026-04-09T15:10:22.706+0530    INFO    display/display.go:56
2026-04-09T15:10:22.706+0530    INFO    display/display.go:59     Image Type:   RAW
2026-04-09T15:10:22.706+0530    INFO    display/display.go:60
2026-04-09T15:10:22.706+0530    INFO    display/display.go:61     Generated Artifacts (including SBOM):
2026-04-09T15:10:22.706+0530    INFO    display/display.go:79       • minimal-desktop-ubuntu-24.04.raw.gz (2.62 GB)
2026-04-09T15:10:22.706+0530    INFO    display/display.go:80         /home/user/image-composer-tool/workspace/ubuntu-ubuntu24-x86_64/imagebuild/minimal/minimal-desktop-ubuntu-24.04.raw.gz
2026-04-09T15:10:22.706+0530    INFO    display/display.go:81
2026-04-09T15:10:22.706+0530    INFO    display/display.go:79       • spdx_manifest_deb_minimal-desktop-ubuntu_20260409_150520.json (1.37 MB)
2026-04-09T15:10:22.706+0530    INFO    display/display.go:80         /home/user/image-composer-tool/workspace/ubuntu-ubuntu24-x86_64/imagebuild/minimal/spdx_manifest_deb_minimal-desktop-ubuntu_20260409_150520.json
2026-04-09T15:10:22.706+0530    INFO    display/display.go:81
2026-04-09T15:10:22.706+0530    INFO    display/display.go:84   ════════════════════════════════════════════════════════════════════════════
2026-04-09T15:10:22.706+0530    INFO    display/display.go:85
2026-04-09T15:10:22.877+0530    INFO    image-composer-tool/build.go:137  image build completed successfully
2026-04-09T15:10:22.877+0530    INFO    display/display.go:154    Build Timings:
2026-04-09T15:10:22.877+0530    INFO    display/display.go:155    +----------------------------------+----------------+
2026-04-09T15:10:22.877+0530    INFO    display/display.go:156    | Stage                            | Duration       |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:157    +----------------------------------+----------------+
2026-04-09T15:10:22.877+0530    INFO    display/display.go:159    | Initialization and Configuration | 16.499s        |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:159    | Package Download                 | 3m20.339s      |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:159    | Chroot Env Initialization        | 52.647s        |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:159    | Image Build                      | 8m54.777s      |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:159    | Image Conversion                 | 4m58.711s      |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:159    | Finalization and Clean Up        | 1.264s         |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:161    +----------------------------------+----------------+
2026-04-09T15:10:22.877+0530    INFO    display/display.go:162    | Total Time                       | 18m24.237s     |
2026-04-09T15:10:22.877+0530    INFO    display/display.go:163    +----------------------------------+----------------+

```

The output artefacts are written to:

```text
./workspace/ubuntu-ubuntu24-x86_64/imagebuild/<config-name>/
```

Expected artifact:

| File                                  | Description                                |
| ------------------------------------- | ------------------------------------------ |
| `minimal-desktop-ubuntu-24.04.raw.gz` | Compressed raw disk image (ready to flash) |

## Package the image into artifacts

Use the `image-from-tool` mode with `make build` now to package the OS image into
the USB artifacts:

```bash
cd "$ENIB_HOME"
make build MODE=image-from-tool ICT_IMG=/absolute/path/to/image
```

`ICT_IMG` may be any readable file on the host — absolute path or path relative to
the repository root. `make` resolves the path and bind-mounts the containing
directory read-only into the build container, so the image does not need to live
inside the repository.

Example for handheld blueprint build:

```bash
cd "$ENIB_HOME"
make build MODE=image-from-tool ICT_IMG=/home/user/image-composer-tool/workspace/ubuntu-ubuntu24-x86_64/imagebuild/minimal/minimal-desktop-ubuntu-24.04.raw.gz
```

Build output:

- `usb-installation-files.tar.gz` in `infrastructure/build-artifacts/out`

Once `usb-installation-files.tar.gz` is ready, continue with
[Phase 2: Prepare Bootable USB](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/get-started/prepare-usb.html) in the global Get Started guide
for the remaining steps: configuring the USB device, writing the artifacts, and booting the target system.

## Package curation and template customization

This section explains how to curate package lists with the `update-install-packages` skill and produce a new Image Composer Tool (ICT) image variant on top of the default template.

Use this flow when you want to build a custom image flavor (for example, debug, media-heavy, or minimal runtime) without editing the baseline files manually each time.

### What you are modifying

The package curation flow can update one or both of the following files:

- The relevant curation script — consumed by the Docker-based standard image build:
  - `infrastructure/host-os/curate-host-packages.sh`
- The relevant ICT template — consumed by the ICT-based advanced image build:
  - `infrastructure/host-os/ict/generic-handheld-os-template.yml`

By default, if not explicitly specified, the skill updates package intent for both the Docker-based standard build and the ICT template.

### End-to-end flow

1. Start from the repository root and define your package delta (add or delete).
2. Run the `update-install-packages` skill to apply package curation safely.
3. Validate YAML and backups created by the skill.
4. Copy the default ICT template into a working template for your variant.
5. Validate and build the image using ICT.
6. Record artifact path and package delta for reproducibility.

### Run the skill

If you are using Copilot Chat in agent mode, invoke the skill with a natural language prompt describing your intent. For example:

```text
Add htop, jq, and iperf3 to the ict-template in /home/user/edge-node-infrastructure-blueprint
```

```text
Delete mosquitto and mosquitto-clients from both curate-host-packages and the ict-template.
```

```text
Add sysbench and stress-ng to curate-host-packages only for a debug image variant.
```

The skill is expected to:

- validate package name format
- verify package availability in Ubuntu 24.04 repositories
- optionally search repositories for packages matching hardware details (device name, model, or vendor) and confirm matches before adding
- create backups before file changes
- return per-file package change results (`added`, `deleted`, `already-present`, `not-found`)
- validate shell and YAML syntax after updates

### Build an ICT variant from the curated baseline

After package curation succeeds, create a variant template from the default template:

```bash
cp "$TEMPLATE" \
   "$(dirname "$TEMPLATE")/my-template.yml"
```

For detailed validation and build instructions, refer to [Building an Ubuntu OS Version 24.04 Image with Image Composer Tool](https://github.com/open-edge-platform/edge-node-infrastructure-blueprint/blob/main/infrastructure/host-os/ict/README.md). That guide covers:

- template validation
- image build process
- troubleshooting and build output artifacts

Expected output artifact type:

- compressed raw image (`.raw.gz`)

### Safety and rollback

Follow these rules for reliable curation:

- do not edit the only source copy without backup
- stop on any precondition or YAML validation failure
- restore from backup if update or validation fails
- do not request or store secrets in prompts or scripts

If rollback is needed, restore backup files produced by the skill for each modified target file and re-run validation.

## Troubleshoot

### Package not found or conflicting versions

If the build fails with errors like `failed: bad status: 404 Not Found` or conflicting versions, the package may not exist in the configured repositories or may have been renamed in Ubuntu 24.04.

1. Confirm the package name is correct:

   ```bash
   apt-cache search <name>
   apt-cache show <name>
   ```

2. Clean the ICT cache and temporary files, then rebuild:

   ```bash
   sudo ./image-composer-tool cache clean
   sudo rm -rf tmp/
   ```

### Mirror issues

Standard Ubuntu mirrors may occasionally be unreliable or return stale metadata. If you encounter intermittent download failures or hash-sum mismatches during the build, update the `packageRepositories` section in your template to use other open-source mirrors. For example, using the Kernel.org mirror:

```yaml
packageRepositories:
  - codename: "noble"
    url: "http://mirrors.edge.kernel.org/ubuntu/"
    component: "main restricted universe multiverse"
    priority: 500
```

To find the fastest mirror for your region, you can optionally use `mirrorselect`:

```bash
sudo snap install mirrorselect
mirrorselect --country us
```

Replace `us` with your country code (for example, `de`, `in`, `sg`) and use the returned URL in `packageRepositories`.

After updating the mirror, clean and rebuild:

```bash
sudo ./image-composer-tool cache clean
sudo rm -rf tmp/
```
