FROM python:3.12.4-bookworm

ENV DOWNLOAD_DIR=/opt/vodloader/videos
ENV DB_PATH=/opt/vodloader/database/db.sqlite

RUN mkdir -p /opt/vodloader/src
WORKDIR /opt/vodloader

COPY vodloader/ /opt/vodloader/vodloader/
COPY .env /opt/vodloader/.env
COPY pyproject.toml /opt/vodloader/pyproject.toml
COPY __about__.py /opt/vodloader/__about__.py

RUN python -m pip install -e .

VOLUME /opt/vodloader/videos
VOLUME /opt/vodloader/database

EXPOSE 8000 8001

CMD ["python", "-m", "vodloader.run"]
#HEALTHCHECK --interval=30s --timeout=3s \
#  CMD curl http://localhost:8000/ || exit 1
