"""
Authentication and authorization utilities for the API.
"""

from quart import request, current_app
from .constants import STATUS_ERROR, HTTP_UNAUTHORIZED


def check_auth():
    """Check if request is authorized"""
    return 'secret' in request.headers and request.headers['secret'] == current_app.secret_key


def require_auth(func):
    """Decorator to require authentication for API endpoints"""
    async def wrapper(*args, **kwargs):
        if not check_auth():
            return {"status": STATUS_ERROR, "message": "Unauthorized"}, HTTP_UNAUTHORIZED
        return await func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper