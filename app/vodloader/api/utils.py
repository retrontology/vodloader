"""
Utility functions for API request handling.
"""

from quart import request
from .constants import STATUS_ERROR, HTTP_BAD_REQUEST


async def parse_json_body(required=False):
    """Parse JSON body with error handling"""
    try:
        data = await request.get_json()
        if required and not data:
            return None, {"status": STATUS_ERROR, "message": "No JSON data provided"}, HTTP_BAD_REQUEST
        return data or {}, None, None
    except Exception:
        return None, {"status": STATUS_ERROR, "message": "Invalid JSON in request body"}, HTTP_BAD_REQUEST


