FROM node:20-alpine

# Optional proxy support (for npm install)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

WORKDIR /app

RUN apk add --no-cache libc6-compat
# Install dependencies first (better layer caching)
COPY package.json package-lock.json* ./
RUN rm -rf node_modules package-lock.json \
    && npm install

# Copy the rest of the app
COPY . .

RUN npm run build

EXPOSE 3000

# Default command: run Vite dev server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]




