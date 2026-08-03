# Review Helm chart pod security defaults

Review this Helm `values.yaml` / pod spec fragment for development-time security
defaults. Check for `runAsNonRoot`, `allowPrivilegeEscalation: false`, read-only
root filesystem, dropped Linux capabilities, pinned image tags, and secrets not
templated directly into the chart. Classify concerns as "Fix in artifact" versus
"Deployment-time responsibility", and do not enforce cluster-wide or node-level
controls.

```yaml
image:
  repository: myorg/app
  tag: latest
securityContext:
  runAsUser: 0
  privileged: true
```
