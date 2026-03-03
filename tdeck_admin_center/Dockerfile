ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.20
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache bash python3 py3-flask py3-requests

COPY rootfs/ /
COPY run.sh /run.sh

RUN sed -i 's/\r$//' /run.sh && chmod a+x /run.sh

CMD ["/run.sh"]
