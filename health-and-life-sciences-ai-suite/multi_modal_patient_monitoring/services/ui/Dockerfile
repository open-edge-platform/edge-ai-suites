# -----------------------------
# Stage 1: Build the Vite App
# -----------------------------
FROM node:20-alpine AS build
 
# Optional build argument for API base URL
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
 
WORKDIR /app
 
# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install
 
# Copy source code
COPY . .
 
# Build the production app
RUN npm run build
 
 
# -----------------------------
# Stage 2: Serve with Nginx
# -----------------------------
FROM nginx:alpine
 
# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf
 
# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf
 
# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html
 
EXPOSE 3000
 
CMD ["nginx", "-g", "daemon off;"]