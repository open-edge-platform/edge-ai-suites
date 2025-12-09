# Environment Variables

This reference application's configuration has the following environment variables.

- **SAMPLE_APP**
- (String). Refers to the application in context, name should match the app directory name
- **APP_DIR**
- (String). Optional. Refers to absolute path to the sample app directory. It gets auto-populated during app installation.

In addtion to the ones above, the application also uses environment variables of following two Microservices:

1. DL Streamer Pipeline Server
    - DL Streamer Pipeline Server reference document on environment variables is present [here](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/environment-variables.html)

2. Model Registry Microservice
    - Model Registry Microservice's reference document on environment variables is present [here](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-registry/environment-variables.html)