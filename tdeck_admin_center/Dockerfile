ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache bash python3 py3-flask py3-requests

COPY rootfs/ /

RUN chmod a+x /run.sh

CMD ["/run.sh"]
