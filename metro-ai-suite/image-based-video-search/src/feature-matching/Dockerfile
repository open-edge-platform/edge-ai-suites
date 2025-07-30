FROM docker.io/library/python:3.11

USER root

WORKDIR /usr/src/app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY encoder.py milvus_utils.py schemas.py server.py ./

# Add non root user
ARG USER=intelmicroserviceuser
ARG UID=1999
RUN useradd -ms /bin/bash ${USER} -o -u $UID && \
    chown ${USER}:${USER} -R /usr/src/app /root
RUN mkdir -p /home/${USER}/ && chown -R ${USER}:${USER} /home/${USER}
USER ${USER}

CMD uvicorn server:app --host 0.0.0.0