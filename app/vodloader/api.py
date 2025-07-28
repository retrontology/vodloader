from quart import Blueprint, Quart, request, current_app
from os import environ
from vodloader.vodloader import subscribe, unsubscribe
from vodloader.models import TwitchChannel
from vodloader.chat import bot
from vodloader import config
import logging


api = Blueprint('api', __name__)
logger = logging.getLogger('vodloader.api')


@api.route("/channel/<n>", methods=['POST'])
async def add_channel(name: str):
    """Add/activate a channel with initial configuration"""

    if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
        return "Unauthorized", 403

    name = name.lower()

    if 'quality' in request.args:
        quality = request.args['quality']
    else:
        quality = 'best'
    
    if 'delete_original_video' in request.args:
        delete_original_video = request.args['delete_original_video'].lower() in ('true', '1', 'yes')
    else:
        delete_original_video = False

    channel = await TwitchChannel.get(login=name)

    if channel:
        # Channel exists, just activate it if needed
        if not channel.active:
            await channel.activate()
            bot.join_channel(channel)
            await subscribe(channel)
        else:
            return "Channel already active", 200

    else:
        # Create new channel with config
        channel = await TwitchChannel.create_with_config(name, quality=quality, delete_original_video=delete_original_video)

        if not channel:
            return "Channel does not exist on Twitch", 400
        
        bot.join_channel(channel)
        await subscribe(channel)

    return "success", 200


@api.route("/channel/<n>", methods=['PUT'])
async def update_channel(name: str):
    """Update channel configuration"""

    if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
        return "Unauthorized", 403

    name = name.lower()

    channel = await TwitchChannel.get(login=name)

    if not channel:
        return "Channel does not exist in database", 404

    # Parse parameters
    config_updated = False
    config = await channel.get_config()

    if 'quality' in request.args:
        config.quality = request.args['quality']
        config_updated = True

    if 'delete_original_video' in request.args:
        config.delete_original_video = request.args['delete_original_video'].lower() in ('true', '1', 'yes')
        config_updated = True

    if config_updated:
        await config.save()
        return "success", 200
    else:
        return "No configuration parameters provided", 400


@api.route("/channel/<n>", methods=['DELETE'])
async def delete_channel(name: str):
    """Deactivate a channel"""
    
    if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
        return "Unauthorized", 403
    
    name = name.lower()

    channel = await TwitchChannel.get(login=name)

    if not channel:
        return "Channel does not exist in database", 403
    
    if channel.active:
        await channel.deactivate()
        bot.leave_channel(channel)
        await unsubscribe(channel)

    return "success", 200


@api.route("/channels", methods=['GET'])
async def get_channels():
    """Get list of all channels"""

    output = []
    
    if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
        return "Unauthorized", 403

    channels = await TwitchChannel.all()
    output = {
        'channels': [
            x.login for x in channels
        ]
    }

    return output, 200


def create_api() -> Quart:
    app = Quart(__name__)
    if not config.API_KEY:
        raise RuntimeError('API_KEY must be specified')
    app.secret_key = config.API_KEY
    app.register_blueprint(api)
    return app