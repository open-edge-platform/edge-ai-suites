# Environment Variables

This reference application's configuration has the following environment variables.

- **SAMPLE_APP**
- (String). Refers to the application in context, name should match the app directory name
- **APP_DIR**
- (String). Optional. Refers to absolute path to the sample app directory. It gets auto-populated during app installation.

In addition to the ones above, the application also uses environment variables of following two Microservices:

1. [DL Streamer Pipeline Server](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/environment-variables.html)

2. [Model Registry Microservice](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-registry/environment-variables.html)
