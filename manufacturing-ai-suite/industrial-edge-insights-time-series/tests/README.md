## Functional Test Steps

1. Run the prerequisite script to clone git submodules:

    ```sh
    cd ./utils/
    ./github_clone.sh
    ```

2. Install test dependencies:

    ```sh
    cd ./functional/
    pip3 install -r ../requirements.txt
    ```

3. For Docker-related test cases, run the following commands:

   > **Note**: Docker and Docker Compose must be installed as prerequisites.

   * Wind Turbine Anomaly Detection

      ```sh
      pytest -v -s --html=docker_wind_turbine_report.html test_docker_deployment_wind_turbine.py

      # InfluxDB retention test
      pytest -v -s --html=docker_influxdb_retention_wind_turbine_report.html test_docker_influxdb_retention.py

      # Stability test
      pytest -v -s --html=docker_stability_wind_turbine_report.html test_docker_deployment_stability.py
      ```

   * Weld Anomaly Detection

      ```sh
      pytest -v -s --html=docker_weld_anomaly_report.html test_docker_deployment_weld_anomaly.py
      ```

4. For Helm-related test cases, run the following commands:

   > **Note**: A Kubernetes cluster and Helm must be installed as prerequisites.

   * Wind Turbine Anomaly Detection

      ```sh
      pytest -v -s --html=helm_wind_turbine_report.html test_helm_deployment_wind_turbine.py

      # InfluxDB retention test
      pytest -v -s --html=helm_influxdb_retention_wind_turbine_report.html test_helm_influxdb_retention.py
      ```

   * Weld Anomaly Detection

      ```sh
      pytest -v -s --html=helm_weld_anomaly_report.html test_helm_deployment_weld_anomaly.py
      ```

5. Security tests:

    ```sh
    pytest -v -s --html=report.html test_docker_helm_deployment_security.py
    ```