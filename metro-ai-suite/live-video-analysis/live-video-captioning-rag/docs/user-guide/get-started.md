# Get Started

The Live Video Captioning RAG sample application is a retrieval-augmented generation workflow that creates caption-text embeddings and stores them in a vector database together with the corresponding video frames and metadata, using an LLM that is optimized and deployed using OpenVINO™ toolkit, for response generation. The application works with the [Live Video Captioning](../../live-video-captioning/) sample application that processes a Real-Time Streaming Protocol (RTSP) video stream, runs video analytics pipelines, and uses a Vision-Language Model (VLM) to generate live captions for video frames. The Live Video Captioning sample application then sends the frame data, caption text, and associated metadata to the Live Video Captioning RAG sample application so the latter can build an embedding context and store it in the vector database. The Live Video Captioning RAG sample application then provides chatbots that answer questions based on the caption text generated from the video frames.

By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose tool to deploy the application in your system environment.
- **Run the sample application**: Launch the application and use the chatbots to answer questions.
- **Customize application parameters**: Customize settings, for example, the LLM models and deployment configurations, to adapt the application to your specific requirements and environment.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- OpenVINO toolkit-compatible LLM in `llm_models/`. See the [model preparation steps](../../../live-video-captioning/docs/user-guide/get-started.md#model-preparation) to prepare the model.

## Run the Application

1. Clone the repository:

     ```bash
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
     # Alternatively, clone a specific release branch
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edges-ai-suites -b <release-tag>
     ```

    > **Note**: If the repository is forked, edit the link.

2. Navigate to the directory:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag
     ```

3. Configure the image registry and tag:

     ```bash
     export REGISTRY="intel/"
     export TAG="latest"
     ```
    Skip this step if you prefer to build the sample application from the source. See [Build from Source](./get-started/build-from-source.md) for details.

4. Configure and export the environment:

     ```bash
     # Configure environment variables. By default, the application uses the CPU device for  embedding and LLM.
     # To use GPU, edit `setup_env.sh` and set: DEVICE="GPU"
     # Set LLM_MODEL_ID to your prepared LLM model.
     # Set EMBEDDING_MODEL_NAME to your desired embedding model.

     # Source the script to apply the environment.
     source scripts/setup_env.sh
     ```

5. Download or export models by following the model preparation steps in [Prerequisites](#prerequisites).

6. Start the application:

     Start the application using the Docker Compose tool:
     ```bash
     docker compose up -d
     ```

     > **Note**: The application will take some time to start. Check the container status and ensure that they are in  the `"healthy/running"` state using the `docker ps` command before accessing the application.

7. Access the application:

     To start the application:

     a. From the web browser, navigate to the `Live Video Captioning RAG` dashboard at `http://<HOST_IP>:4172`.
     b. Enter any query in the chatbot.<br>
        > **Note**: You will get a generic response at this point because no context has been created in the vector store yet.
     c. To demonstrate the full functionality, run the following commands to create the context using a sample image and caption:
	 
         ```bash
         # Navigate to the directory
         cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag

         # Run the Python script
         python3 sample/demo_call_embedding.py
         ```

         > **Notes**: Intel provides this script for demonstration purposes only. The script will:
         - Download a sample image.
         - Call the `embeddings/` endpoint to generate embeddings.
         - Create the context and store it in the vector store.
     d. Once the script completes its execution, return to the dashboard in your browser and test the chatbot with contextual queries.<br>
        `Example query: "How many students are there in the classroom?"`<br>
        You will now receive contextual responses from the RAG chatbot.

8. Stop the services:

     Stop the sample application services:
     ```bash
     docker compose down
     ```

## Build from Source

If you want to build the application from the source, see [Build from Source](./get-started/build-from-source.md).

## Integrate with Live Video Captioning

This sample application can run together with Live Video Captioning to enable embedding creation and RAG-based contextual chat. For setup instructions, see [Setup Live Video Captioning RAG along with Live Video Captioning](../../../live-video-captioning/docs/user-guide/embedding-creation-with-rag.md).

## Learn More

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)
