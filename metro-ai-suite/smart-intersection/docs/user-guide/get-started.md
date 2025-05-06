# Get Started

<!--
**Sample Description**: Provide a brief overview of the application and its purpose.
-->
The Smart Intersection Application is a modular sample application designed to help developers create intelligent intersection monitoring solutions. By leveraging AI and sensor fusion, this sample application demonstrates how to achieve accurate traffic detection, congestion management, and real-time alerting.

<!--
**What You Can Do**: Highlight the developer workflows supported by the guide.
-->
By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run a predefined pipeline**: Execute a sample pipeline to see real-time traffic monitoring and object detection in action.
- **Modify application parameters**: Customize settings like input sources, tracking parameters, camera properties and regions of interest to adapt the application to your specific requirements.


## Prerequisites
- Verify that your system meets the [Minimum Requirements](./system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/). Enable running docker without "sudo": [Post Install](https://docs.docker.com/engine/install/linux-postinstall/)

<!--
**Setup and First Use**: Include installation instructions, basic operation, and initial validation.
-->
## Set up and First Use

<!--
**User Story 1**: Setting Up the Application  
- **As a developer**, I want to set up the application in my environment, so that I can start exploring its functionality.

**Acceptance Criteria**:
1. Step-by-step instructions for downloading and installing the application.
2. Verification steps to ensure successful setup.
3. Troubleshooting tips for common installation issues.
-->

1. **Download the Smart Intersection Application**

    To begin, download the full application package, which includes all source code, container images and configuration files.
        
    - Visit the **Smart Intersection Sample Application** page in the [Edge Software Catalog](https://edgesoftwarecatalog.intel.com/).
    - Click on the **"Request Access"** button in the **Get Started** section.
 
    - After approval, you will receive a confirmation email containing a product key and download instructions.
 
    - Once downloaded, Extract the folder to access the source code and the artifacts required for the sample application:
      ```bash
      unzip intel-scenescape-itep.zip
      cd intel-scenescape-itep
      chmod +x edgesoftware
      ./edgesoftware download
      cd Smart_Intersection_Sample_Application_1.0.0/SMART_INTERSECTION/smart_intersection/
      ```

2. **Setup Credentials**:
    - Use docker to setup the credentials:
      ```bash
      docker run --rm -ti \
          -v $(pwd)/init.sh:/init.sh \
          -v $(pwd)/chart:/chart \
          -v $(pwd)/src:/src \
          docker.io/library/python:3.12 bash init.sh
      ```

3. **Import Scenescape Container Images**:
    - Use docker load to import the container images:
      ```bash
      docker load -i ./images/scenescape.tar
      docker load -i ./images/scenescape-controller.tar
      ```
## Select Deployment Option

Choose one of the following methods to deploy the Smart Intersection application:

- **[Deploy Using Docker Compose](./how-to-deploy-docker.md)**: Use Docker Compose to quickly set up and run the application in a containerized environment.
- **[Deploy Using Helm](./how-to-deploy-helm.md)**: Use Helm to deploy the application to a Kubernetes cluster for scalable and production-ready deployments.

## Supporting Resources
- [Docker Compose Documentation](https://docs.docker.com/compose/)
