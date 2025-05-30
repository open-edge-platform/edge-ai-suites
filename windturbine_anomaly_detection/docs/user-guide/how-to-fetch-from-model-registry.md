# How to Fetch Models from the Model Registry

## Uploading Models to the Model Registry

1. Create a ZIP file with the following structure:
   ```
   udfs/
       ├── requirements.txt
       ├── <udf_script.py>
   tick_scripts/
       ├── <tick_script.tick>
   models/
       ├── <model_file.pkl>
   ```
2. Open the Model Registry Swagger UI at `http://<ip>:32002`.
3. Expand the `models` POST method and click **Try it out**.
4. Upload the ZIP file, specify the `name` and `version`, and click **Execute**.

## Updating Time Series Analytics Microservice `config.json` for Model Registry usage

To fetch UDFs and models from the Model Registry, update the configuration file at:
`time_series_analytics_microservice/config.json`.

1. Set `fetch_from_model_registry` to `true`.
2. Specify the `task_name` and `version` as defined in the Model Registry.
   > **Note**: Mismatched task names or versions will cause the microservice to restart.
3. Update the `tick_script` and `udfs` sections with the appropriate `name` and `models` details.
