# Build from Source

This guide provides step-by-step instructions for building Live Video Captioning Sample Application from source.

## Building the Images

To build the Docker image for `Live Video Captioning` application, follow these steps:

1. Ensure you are in the project directory:

      ```bash
      cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning
      ```

2. If you are running [`Live Video Captioning with RAG`](../how-to-guides/configure-embedding-creation-with-rag.md), export the following environment variable:

      ```bash
      export COMPOSE_PROFILES=EMBEDDING
      ```

   Skip this step if you are running only Live Video Captioning.

3. [Optional] To include third-party copyleft source packages in the built images, export the environment variable before building:

     ```bash
     export COPYLEFT_SOURCES=true
     ```

4. Run the following `docker compose` command:

      ```bash
      docker compose build
      ```
