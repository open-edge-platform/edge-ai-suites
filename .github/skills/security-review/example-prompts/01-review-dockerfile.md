# Review a Dockerfile for security issues

Review the changes to this `Dockerfile` for security problems at authoring time.
Flag any use of floating tags, root execution, embedded secrets, `ADD` where
`COPY` suffices, or missing multi-stage cleanup. Classify each finding as either
"Fix in artifact" or "Deployment-time responsibility", assign a severity
(Critical/High/Medium/Low) and a confidence level, and reference the specific
line and a recommended fix.

```dockerfile
FROM python:latest
WORKDIR /app
ADD . /app
ENV API_TOKEN=sk-prod-abc123
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
```
