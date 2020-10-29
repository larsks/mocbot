FROM python:3.8-alpine AS builder

RUN apk add --update czmq czmq-dev gcc g++
RUN pip install -U pip

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM python:3.8-alpine

RUN apk add --update czmq su-exec
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin/supybot* /usr/local/bin
COPY --from=builder /usr/local/bin/gunicorn* /usr/local/bin

RUN adduser -D -h /app mocbot

COPY . /app
WORKDIR /app

COPY docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
