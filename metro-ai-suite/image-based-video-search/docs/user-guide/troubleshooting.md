# Troubleshooting

This page provides troubleshooting steps, FAQs, and resources to help you
resolve common issues. If you encounter any problems with the application not addressed here,
check the [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues) board.
Feel free to file new tickets there (after learning about the guidelines for [Contributing](https://github.com/open-edge-platform/edge-ai-suites/blob/main/CONTRIBUTING.md)).

## Troubleshooting Common Issues

1. **Containers Not Starting**

- **Issue**: The application containers fail to start.

- **Solution**:

  ```bash
  docker compose logs
  ```

  Check the logs for errors and resolve dependency issues.

2. **Port Conflicts**

- **Issue**: Port conflicts with other running applications.

- **Solution**: Update the ports section in the Docker Compose file.

3. **`ibvs-milvusdb` container is unhealthy**

- **Issue**: `ibvs-milvusdb` container fails to start.

- **Solution**:

  Currently, milvusdb does not work with proxy servers. Make sure that the proxies `http_proxy`, `https_proxy` and `no_proxy` are set to empty string in `compose.yml` file.

4. **Empty search results after clicking on `Search Object`**

- **Issue**: Search results are empty after clicking on `Search Object` button.

- **Solution**:

  - Make sure the models are able to detect the objects in the stream correctly
  - Make sure you have analysed the stream first to capture the video frames into milvus database
  - Make sure you are using the right frame to search the object
  - Increase the 'To' timestamp in the search results to accommodate the latest results

5. **Failure to launch `ibvs-app`, `ibvs-featurematching` or `ibvs-streaming` containers**

- **Issue**: One of the above containers fails to come up.

- **Solution**:

  Try building the image locally as mentioned in Step 2 of
  [Set up and First Use](./get-started.md#set-up-and-first-use) before bringing up the containers.

## Troubleshooting Helm Deployments

1. **Helm Chart Not Found**

   - Check if the Helm repository was added:

     ```bash
     helm repo list
     ```

2. **Pods Not Running**:

   - Review pod logs:

     ```bash
     kubectl logs {{pod-name}} -n {{namespace}}
     ```

3. **Service Unreachable**:

   - Confirm the service configuration:

     ```bash
     kubectl get svc -n {{namespace}}
     ```
