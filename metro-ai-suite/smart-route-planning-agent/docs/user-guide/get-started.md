# Get Started

| **STATUS** |  Work in Progress |
|------------| ------------------|

This application uses AI Agent to analyze a route between given source and destination. It communicates with other agents to fetch live analysis reports for traffic intersections found along all feasible routes between the source and destination. Subsequently, the agent finds an optimum route in real-time which is likely to be free from any possible incidents (like congestion, weather, roadblocks, accidents etc.).

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

## Quick Start with Setup Script

| **STATUS** |  Work in Progress |
|------------| ------------------|


The Smart Route Planning Agent includes a unified setup script (`setup.sh`) that combines both setup and orchestration functionality. It handles environment configuration, building, deployment, and ongoing service management. This is the **recommended approach** for getting started and managing the services.

### 1. Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/smart-route-planning-agent
```

### 2. Run the Complete Setup

The setup script provides several options. For a complete setup (recommended for first-time users):

```bash
source setup.sh setup
```

### 3. Alternative Setup Options

For more granular control, the setup script provides individual commands:

```bash
# Set environment variables only
source setup.sh setenv

# Start services only (after setup)
source setup.sh up

# Stop services
source setup.sh down

# Restart services
source setup.sh restart

# Check service status
source setup.sh status

```

### 4. Verify

Check Smart Route Planning Agent health:

```bash
curl -s -X GET http://localhost:8082/health
```

## Manual Setup (Advanced Users)

For advanced users who need more control over the configuration, you can manually set up the stack using Docker Compose.

### Manual Environment Configuration

If you prefer to manually configure environment variables instead of using the setup script, see the [Environment Variables Guide](./environment-variables.md) for complete details. 

### Manual Docker Compose Deployment

| **STATUS** |  Work in Progress |
|------------| ------------------|


## Configuration Files

The Smart Route Planning Agent stack uses several configuration files located in the `config/` directory:

### Smart Route Planning Agent Configuration

| **STATUS** |  Work in Progress |
|------------| ------------------|