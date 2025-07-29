# Get Help

This page provides comprehensive support and troubleshooting information for the Smart NVR Sample Application. It is divided into the following sections:

  - **Common Issues**: General troubleshooting steps for resolving issues like container failures, port conflicts, and missing dependencies.
  - **Troubleshooting Docker Deployments**: Steps to address problems specific to Docker deployments.

## Troubleshooting Common Issues

### 1. Containers Not Starting
- **Issue**: The application containers fail to start.
- **Solution**:

  ```bash
  docker ps
  docker logs <container-id>
  ```
  Check the logs for errors.

### 2. Port Conflicts
- **Issue**: Port conflicts with other running applications.
- **Solution**: Update the ports section in the Docker Compose file.
  
### 3. Description not coming in UI
- Check logs for frigate container
- Check if VLM microservice is running and reachable.
- Verify that `NVR_GENAI=true` is set and frigate config has `genai.enabled: true`

### 4. GenAI Event Descriptions Not Working
- **Issue**: AI-powered event descriptions are not being generated or displayed.
- **Solution**:
  - Ensure `NVR_GENAI=true` environment variable is set before starting the application
  - Verify the frigate configuration file has `genai.enabled: true`
  - Check VLM microservice logs for connectivity issues: `docker logs <vlm-container-id>`
  - Verify the model specified in frigate config matches the one deployed in VLM service
  - Note: This is an experimental feature with known stability issues

### 5. Object not getting detected 
- Check the label in frigate config.yaml for the specific camera
- Check the top_score parameter 

### 6. "No video footage available" warning during Summarize/Search Clip
- Ensure the browser’s date and time are correctly set and in sync with the system time of the machine running the NVR services.
- Video clips are only available from the time the NVR services started running. If a past time (before service start) is selected, this warning will be shown.

## Troubleshooting Docker Containers

### 1. Containers Failing:
   - Check the Docker logs for errors:
     ```bash
     docker ps
     docker logs <container-id>
     ```
### 2. Port Conflicts:
   - Update the `ports` section in the Compose file to resolve conflicts.
### 3. Reset Application:
   - Follow these steps to reset the application to the initial state
     ```bash
     ./setup.sh stop
     docker volume ls | grep nvr-event-router | awk '{ print $2 }' | xargs docker volume rm
     ```
<!--
## Support
- **Developer Forum**: Join the community forum
- **Contact Support**: [Support Page](#)
-->
