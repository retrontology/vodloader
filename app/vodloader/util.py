import os
from pathlib import Path
from typing import Dict
from irc.client import Event
from datetime import datetime, timezone


DEFAULT_DOWNLOAD_DIR = 'videos'


def get_download_dir() -> Path:
    if 'DOWNLOAD_DIR' not in os.environ:
        os.environ['DOWNLOAD_DIR'] = DEFAULT_DOWNLOAD_DIR
    download_dir = Path(os.environ['DOWNLOAD_DIR'])
    return download_dir

def parse_tags(event: Event) -> Dict[str, str]:
    tags = {}
    for tag in event.tags:
        tags[tag['key']] = tag['value']
    return tags

def parse_irc_ts(timestamp: int | str) -> datetime:
    local = datetime.now(timezone.utc).astimezone().tzinfo
    timestamp = float(timestamp)/1000
    datetime_ts = datetime.fromtimestamp(timestamp, local)
    datetime_ts = datetime_ts.astimezone(timezone.utc)
    return datetime_ts
