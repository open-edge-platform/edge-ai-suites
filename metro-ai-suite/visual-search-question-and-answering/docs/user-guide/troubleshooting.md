# Troubleshooting

## Error Logs

- Check the container log if a microservice shows mal-functional behaviors.

  ```bash
  docker logs <container_id>
  ```

- Click `showInfo` button on the web UI to get essential information about microservices

## VLM Microservice Model Loading Issues

**Problem**: VLM microservice fails to load or save models with permission errors, or you see errors related to model access in the logs.

**Cause**: This issue occurs when the `ov-models` Docker volume was created with incorrect ownership (root user) in previous versions of the application. The VLM microservice runs as a non-root user and requires proper permissions to read/write models.

**Symptoms**:

- VLM microservice container fails to start or crashes during model loading.
- Permission denied errors in VLM service logs.
- Model conversion or caching failures.
- Error messages mentioning `/home/appuser/.cache/huggingface` or `/app/ov-model` access issues.

**Solution**:

1. Stop the running application:

   ```bash
   docker compose -f compose_milvus.yaml down
   ```

2. Remove the existing `ov-models`:

   ```bash
   docker volume rm ov-models
   ```

3. Restart the application (the volume will be recreated with correct permissions):

   ```bash
   source env.sh
   docker compose -f compose_milvus.yaml up -d
   ```

> **Note**: Removing the `ov-models` volume will delete any previously
> cached/converted models. The VLM service will automatically re-download and
> convert models on the next startup, which may take additional time depending
> on your internet connection and the model size.

## Embedding Model Changed Issues

**Problem**: Dataprep microservice API fails and "mismatch" is found in logs.

**Cause**: If the application is re-deployed with a different embedding model set for the multimodal embedding service other than the previous deployment, it is possible that the embedding dimension has changed as well, leading to a vector dimension mismatch in vector DB.

**Solution**:

1. Stop the running application:

   ```bash
   docker compose -f compose_milvus.yaml down
   ```

2. Remove the existing Milvus volumes:

   ```bash
   sudo rm -rf /volumes/milvus
   sudo rm -rf /volumes/minio
   sudo rm -rf /volumes/etcd
   ```

3. Restart the application:

   ```bash
   source env.sh
   docker compose -f compose_milvus.yaml up -d
   ```

## Known Issues

- Sometimes downloading the demo dataset can be slow. Try manually downloading it from
[the website](https://data.vision.ee.ethz.ch/csergi/share/davis/DAVIS-2017-test-dev-480p.zip),
and put the zip file under your host `$HOME/data` folder.
