from quart import Blueprint, Quart, request, current_app
from os import environ
from vodloader.vodloader import subscribe, unsubscribe
from vodloader.models import TwitchChannel
from vodloader.chat import bot
from vodloader import config
import logging


api = Blueprint('api', __name__)
logger = logging.getLogger('vodloader.api')


@api.route("/channel/<name>", methods=['POST'])
async def add_channel(name: str):

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

        if not channel.active:
            await channel.activate()
            bot.join_channel(channel)
            await subscribe(channel)
        
        # Update config if parameters are specified
        if 'quality' in request.args or 'delete_original_video' in request.args:
            config = await channel.get_config()
            if 'quality' in request.args:
                config.quality = quality
            if 'delete_original_video' in request.args:
                config.delete_original_video = delete_original_video
            await config.save()

    else:

        channel = await TwitchChannel.create_with_config(name, quality=quality, delete_original_video=delete_original_video)

        if not channel:
            return "Channel does not exist on Twitch", 400
        
        bot.join_channel(channel)
        await subscribe(channel)

    return"success",  200


@api.route("/channel/<name>", methods=['DELETE'])
async def delete_channel(name: str):
    
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
