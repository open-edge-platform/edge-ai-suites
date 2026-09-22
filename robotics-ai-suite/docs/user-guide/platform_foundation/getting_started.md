# Getting Started

This guide will setup and install the Robotics AI Suite, providing a common base
for running the included ingredients and reference applications, and for developing
your own applications.

## Requirements
This guide expects you to be familiar with common Linux terminal commands. An understanding
of ROS is also highly recommended.

- Review the [System Requirements](system_requirements.md) before installation.

## Select a Configuration

```{include} getting_started/fragment_configurations.md
```

## Setup

Follow one of the setup guides below:

| Setup type | Description | Recommendation |
| --- | --- | --- |
| **[Express Setup](getting_started/express.md)** | Use an installation tool to automatically configure and install the necessary content on an existing Ubuntu system. | Recommended if you are new to Robotics AI Suite. |
| **[Image Composer Tool Setup](getting_started/image_composer_tool.md)** | Build a pre-configured, bootable OS image (ISO or raw disk) with ROS 2 and the Robotics AI Suite repositories for deployment to multiple systems or fresh installations. | Recommended if you want to scale the deployment to many systems. |
| **[Step by Step](getting_started/step_by_step.md)** | Go through configuring and installing the necessary content on your system manually, one step at a time. | Recommended if you want to understand the individual setup steps. Not recommended for most deployments. |



:::{toctree}
:hidden:

Express Setup <getting_started/express>
Image Composer Tool Setup <getting_started/image_composer_tool>
Step by Step Setup <getting_started/step_by_step>
Conditional Setup <getting_started/conditional>
:::

