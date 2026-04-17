# Known Issues

## Limited Functionality when Deployed Standalone

- This sample application is now designed to run with the Live Video Captioning sample application.
- If you run the Live Video Captioning RAG sample application by itself, the application can still start, but its capabilities may be limited because it does not receive the continuous frame, caption, and metadata inputs that are produced by the Live Video Captioning sample application.
- In standalone mode, chatbot responses may remain generic or have reduced contextual accuracy until embeddings are added manually or until another upstream workflow provides the required context data.

## Not Tested on EMT-S and EMT-D Variants of Edge Microvisor Toolkit

- Intel does not validate the sample application on the EMT-S and EMT-D variants of the Edge Microvisor Toolkit.
