# search_image_by_image

A Helm chart for search_image_by_image

## Installing the Chart

To install the chart with the release name `my-release`:

```bash
# Standard Helm install
$ helm install  my-release search_image_by_image

# To use a custom namespace and force the creation of the namespace
$ helm install my-release --namespace my-namespace --create-namespace search_image_by_image

# To use a custom values file
$ helm install my-release -f my-values.yaml search_image_by_image
```

See the [Helm documentation](https://helm.sh/docs/intro/using_helm/) for more information on installing and managing the chart.

## Configuration

The following table lists the configurable parameters of the search_image_by_image chart and their default values.

| Parameter                    | Default                               |
| ---------------------------- | ------------------------------------- |
| `broker.imagePullPolicy`     | `IfNotPresent`                        |
| `broker.replicas`            | `1`                                   |
| `broker.repository.image`    | `docker.io/library/eclipse-mosquitto` |
| `broker.repository.tag`      | `2.0.20`                              |
| `broker.serviceAccount`      | ``                                    |
| `mediamtx.imagePullPolicy`   | `IfNotPresent`                        |
| `mediamtx.replicas`          | `1`                                   |
| `mediamtx.repository.image`  | `docker.io/bluenviron/mediamtx`       |
| `mediamtx.repository.tag`    | `1.10.0`                              |
| `mediamtx.serviceAccount`    | ``                                    |
| `streaming.imagePullPolicy`  | `IfNotPresent`                        |
| `streaming.replicas`         | `1`                                   |
| `streaming.repository.image` | `streaming-pipeline`                  |
| `streaming.repository.tag`   | ``                                    |
| `streaming.serviceAccount`   | ``                                    |


