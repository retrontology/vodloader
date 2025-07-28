"""
Channel management API endpoints.
"""

from quart import Blueprint
from vodloader.vodloader import subscribe, unsubscribe
from vodloader.models import TwitchChannel
from vodloader.chat import bot

from .auth import require_auth
from .utils import parse_json_body
from .validation import validate_channel_config, validate_quality, validate_delete_original_video
from .constants import (
    STATUS_SUCCESS, STATUS_ERROR, STATUS_INFO,
    HTTP_OK, HTTP_CREATED, HTTP_BAD_REQUEST, HTTP_NOT_FOUND
)

channels_bp = Blueprint('channels', __name__)


@channels_bp.route("/channel/<name>", methods=['POST'])
@require_auth
async def add_channel(name: str):
    """Add/activate a channel with initial configuration"""
    name = name.lower()

    # Parse JSON body for configuration
    data, error_response, status_code = await parse_json_body()
    if error_response:
        return error_response, status_code

    # Extract configuration with defaults
    quality = data.get('quality', 'best')
    delete_original_video = data.get('delete_original_video', False)

    # Validate configuration
    error_response, status_code = validate_channel_config({
        'quality': quality,
        'delete_original_video': delete_original_video
    })
    if error_response:
        return error_response, status_code

    channel = await TwitchChannel.get(login=name)

    if channel:
        # Channel exists, just activate it if needed
        if not channel.active:
            await channel.activate()
            bot.join_channel(channel)
            await subscribe(channel)
            return {"status": STATUS_SUCCESS, "message": "Channel activated"}, HTTP_OK
        else:
            return {"status": STATUS_INFO, "message": "Channel already active"}, HTTP_OK

    else:
        # Create new channel with config
        channel = await TwitchChannel.create_with_config(
            name, 
            quality=quality, 
            delete_original_video=delete_original_video
        )

        if not channel:
            return {
                "status": STATUS_ERROR, 
                "message": "Channel does not exist on Twitch"
            }, HTTP_BAD_REQUEST
        
        bot.join_channel(channel)
        await subscribe(channel)
        return {
            "status": STATUS_SUCCESS, 
            "message": "Channel created and activated"
        }, HTTP_CREATED


@channels_bp.route("/channel/<name>", methods=['PUT'])
@require_auth
async def update_channel(name: str):
    """Update channel configuration"""
    name = name.lower()

    channel = await TwitchChannel.get(login=name)

    if not channel:
        return {
            "status": STATUS_ERROR, 
            "message": "Channel does not exist in database"
        }, HTTP_NOT_FOUND

    # Parse JSON body (required for PUT)
    data, error_response, status_code = await parse_json_body(required=True)
    if error_response:
        return error_response, status_code

    # Update channel configuration
    config = await channel.get_config()
    config_updated = False
    updated_fields = []

    # Update quality if provided
    if 'quality' in data:
        error_response, status_code = validate_quality(data['quality'])
        if error_response:
            return error_response, status_code
        
        config.quality = data['quality']
        config_updated = True
        updated_fields.append('quality')

    # Update delete_original_video if provided
    if 'delete_original_video' in data:
        error_response, status_code = validate_delete_original_video(data['delete_original_video'])
        if error_response:
            return error_response, status_code
        
        config.delete_original_video = data['delete_original_video']
        config_updated = True
        updated_fields.append('delete_original_video')

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


@channels_bp.route("/channel/<name>", methods=['DELETE'])
@require_auth
async def delete_channel(name: str):
    """Deactivate a channel"""
    name = name.lower()

    channel = await TwitchChannel.get(login=name)

    if not channel:
        return {
            "status": STATUS_ERROR, 
            "message": "Channel does not exist in database"
        }, HTTP_NOT_FOUND
    
    if channel.active:
        await channel.deactivate()
        bot.leave_channel(channel)
        await unsubscribe(channel)
        return {"status": STATUS_SUCCESS, "message": "Channel deactivated"}, HTTP_OK
    else:
        return {"status": STATUS_INFO, "message": "Channel already inactive"}, HTTP_OK


@channels_bp.route("/channels", methods=['GET'])
@require_auth
async def get_channels():
    """Get list of all channels with their configurations"""
    channels = await TwitchChannel.all()
    channel_list = []
    
    for channel in channels:
        try:
            config = await channel.get_config()
            channel_data = {
                'login': channel.login,
                'name': channel.name,
                'active': channel.active,
                'quality': config.quality,
                'delete_original_video': config.delete_original_video
            }
        except:
            # Fallback if config doesn't exist
            channel_data = {
                'login': channel.login,
                'name': channel.name,
                'active': channel.active,
                'quality': 'best',
                'delete_original_video': False
            }
        
        channel_list.append(channel_data)

    return {
        'status': STATUS_SUCCESS,
        'channels': channel_list,
        'count': len(channel_list)
    }, HTTP_OK