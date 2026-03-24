## Functional Test Steps

1. Run the prerequisite script to clone git submodules:

    ```sh
    # From the repository root
    cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/tests/utils/
    ./github_clone.sh
    cd ../../../../industrial-edge-insights-multimodal/tests/
    ```

2. Install test dependencies:

    ```sh
    cd ./functional/
    pip3 install -r ../requirements.txt
    ```

3. For Docker-related test cases, run the following commands:

   > **Note**: Docker and Docker Compose must be installed as prerequisites.

   ```sh
   pytest -v -s --html=docker_multimodal_report.html test_docker_deployment_multimodal.py
   ```

4. For Helm-related test cases, run the following commands:

   > **Note**: A Kubernetes cluster and Helm must be installed as prerequisites.

   ```sh
   pytest -v -s --html=helm_multimodal_report.html test_helm_deployment_multimodal.py
   ```
