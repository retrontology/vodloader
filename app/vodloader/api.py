from quart import Blueprint, Quart, request, current_app
from os import environ
from vodloader.vodloader import subscribe, unsubscribe
from vodloader.models import TwitchChannel
from vodloader import config
import logging


api = Blueprint('api', __name__)
logger = logging.getLogger('vodloader.api')


@api.route("/channel/<name>", methods=['POST'])
async def add_channel(name: str):

    try:

        if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
            return "Unauthorized", 403

        name = name.lower()

        if 'quality' in request.args:
            quality = request.args['quality']
        else:
            quality = 'best'

        channel = await TwitchChannel.get(login=name)

        if channel:

            if not channel.active:
                await channel.activate()
                await subscribe(channel)

        else:

            channel = await TwitchChannel.from_name(name, quality)

            if not channel:
                return "Channel does not exist on Twitch", 400

            await channel.save()
            await subscribe(channel)

    except Exception as e:
        return "Internal error", 500
    
    finally:
        return"success",  200


@api.route("/channel/<name>", methods=['DELETE'])
async def delete_channel(name: str):
    
    try:

        if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
            return "Unauthorized", 403

        channel = await TwitchChannel.get(login=name)

        if not channel:
            return "Channel does not exist in database", 403
        
        if channel.active:
            await channel.deactivate()
            await unsubscribe(channel)
       
    except Exception as e:
        return "Internal error", 500
    
    finally:
        return "success", 200


@api.route("/channels", methods=['GET'])
async def get_channels():
    
    try:

        if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
            return "Unauthorized", 403

        channels = await TwitchChannel.all()
        output = {
            'channels': [
                x for x in channels
            ]
        }
    
    except Exception as e:
        return "Internal error", 500

    finally:
        return output, 200


def create_api() -> Quart:
    app = Quart(__name__)
    if not config.API_KEY:
        raise RuntimeError('API_KEY must be specified')
    app.secret_key = config.API_KEY
    app.register_blueprint(api)
    return app
