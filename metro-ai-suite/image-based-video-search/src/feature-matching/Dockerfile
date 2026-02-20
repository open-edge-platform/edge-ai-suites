FROM docker.io/library/python:3.11

USER root

# Pull Debian security fixes (addresses libpng/libpq/linux-libc-dev CVEs when available in node security)
RUN apt-get update \
 && apt-get -y upgrade \
 && apt-get install --yes --no-install-recommends gstreamer1.0-plugins-ugly wget \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

RUN python -m pip install --upgrade \
    pip \
    setuptools \
    wheel

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY encoder.py milvus_utils.py schemas.py server.py ./

# Add non root user
ARG USER=intelmicroserviceuser
ARG UID=1999
RUN useradd -ms /bin/bash ${USER} -o -u $UID && \
    chown ${USER}:${USER} -R /usr/src/app /root
RUN mkdir -p /usr/src/app/static && \
    chown -R ${USER}:${USER} /usr/src/app/static
RUN mkdir -p /home/${USER}/ && chown -R ${USER}:${USER} /home/${USER}
USER ${USER}

CMD uvicorn server:app --host 0.0.0.0