
# How It Works
This section provides a high-level view of how the application processes audio input and integrates with a modular backend architecture.

![High-Level System Diagram](./images/education-ai-suite-smart-class-backend-service-layer.drawio.svg)

## Inputs

**Audio Files**
You can upload audio recordings through the *Web-based UI layer*, which supports:

- Audio upload
- Viewing transcription, summaries, and performance metrics
- Localisation options (English/Chinese)

The uploaded audio is passed to the Backend API, which acts as the gateway to the backend service layer and provides similar capabilities.

**Processing**

- **Audio Pre-processing**
  Cleans and formats audio data for downstream tasks.


- **ASR Component (Automatic Speech Recognition)**
  Converts audio into text using integrated ASR providers:
    - FunASR
    - OpenVINO
    - OpenAI


- **Summariser Component**
  Generates concise summaries of transcribed text using LLM providers:
    - iPexLLM
    - OpenVINO

- **Metrics Collector**
   Monitors and collects:
    - xPU utilisation for hardware performance
    - LLM metrics for summarisation efficiency


## Outputs

- Transcriptions and summaries can be accessed from the Web-based UI and file system. The path for file system is **/<project-location>/<your-project-name>/**. For example, /storage/chapter-10/
- Performance metrics (e.g., utilisation, model efficiency) are displayed for monitoring.
- Localisation ensures outputs are available in multiple languages (English/Chinese).


## Learn More

- [System Requirements](system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Get Started](get-started.md): Follow step-by-step instructions to set up the application.
- [Application Flow](application-flow.md): Check the flow of application.

