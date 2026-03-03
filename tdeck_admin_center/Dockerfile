ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.20
ARG BUILD_VERSION=0.25.0
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1
ENV ADDON_VERSION=${BUILD_VERSION}

RUN apk add --no-cache bash python3 py3-flask py3-requests

COPY rootfs/ /
COPY run.sh /run.sh

RUN sed -i 's/\r$//' /run.sh && chmod a+x /run.sh

CMD ["/run.sh"]

