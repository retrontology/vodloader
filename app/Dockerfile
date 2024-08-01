FROM python:3.12.4-bookworm

RUN mkdir /opt/vodloader
WORKDIR /opt/vodloader

COPY requirements.txt /opt/vodloader/requirements.txt
RUN python -m pip install -r /opt/vodloader/requirements.txt

COPY *.py /opt/vodloader/
COPY config.yml /opt/vodloader/config.yml

VOLUME /opt/maierbox/static

EXPOSE 80

CMD ["/usr/bin/bash", "/opt/maierbox/start.sh"]
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl --unix-socket /opt/maierbox/socket/gunicorn.sock http://localhost/ || exit 1
