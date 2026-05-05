## Functional Test Steps

1. Install test dependencies:

    ```sh
    cd ./tests/functional/
    python3 -m venv env
    source env/bin/activate
    pip3 install -r ../requirements.txt
    ```

2. For Docker-related test cases, run the following commands:

   > **Note**: Docker and Docker Compose must be installed as prerequisites.

   ```sh
   pytest -v -s --html=docker_multimodal_report.html test_docker_deployment_multimodal.py
   ```

3. For Helm-related test cases, run the following commands:

   > **Note**: A Kubernetes cluster and Helm must be installed as prerequisites.

   ```sh
   pytest -v -s --html=helm_multimodal_report.html test_helm_deployment_multimodal.py
   ```
