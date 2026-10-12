# Build from Source

This guide provides step-by-step instructions for building Real Time Scene Understanding Sample Application from source.

## Building the Images

To build the Docker images for `Real Time Scene Understanding` application, follow these steps:

1. Ensure you are in the project directory:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/real-time-scene-understanding/
     ```

2. [Optional] To include third-party copyleft source packages in the built images, export the environment variable before building:

     ```bash
     export COPYLEFT_SOURCES=true
     ```

3. Run the following `docker compose` command:

     ```bash
     docker compose build
     ```