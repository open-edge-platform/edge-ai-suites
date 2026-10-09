FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && python -m pip uninstall -y pip

COPY server.py mcp-server/server.py
RUN mkdir -p configs/dlstreamer-pipeline-server && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "mcp-server/server.py"]