FROM docker.io/library/node:24

USER root

# Set the working directory inside the container
WORKDIR /usr/src/app

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code to the working directory
COPY . .

# Build the Vue.js application
RUN npm run build

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