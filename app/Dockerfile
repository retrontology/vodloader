FROM python:3.12.4-bookworm

ENV DOWNLOAD_DIR=/opt/vodloader/videos
ENV DB_PATH=/opt/vodloader/database/db.sqlite

RUN mkdir -p /opt/vodloader/src
WORKDIR /opt/vodloader

COPY src/*.py /opt/vodloader/src/
COPY .env /opt/vodloader/.env

COPY requirements.txt /opt/vodloader/requirements.txt
RUN python -m pip install -r /opt/vodloader/requirements.txt

VOLUME /opt/vodloader/videos
VOLUME /opt/vodloader/database

EXPOSE 8000 8001

CMD ["python", "-m", "src.run"]
#HEALTHCHECK --interval=30s --timeout=3s \
#  CMD curl http://localhost:8000/ || exit 1
