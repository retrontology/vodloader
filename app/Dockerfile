FROM python:3.12.4-bookworm

RUN mkdir /opt/maierbox
WORKDIR /opt/maierbox

COPY requirements.txt /opt/maierbox/requirements.txt
RUN python -m pip install -r /opt/maierbox/requirements.txt
RUN python -m pip install gunicorn==22.0.0

COPY albums /opt/maierbox/albums
COPY categories /opt/maierbox/categories
COPY comments /opt/maierbox/comments
COPY images /opt/maierbox/images
COPY maierbox /opt/maierbox/maierbox
COPY posts /opt/maierbox/posts
COPY tags /opt/maierbox/tags
COPY watermarks /opt/maierbox/watermarks
COPY manage.py /opt/maierbox/manage.py
COPY start.sh /opt/maierbox/start.sh

VOLUME /opt/maierbox/static
VOLUME /opt/maierbox/media
VOLUME /opt/maierbox/socket

EXPOSE 80

CMD ["/usr/bin/bash", "/opt/maierbox/start.sh"]
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl --unix-socket /opt/maierbox/socket/gunicorn.sock http://localhost/ || exit 1
