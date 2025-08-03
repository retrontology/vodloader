"""
Chat configuration API endpoints.
"""

from quart import Blueprint
from vodloader.models import TwitchChannel

from .auth import require_auth
from .utils import parse_json_body
from .validation import validate_chat_config
from .constants import (
    STATUS_SUCCESS, STATUS_ERROR,
    HTTP_OK, HTTP_BAD_REQUEST, HTTP_NOT_FOUND
)

chat_config_bp = Blueprint('chat_config', __name__)


@chat_config_bp.route("/channels/<channel_name>/config/chat", methods=['GET'])
@require_auth
async def get_chat_config(channel_name: str):
    """Get chat overlay configuration for a channel"""
    channel_name = channel_name.lower()
    
    channel = await TwitchChannel.get(login=channel_name)
    if not channel:
        return {
            "status": STATUS_ERROR,
            "message": "Channel does not exist in database"
        }, HTTP_NOT_FOUND
    
    config = await channel.get_config()
    
    # Return current configuration with effective values (including defaults)
    chat_config = {
        "font_family": config.get_chat_font_family(),
        "font_size": config.get_chat_font_size(),
        "font_style": config.get_chat_font_style(),
        "font_weight": config.get_chat_font_weight(),
        "text_color": config.get_chat_text_color(),
        "text_shadow_color": config.get_chat_text_shadow_color(),
        "text_shadow_size": config.get_chat_text_shadow_size(),
        "overlay_width": config.get_chat_overlay_width(),
        "overlay_height": config.get_chat_overlay_height(),
        "position": config.get_chat_position(),
        "padding": config.get_chat_padding(),
        "message_duration": config.get_chat_message_duration(),
        "keep_chat_overlay": config.get_keep_chat_overlay()
    }
    
    return {
        "status": STATUS_SUCCESS,
        "config": chat_config
    }, HTTP_OK


@chat_config_bp.route("/channels/<channel_name>/config/chat", methods=['PUT'])
@require_auth
async def update_chat_config(channel_name: str):
    """Update chat overlay configuration for a channel"""
    channel_name = channel_name.lower()
    
    channel = await TwitchChannel.get(login=channel_name)
    if not channel:
        return {
            "status": STATUS_ERROR,
            "message": "Channel does not exist in database"
        }, HTTP_NOT_FOUND
    
    # Parse JSON body (required for PUT)
    data, error_response, status_code = await parse_json_body(required=True)
    if error_response:
        return error_response, status_code
    
    # Validate chat configuration data
    error_response, status_code = validate_chat_config(data)
    if error_response:
        return error_response, status_code
    
    # Update channel configuration
    config = await channel.get_config()
    config_updated = False
    updated_fields = []
    
    # Map API field names to database field names
    field_mapping = {
        'font_family': 'chat_font_family',
        'font_size': 'chat_font_size',
        'font_style': 'chat_font_style',
        'font_weight': 'chat_font_weight',
        'text_color': 'chat_text_color',
        'text_shadow_color': 'chat_text_shadow_color',
        'text_shadow_size': 'chat_text_shadow_size',
        'overlay_width': 'chat_overlay_width',
        'overlay_height': 'chat_overlay_height',
        'position': 'chat_position',
        'padding': 'chat_padding',
        'message_duration': 'chat_message_duration',
        'keep_chat_overlay': 'keep_chat_overlay'
    }
    
    # Update each provided field
    for api_field, db_field in field_mapping.items():
        if api_field in data:
            setattr(config, db_field, data[api_field])
            config_updated = True
            updated_fields.append(api_field)
    
    if config_updated:
        await config.save()
        return {
            "status": STATUS_SUCCESS,
            "message": f"Updated {', '.join(updated_fields)}",
            "updated_fields": updated_fields
        }, HTTP_OK
    else:
        return {
            "status": STATUS_ERROR,
            "message": "No valid configuration parameters provided"
        }, HTTP_BAD_REQUEST


@chat_config_bp.route("/channels/<channel_name>/config/chat/reset", methods=['POST'])
@require_auth
async def reset_chat_config(channel_name: str):
    """Reset chat overlay configuration to defaults for a channel"""
    channel_name = channel_name.lower()
    
    channel = await TwitchChannel.get(login=channel_name)
    if not channel:
        return {
            "status": STATUS_ERROR,
            "message": "Channel does not exist in database"
        }, HTTP_NOT_FOUND
    
    # Reset all chat configuration fields to None (which will use defaults)
    config = await channel.get_config()
    
    config.chat_font_family = None
    config.chat_font_size = None
    config.chat_font_style = None
    config.chat_font_weight = None
    config.chat_text_color = None
    config.chat_text_shadow_color = None
    config.chat_text_shadow_size = None
    config.chat_overlay_width = None
    config.chat_overlay_height = None
    config.chat_position = None
    config.chat_padding = None
    config.chat_message_duration = None
    config.keep_chat_overlay = None
    
    await config.save()
    
    # Return the effective configuration after reset
    chat_config = {
        "font_family": config.get_chat_font_family(),
        "font_size": config.get_chat_font_size(),
        "font_style": config.get_chat_font_style(),
        "font_weight": config.get_chat_font_weight(),
        "text_color": config.get_chat_text_color(),
        "text_shadow_color": config.get_chat_text_shadow_color(),
        "text_shadow_size": config.get_chat_text_shadow_size(),
        "overlay_width": config.get_chat_overlay_width(),
        "overlay_height": config.get_chat_overlay_height(),
        "position": config.get_chat_position(),
        "padding": config.get_chat_padding(),
        "message_duration": config.get_chat_message_duration(),
        "keep_chat_overlay": config.get_keep_chat_overlay()
    }
    
    return {
        "status": STATUS_SUCCESS,
        "message": "Chat configuration reset to defaults",
        "config": chat_config
    }, HTTP_OK