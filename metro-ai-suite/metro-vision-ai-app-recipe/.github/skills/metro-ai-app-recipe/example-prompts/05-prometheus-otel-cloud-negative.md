# Cloud Prometheus + OpenTelemetry metrics stack (negative / should NOT trigger)

Set up a Prometheus + OpenTelemetry metrics and tracing stack for a cloud-hosted
Kubernetes microservice running on AWS, with Grafana dashboards for request
latency and error rates.

This case exists to confirm the skill's **`DO NOT USE FOR`** boundary holds. It
is a cloud-only, Prometheus/OpenTelemetry **metrics** deployment with no Intel
edge hardware and no computer-vision pipeline, so the `metro-ai-app-recipe`
skill should **not** trigger. The correct response is generic
Prometheus/OTel/Kubernetes guidance, not the Intel-hardware DLSPS + MediaMTX +
Node-RED + Grafana CV recipe.
