"""
Vodloader API module.

This module provides a RESTful API for managing Twitch channels and their configurations.
The API is organized into submodules for better maintainability:

- auth: Authentication and authorization utilities
- validation: Request data validation functions
- utils: Common utility functions
- channels: Channel management endpoints
- constants: API constants and configuration
"""

from quart import Quart
from vodloader import config

from .channels import channels_bp
from .chat_config import chat_config_bp


def create_api() -> Quart:
    """Create and configure the API application"""
    app = Quart(__name__)
    
    if not config.API_KEY:
        raise RuntimeError('API_KEY must be specified')
    
    app.secret_key = config.API_KEY
    
    # Register blueprints
    app.register_blueprint(channels_bp)
    app.register_blueprint(chat_config_bp)
    
    return app


# Export commonly used functions and constants
from .auth import check_auth, require_auth
from .validation import (
    validate_quality, validate_delete_original_video, validate_channel_config,
    validate_chat_config, VALID_CHAT_POSITIONS, VALID_FONT_STYLES, VALID_FONT_WEIGHTS
)
from .utils import parse_json_body
from .constants import VALID_QUALITIES, STATUS_SUCCESS, STATUS_ERROR, STATUS_INFO

__all__ = [
    'create_api',
    'check_auth',
    'require_auth', 
    'validate_quality',
    'validate_delete_original_video',
    'validate_channel_config',
    'validate_chat_config',
    'parse_json_body',
    'VALID_QUALITIES',
    'VALID_CHAT_POSITIONS',
    'VALID_FONT_STYLES',
    'VALID_FONT_WEIGHTS',
    'STATUS_SUCCESS',
    'STATUS_ERROR', 
    'STATUS_INFO'
]