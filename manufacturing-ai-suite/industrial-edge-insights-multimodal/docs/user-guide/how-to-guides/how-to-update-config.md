# Update config in Time Series Analytics Microservice

The Time Series Analytics Microservice provides an interactive Swagger UI at `https://<host_ip>:3000/ts-api/docs`.

## Accessing the Swagger UI

### View the current configuration

1. Open the Swagger UI in your browser.
2. Locate the `GET /config` endpoint.
3. Expand the endpoint and click **Execute**.
4. The response will display the current configuration of the Time Series Analytics Microservice.

### Activate the new UDF deployment package

1. Open the Swagger UI in your browser.
2. Locate the `GET /config` endpoint.
3. Expand the endpoint, set the `restart` option to `true` in the request body, and click **Execute**.
4. The response will display the current configuration and activate the new UDF deployment of the Time Series Analytics Microservice.

### Update the current configuration

1. Open the Swagger UI in your browser.
2. Find the `POST /config` endpoint.
3. Expand the endpoint, enter the new configuration in the request body, and click **Execute**.
4. The service will apply the updated configuration and start with the new configuration.
