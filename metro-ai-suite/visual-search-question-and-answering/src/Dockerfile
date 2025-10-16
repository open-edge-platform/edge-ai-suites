# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12.10-slim

ENV LANG=C.UTF-8

ARG ARCH="gpu"

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing libgl1-mesa-glx libglib2.0-0 build-essential ca-certificates wget curl

RUN useradd -m -s /bin/bash user && \
mkdir -p /home/user && \
chown -R user /home/user/

COPY visual-search-question-and-answering /home/user/visual-search-qa
RUN chown -R user /home/user/visual-search-qa

RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r /home/user/visual-search-qa/src/requirements.txt

ENV PYTHONPATH=$PYTHONPATH:/home/user

RUN mkdir -p /home/user/data && chown -R user /home/user/data

USER user

EXPOSE 17580

WORKDIR /home/user/visual-search-qa/src

CMD ["streamlit", "run", "app.py", "--server.port", "17580", "--server.headless", "true"]