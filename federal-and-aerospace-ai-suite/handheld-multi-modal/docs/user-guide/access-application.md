# Access Application User Interface

This composite application exposes multiple endpoints through the NGINX TLS reverse proxy.
They are bound to localhost only and are not exposed on any external IP address.
Since the intended use is on handheld devices, the applications do not provide authentication
or authorization.

> **Notice**:
> The "self-signed certificate" browser warning is expected.
> Modern browsers require HTTPS to enable microphone input used by Open WebUI and
  Speech To Text services, therefore, the NGINX reverse proxy uses the certificate to ensure
  TLS transport on the `localhost` bound addresses.

To add a certificate to the trust pool, open a browser of your choice and navigate to `Settings->Certificates->Manage certificates` page. Next, select the `Authorities` tab and click `Import`. In file explorer, navigate to the folder that contains Handheld Multi-Modal Application and select the `data/nginx-certs/ca-cert.pem` file. Finally, select the `Trust this CA to identify websites` checkbox and click `Ok`.


| Service | URL | Notes |
|---------|-----|-------|
| Single pane page | https://localhost:443 | via NGINX reverse proxy |
| Visual Pipeline and Platform Evaluation Tool UI | https://localhost:1443 | via NGINX reverse proxy |
| Open WebUI | https://localhost:8443 | Conversational Agent backed by LLM — browser microphone enabled (via NGINX reverse proxy) |
| Whisper speech-to-text service | https://localhost:5443 | Speech-to-text — browser microphone enabled (via NGINX reverse proxy) |
| Grafana dashboard | https://localhost:7443 | Pre-provisioned dashboards (via NGINX reverse proxy) |


<!--
Source: [Endpoints](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/federal-and-aerospace-ai-suite/handheld-multi-modal/README.md#endpoints)
-->

## ViPPET

After opening the main page of ViPPET, you can select one of the several options available in ViPPET:
1) Pipelines - to check and run one of the predefined pipelines and understand how it works. Predefined pipelines will provide a video output stream that shows how a model works, as well as a small subset of system metrics during execution of the pipeline. It also exposes an option to add a new custom pipeline for advanced users, but it might require additional input from other options.
2) Benchmarks - allows you to compare performance of pipelines on different combinations of supported hardware (CPU/NPU/GPU/NPU+GPU) to find out the best device for a specific pipeline.
3) Models - exposes a list of available models that can be used in a pipeline, as well as the import functionality for models.
4) Video/Images/Cameras - allows configuration of data source that could be used in a pipeline.

## Open WebUI

The main page exposes a chat with the default AI model, where you can ask questions. If an initial response is not sufficient, the chat with the AI model can be continued in the same window, which will keep context. If a question is related to attachment(s), such as a file, web-page or other chat, it could be added by clicking the `+` sign and selecting the corresponding option.
It is recommended to open the `New Chat` window and start a new chat to change the topic and to keep the AI model context clean, as it improves results.

## Whisper

On the main page of Whisper, there are two options to upload audio for the transcription:
1) By uploading an audio file in one of the supported audio formats ("flac", "m4a", "mp3", "mp4", "ogg", "wav", "webm") and clicking on the corresponding section in UI, and selecting a file in the file explorer, or by drag-and-dropping the file into the section.
2) By recording audio from a microphone. Click the round `record` button, allow Whisper access to the microphone and start talking into the microphone.
In both cases, the transcription text will appear on the lower part of the page in real-time, in parts, as soon as Whisper has completed the transcription of a part of the recording. Once the whole recording has been transcribed, an additional section will appear and show the duration and ratio of the transcription.

## Grafana

By default, the main page shows generic metrics from the system, such as CPU/NPU and power consumption. To switch to more detailed, per-application view, navigate to `Dashboards->Panther Lake Live Dashboard`. On this dashboard, most of the metrics will be either empty or will not display any values, since the metrics are gathered in real-time and other applications must execute a workload to generate metrics. The metrics map to other handheld applications as follows:
1) `Frame Rate Over Time` and `Latest Pipeline Frame Rate Average` are from ViPPET.
2) `LLM Number of Responses Generated` and `LLM Number of Responses Generated` are from Open WebUI.
3) `Speech to text Processing Ratio Last` and `Speech To Text Processing Ratio` are from Whisper.
Metrics do not persist in any database, so a refresh of the page will reset ALL gathered metrics.
