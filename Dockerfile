FROM python:3.11-slim-bookworm

RUN mkdir /app

COPY app /app

WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT ["/bin/bash"]