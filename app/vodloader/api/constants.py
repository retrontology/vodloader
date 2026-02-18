"""
API constants and configuration values.
"""

# Valid quality options for Twitch streams
VALID_QUALITIES = [
    'best', 'worst', 'source', 
    '1080p', '720p', '480p', '360p', '160p'
]

# HTTP status codes
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 403
HTTP_NOT_FOUND = 404

# Response status indicators
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_INFO = "info"