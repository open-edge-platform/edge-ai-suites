FROM docker.io/library/node:25

USER root

# Pull Debian security fixes (addresses libpng/libpq/linux-libc-dev CVEs when available in node security)
RUN apt-get update \
  && apt-get -y upgrade \
  && apt-get -y autoremove \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /usr/src/app

# Upgrade npm to latest package version
RUN npm install -g npm@latest

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code to the working directory
COPY . .

# Build the Vue.js application
RUN npm run build

# REMOVE build-time dependencies
RUN rm -rf node_modules

# Install serve globally *before* switching user
RUN npm install -g serve

# Expose the port the app runs on
EXPOSE 3000

# Add non root user
ARG USER=intelmicroserviceuser
ARG UID=1999
RUN useradd -ms /bin/bash ${USER} -o -u $UID && \
    chown ${USER}:${USER} -R /usr/src/app /root
RUN mkdir -p /home/${USER}/ && chown -R ${USER}:${USER} /home/${USER}
USER ${USER}

# Serve built static files
CMD ["serve", "-s", "dist", "-l", "3000"]