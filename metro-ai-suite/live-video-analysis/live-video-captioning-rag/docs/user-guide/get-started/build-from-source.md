# Build from Source

This guide shows how to build the Live Video Captioning RAG sample application from the source.

## Build the Image

1. Ensure you are in the project directory:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag
     ```

2. (Optional) To include third-party copyleft source packages in the built images, export the environment variable before building:

     ```bash
     export COPYLEFT_SOURCES=true
     ```

3. Export the environment:

     ```bash
     # Configure environment variables. By default, the application uses the CPU device for embedding and LLM.
     # To use GPU, edit `setup_env.sh` and set: DEVICE="GPU"
     # Set LLM_MODEL_ID to your prepared LLM model.
     # Set EMBEDDING_MODEL_NAME to your desired embedding model.

     # Source the script to apply the environment.
     source scripts/setup_env.sh
     ```

4. Build the Docker image:

     ```bash
     docker compose build
     ```
