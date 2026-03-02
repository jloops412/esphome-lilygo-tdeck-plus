ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache bash
RUN pip3 install --no-cache-dir flask requests

COPY rootfs/ /

RUN chmod a+x /run.sh

CMD ["/run.sh"]
