# Get Started

The Live Video Captioning RAG sample application is a retrieval-augmented generation workflow that creates caption-text embeddings and stores them in a vector database together with the corresponding video frames and metadata, using an LLM that is optimized and deployed using OpenVINO™ toolkit, for response generation. The application works with the [Live Video Captioning](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning/index.html) sample application that processes a Real-Time Streaming Protocol (RTSP) video stream, runs video analytics pipelines, and uses a Vision-Language Model (VLM) to generate live captions for video frames. The Live Video Captioning sample application then sends the frame data, caption text, and associated metadata to the Live Video Captioning RAG sample application so the latter can build an embedding context and store it in the vector database. The Live Video Captioning RAG sample application then provides chatbots that answer questions based on the caption text generated from the video frames.

By following this guide, you will learn how to:

- **Set up the sample application**: Use Docker Compose tool to deploy the application in your system environment.
- **Run the sample application**: Launch the application and use the chatbots to answer questions.
- **Customize application parameters**: Customize settings, for example, the LLM models and deployment configurations, to adapt the application to your specific requirements and environment.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- OpenVINO toolkit-compatible LLM in `llm_models/`. User may refer to the [model preparation steps](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning/get-started/model-preparation.html) provided to prepare the model.

## Run the Application

1. Clone the suite:

   Go to the target directory of your choice and clone the suite.
   If you want to clone a specific release branch, replace `main` with the desired tag.
   To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

   ```bash
   git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/live-video-analysis/live-video-captioning-rag
   ```

2. Configure Image Registry and Tag:

     If you prefer to use prebuilt images from Docker Hub, export the following variables:

     ```bash
     export REGISTRY="intel/"
     export TAG="latest"
     ```

     If you prefer to build the sample application from source code instead, skip this step and follow the [Build from Source](./get-started/build-from-source.md) guide.

3. Download and export models:

     Follow the model preparation steps in [Prerequisites](#prerequisites).

4. Configure and export the environment:

     From the `live-video-analysis/live-video-captioning-rag` directory, use the helper script below to configure and export the application environment.

     ```bash
     # Configure environment variables. By default, the application uses the CPU device for embedding and LLM.
     # To use GPU, edit `setup_env.sh` and set: DEVICE="GPU"
     # Set LLM_MODEL_ID to your prepared LLM model.
     # Set EMBEDDING_MODEL_NAME to your desired embedding model.

     # Source the script to apply the environment.
     source scripts/setup_env.sh
     ```

5. Start the Live Video Captioning RAG sample application:

     From the `live-video-analysis/live-video-captioning-rag` directory, start the sample application using the Docker Compose tool:

     ```bash
     docker compose up -d
     ```

     > **Note:** The application will take some time to start. Check the container status and ensure that they are in the `"healthy/running"` state using the `docker ps` command before accessing the application.

6. Access the application:

     To start the application:

     a. From the web browser, navigate to the `Live Video Captioning RAG` dashboard at `http://<HOST_IP>:4172`.

     b. Enter any query in the chatbot.

     > **Note:** You will get a generic response at this point because no context has been created in the vector store yet.

     c. To demonstrate the full functionality, run the following commands to create the context using a sample image and caption:

     ```bash
     # Navigate to the directory
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag

     # Run the Python script
     python3 sample/demo_call_embedding.py
     ```

     > **Note:** Intel provides this script for demonstration purposes only. The script will:
     > - Download a sample image.
     > - Call the `embeddings/` endpoint to generate embeddings.
     > - Create the context and store it in the vector store.

     d. Once the script completes its execution, return to the dashboard in your browser and test the chatbot with contextual queries.<br>
        `Example query: "How many students are there in the classroom?"`<br>
        You will now receive contextual responses from the RAG chatbot.

7. Stop the Live Video Captioning RAG sample application services:

     ```bash
     docker compose down
     ```

## Integration with Live Video Captioning

This sample application can run together with the Live Video Captioning sample applicaion to enable embedding creation and RAG-based contextual chat.
For setup instructions, see [Setup Live Video Captioning RAG along with Live Video Captioning](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning/how-to-guides/configure-embedding-creation-with-rag.html)

## Learn More

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [API Reference](./api-reference.md)
- [Build from Source](./get-started/build-from-source.md)
- [Known Issues](./known-issues.md)

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements.md
./get-started/build-from-source.md

:::
hide_directive-->
