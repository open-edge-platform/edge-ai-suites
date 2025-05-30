# How to enable System Metrics Dashboard

To enable the system metrics dashboard for validation, run the following command:

```bash
make up_opcua_ingestion INCLUDE=validation
```

> **Note**: The system metrics dashboard is only supported with Docker Compose deployments and requires `Telegraf` to run as the `root` user.

##  Viewing System Metrics Dashboard

- Use link `http://<host_ip>:3000` to launch Grafana from browser (preferably, chrome browser)

- Login to the Grafana with values set for `VISUALIZER_GRAFANA_USER` and `VISUALIZER_GRAFANA_PASSWORD`
    in `.env` file and select **System Metrics Dashboard**.

    ![Grafana login](./_images/login_wt.png)

- After login, click on Dashboard 

    ![Menu view](./_images/dashboard.png)

- Select the `System Metrics Dashboard`.

    ![List all dashboard](./_images/list_all_dashboard.png)

- One will see the below output.

    ![System Metrics Dashboard](./_images/system_metrics_dashboard.png)