# Update config in Time Series Analytics Microservice

The Time Series Analytics Microservice provides an interactive Swagger UI at `http://<host_ip>:5000/docs`.

**Note:** Use the link `http://localhost:30002/docs` to access the Swagger UI if doing a Helm-based deployment on a Kubernetes cluster.

## Accessing the Swagger UI

### To view the current configuration:

1. Open the Swagger UI in your browser.
2. Locate the `GET /config` endpoint.
3. Expand the endpoint and click **Execute**.
4. The response will display the current configuration of the Time Series Analytics Microservice.

### To activate the new UDF deployment package

1. Open the Swagger UI in your browser.
2. Locate the `GET /config` endpoint.
3. Expand the endpoint, set the `restart` option to `true` in the request body, and click **Execute**.
4. The response will display the current configuration and activate the new UDF deployment of the Time Series Analytics Microservice.

### To update the current configuration:

1. Open the Swagger UI in your browser.
2. Find the `POST /config` endpoint.
3. Expand the endpoint, enter the new configuration in the request body, and click **Execute**.
4. The service will apply the updated configuration and start with the new configuration.
