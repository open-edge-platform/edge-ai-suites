FROM docker.io/library/python:3.11

WORKDIR /usr/src/app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY encoder.py milvus_utils.py schemas.py server.py ./

CMD uvicorn server:app --host 0.0.0.0