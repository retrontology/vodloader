
from typing import Dict
from irc.client import Event
from datetime import datetime, timezone


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
