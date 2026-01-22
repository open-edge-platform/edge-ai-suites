# Smart Route Planning Agent

| **STATUS** |  Work in Progress |
|------------| ------------------|

This application uses AI Agent to analyze a route between given source and destination. It communicates with other agents to fetch live analysis reports for traffic intersections found along all feasible routes between the source and destination. Subsequently, the agent finds an optimum route in real-time which is likely to be free from any possible incidents (like congestion, weather, roadblocks, accidents etc.).

## Documentation

- **Overview**
  - [Overview](docs/user-guide/Overview.md): A high-level introduction to the microservice and its features.

- **Getting Started**
  - [Get Started](docs/user-guide/get-started.md): Step-by-step guide to getting started with the microservice.
  - [System Requirements](docs/user-guide/system-requirements.md): Hardware and software requirements for running the microservice.

- **Configuration**
  - [Environment Variables](docs/user-guide/environment-variables.md): Complete guide to configuring the microservice through environment variables.
  - [Traffic Data Analysis Workflow](docs/user-guide/traffic-data-analysis-workflow.md): Comprehensive guide to traffic analysis, VLM integration, trigger conditions, windowed analysis, and configuration parameters.

- **Deployment**
  - [How to Build from Source](docs/user-guide/how-to-build-from-source.md): Instructions for building the microservice from source code.

- **Release Notes**
  - [Release Notes](docs/user-guide/release-notes.md): Information on the latest updates, improvements, and bug fixes.
