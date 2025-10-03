FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY fusion.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose any necessary ports (if needed for debugging/monitoring)
EXPOSE 8080

# Run the fusion service
CMD ["python", "fusion.py"]
