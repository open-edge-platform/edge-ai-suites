FROM node:20-alpine

# Optional proxy support (for npm install)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV http_proxy=${http_proxy:-$HTTP_PROXY} \
    https_proxy=${https_proxy:-$HTTPS_PROXY} \
    no_proxy=${no_proxy:-$NO_PROXY} \
    HTTP_PROXY=${HTTP_PROXY:-$http_proxy} \
    HTTPS_PROXY=${HTTPS_PROXY:-$https_proxy} \
    NO_PROXY=${NO_PROXY:-$no_proxy}

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copy the rest of the app
COPY . .

EXPOSE 3000

# Default command: run Vite dev server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
