# Get Started

The Live Video Captioning RAG sample application is a Retrieval-Augmented Generation workflow that creates caption-text embeddings and stores them in a vector database together with the corresponding video frames and metadata, using an OpenVINO™ LLM for response generation. The application is designed to work alongside the [Live Video Captioning](../../live-video-captioning/) sample, which processes an RTSP video stream, runs video analytics pipelines, and uses a Vision-Language Model (VLM) to generate live captions for video frames. It then sends the frame data, caption text, and associated metadata to the Live Video Captioning RAG sample application so it can build embedding context and store it in the vector database. The Live Video Captioning RAG sample application then provides chatbots that answer questions based on the caption text generated from the video frames.

By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to deploy the application in your system environment.
- **Run the sample application**: Launch the application and use the chatbots to answer questions.
- **Customize application parameters**: Customize settings like LLM models and deployment configurations to adapt the application to your specific requirements and environment.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose: [Installation Guide](https://docs.docker.com/compose/install/).
- OpenVINO-compatible LLM in `llm_models/`. User may refer to the [model preparation steps](../../../live-video-captioning/docs/user-guide/model-preparation.md) provided to prepare the model.

## Run the application

1. **Clone the repository**:
     ```bash
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
     # Alternatively, clone a specific release branch
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edges-ai-suites -b <release-tag>
     ```

> **Note:** Adjust the repo link appropriately in case of forked repo.

2. **Navigate to the Directory**
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag
     ```

3. **Configure Image Registry and Tag**:

     If you prefer to use prebuilt images from Docker Hub, export the variables below.

     ```bash
     export REGISTRY="intel/"
     export TAG="latest"
     ```

     If you prefer to build the sample application from source code instead, skip this step and follow the [Build from Source](./get-started/build-from-source.md) guide.

4. **Configure and export the environment**:
     ```bash
     # Configure environment variables. By default, the application uses the CPU device for  embedding and LLM.
     # To use GPU, edit `setup_env.sh` and set: DEVICE="GPU"
     # Set LLM_MODEL_ID to your prepared LLM model.
     # Set EMBEDDING_MODEL_NAME to your desired embedding model.

     # Source the script to apply the environment.
     source scripts/setup_env.sh
     ```

5. **Download/Export Models**:

     Follow the model preparation steps outlined in [Prerequisites](#prerequisites).

6. **Start the Application**:

     Start the application using Docker Compose tool:
     ```bash
     docker compose up -d
     ```

     Notes:
     - It will take sometimes for the application to get started. Check the container status and make sure they are in `"healthy/running"` state using `docker ps` command before accessing the application.

7. **Access the application**:

     To start the application:

     1. Open the web browser and navigate to the `Live Video Captioning RAG` dashboard at `http://<HOST_IP>:4172
     2. Enter any query in the chatbot.<br>
        Note: You should expect a "generic" response at this point since no context has been created in the vector store yet.
     3. To demonstrate the full functionality, run the following commands to create context using a sample image and caption:
         ```bash
         # Navigate to the directory
         cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag

         # Run the python script
         python3 sample/demo_call_embedding.py
         ```

         Notes: This script is provided for demonstration purposes only. It will:
         - Download a sample image
         - Call the `embeddings/` endpoint to generate embeddings
         - Create context and store in the vector store
     4. Once the script has completed execution, return to the dashboard in your browser and test the chatbot with contextual queries.<br>
        `Example query: "How many students in the classroom?"`<br>
        You should now receive contextual responses from the RAG Chatbot.

8. **Stop the Services**:

     Stop the sample application services using below:
     ```bash
     docker compose down
     ```

## Integration with Live Video Captioning

This sample application can run together with Live Video Captioning to enable embedding creation and RAG-based contextual chat.
For setup instructions, refer to:

- [Setup Live Video Captioning RAG along with Live Video Captioning](../../../live-video-captioning/docs/user-guide/embedding-creation-with-rag.md)

## Supporting Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [API Reference](./api-reference.md)
- [Build from Source](./get-started/build-from-source.md)
- [Known Issues](./known-issues.md)
