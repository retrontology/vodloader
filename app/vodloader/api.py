from quart import Blueprint, Quart, request, current_app
from os import environ
from vodloader.vodloader import subscribe, unsubscribe
from vodloader.models import TwitchChannel
import logging


api = Blueprint('api', __name__)
logger = logging.getLogger('vodloader.api')


@api.route("/channel/<name>", methods=['POST'])
async def add_channel(name: str):

    try:

        if 'quality' in request.args:
            quality = request.args['quality']
        else:
            quality = 'best'

        channel = await TwitchChannel.from_name(name, quality)

        if not channel:
            return "channel does not exist", 403
        
        await channel.save()
        await subscribe(channel)
        
        return 200

    except Exception as e:
        return 500


@api.route("/channel/<name>", methods=['DELETE'])
async def delete_channel(name: str):
    
    try:

        if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
            return 403
        
        

        await vodloader.remove_channel(channel)
    except ChannelNotAdded as e:
        return {
            'result': 'failure',
            'reason': f'The channel "{channel}" has not been added to VODLoader'
        }
    return {'result': 'success'}


@api.route("/channels", methods=['GET'])
async def get_channels():
    
    if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
        return 'Get outta here ya bum', 403

    vodloader: VODLoader = current_app.config['vodloader']
    channels = {
        'channels': [
            x for x in vodloader.channels
        ]
    }
    return channels


def create_api() -> Quart:
    app = Quart(__name__)
    if 'API_SECRET_KEY' not in environ or not environ['API_SECRET_KEY']:
        raise RuntimeError('API_SECRET_KEY must be specified either as an environment variable or in the .env file')
    app.secret_key = environ['API_SECRET_KEY']
    app.register_blueprint(api)
    return app
