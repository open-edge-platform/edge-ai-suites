# Copyright Intel Corporation

FROM ubuntu:22.04
# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

ARG TIMESERIES_UID
ARG TIMESERIES_USER_NAME
RUN groupadd $TIMESERIES_USER_NAME -g $TIMESERIES_UID && \
    useradd -r -u $TIMESERIES_UID -g $TIMESERIES_USER_NAME $TIMESERIES_USER_NAME
    
# Update package list and install Python and pip
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

HEALTHCHECK --interval=5m CMD exit 0

USER $TIMESERIES_USER_NAME
# Set the default command to run your application
CMD ["python3", "app.py"]

