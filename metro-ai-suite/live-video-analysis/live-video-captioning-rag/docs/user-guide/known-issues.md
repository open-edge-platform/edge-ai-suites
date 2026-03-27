# Known Issues

## Limited functionality when deployed standalone

- This sample application is now designed to run alongside the Live Video Captioning application.
- If you run Live Video Captioning RAG by itself, the application can still start, but its capabilities may be limited because it does not receive the continuous frame, caption, and metadata inputs normally produced by Live Video Captioning.
- In standalone mode, chatbot responses may remain generic or have reduced contextual accuracy until embeddings are added manually or another upstream workflow provides the required context data.

## Not tested on EMT-S and EMT-D

- This release is not validated on EMT‑S and EMT‑D.