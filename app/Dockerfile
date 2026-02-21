FROM python:3.12.4-bookworm

ENV DOWNLOAD_DIR=/opt/vodloader/videos
ENV DB_PATH=/opt/vodloader/database/db.sqlite

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/vodloader/src
WORKDIR /opt/vodloader

COPY vodloader/ /opt/vodloader/vodloader/
COPY __about__.py pyproject.toml README.md /opt/vodloader/

RUN python -m pip install -e .

# Playwright browser and system deps for chat overlay generation (Chromium only)
RUN playwright install --with-deps chromium

VOLUME /opt/vodloader/videos
VOLUME /opt/vodloader/database

EXPOSE 8000 8001

CMD ["python", "-m", "vodloader.run"]
#HEALTHCHECK --interval=30s --timeout=3s \
#  CMD curl http://localhost:8000/ || exit 1
