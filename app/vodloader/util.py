
from typing import Dict, Any
from datetime import datetime, timezone


class MockEvent:
    """Mock event class used by IRC ingestion."""
    def __init__(self, tags=None, source='', target='', arguments=None):
        self.tags = tags or []
        self.source = source
        self.target = target
        self.arguments = arguments or []


def parse_tags(event: Any) -> Dict[str, str]:
    """Parse tags from the internal mock event format."""
    tags = {}
    if hasattr(event, 'tags') and event.tags:
        for tag in event.tags:
            if isinstance(tag, dict):
                tags[tag['key']] = tag['value']
    return tags

def parse_irc_ts(timestamp: int | str) -> datetime:
    local = datetime.now(timezone.utc).astimezone().tzinfo
    timestamp = float(timestamp)/1000
    datetime_ts = datetime.fromtimestamp(timestamp, local)
    datetime_ts = datetime_ts.astimezone(timezone.utc)
    return datetime_ts
