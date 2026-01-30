# 🎓 Smart Classroom

The **Smart Classroom** project is a modular, extensible framework designed to process and summarize educational content using advanced AI models. It supports transcription, summarization, mindmap generation and future capabilities like video understanding and real-time analysis. 

The main features are as follows:

•	Audio transcription with ASR models (e.g., Whisper, Paraformer)\
•	Speaker diarization is supported using Pyannote Audio models.
•	Summarization using powerful LLMs (e.g., Qwen, LLaMA)\
•	MindMap Generation using Mermaid.js for visual diagram rendering of the summary\
•	Plug-and-play architecture for integrating new ASR and LLM models\
•	API-first design ready for frontend integration\
•	Video analysis

## Get Started 

To see the system requirements and other installations, see the following guides:

- [System Requirements](./docs/user-guide/system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up the application.
- [Application Flow](./docs/user-guide/application-flow.md): Check the flow of application.

## How It Works

The basic architecture follows a modular pipeline designed for efficient audio summarisation. It begins with **audio preprocessing**, where FFMPEG chunks input audio into smaller segments for optimal handling. These segments are processed by an **ASR transcriber** (e.g., Whisper or Paraformer) to convert speech into text. Finally, an **LLM summariser** (such as Qwen or Llama), optimised through frameworks like OpenVINO IR, Llama.cpp, or IPEX, generates concise summaries, which are delivered via the **output handler** for downstream use.


![High-Level System Diagram](./docs/user-guide/images/architecture.svg)


For more information see [How it works](./docs/user-guide/how-it-works.md)

## Learn More

•	[Release Notes](./docs/user-guide/release-notes.md)
