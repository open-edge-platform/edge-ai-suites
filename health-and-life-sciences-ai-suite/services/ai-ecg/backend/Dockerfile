
FROM python:3.10-slim

ENV http_proxy=http://proxy-iind.intel.com:912
ENV https_proxy=http://proxy-iind.intel.com:912
ENV HTTP_PROXY=http://proxy-iind.intel.com:912
ENV HTTPS_PROXY=http://proxy-iind.intel.com:912
ENV no_proxy=localhost,127.0.0.1,::1
ENV NO_PROXY=localhost,127.0.0.1,::1


WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
