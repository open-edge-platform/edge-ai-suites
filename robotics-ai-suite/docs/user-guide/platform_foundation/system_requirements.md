# System Requirements

The Robotics AI Suite supports the platform and middleware configurations below.
Each Blueprint defines the hardware, drivers, packages, and peripherals that
have been validated for its workflows.

## Supported Intel Processors

| Code Name | Intel Processor
| --- | --- |
| Panther Lake | Series 3 Intel® Core™ Ultra Processor |
| Wildcat Lake | Series 3 Intel® Core™ Processor |
| Arrow Lake | Series 2 Intel® Core™ Ultra Processor |

## Supported Operating Systems

| OS Distribution | OS Version | OS Variant |
| --- | --- | --- |
| Canonical Ubuntu | 24.04 LTS (Noble Numbat) | 64-bit Desktop |
| Canonical Ubuntu | 22.04 LTS (Jammy Jellyfish) | 64-bit Desktop |

## Supported Configurations

```{include} getting_started/fragment_configurations.md
```

Use the [Middleware](../components/middleware/index.md) guidance to configure
the ROS 2 distribution for the selected system profile. Before installing a
robot application, review its Blueprint for compatible hardware, sensor,
firmware, and package requirements.

## Additional Requirements

- Internet connectivity is required during initial installation.
- You should be familiar with executing Linux commands.
- A ROS 2 background is strongly recommended.

Individual Blueprints and how-to guides can require additional robot hardware,
sensors, software packages, or peripherals. Review their prerequisites before
starting a specific workflow.

## Next Steps

Learn more about the support development kits:

- **[Development Kits](development_kits/index.md)** — select a development kit to get started with.

Bring your own system and continue to the Getting Started guide:

- **[Getting Started](getting_started.md)** — setup your system for the Robotics AI Suite.


:::{toctree}
:hidden:

Development Kits <development_kits/index>
:::

