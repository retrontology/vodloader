from quart import Blueprint, Quart, request, current_app
from os import environ
from vodloader.models import TwitchClient
from twitchAPI.helper import first


api = Blueprint('api', __name__)


@api.route("/channel", methods=['POST'])
async def add_channel():

    try:
        data = await request.get_json()

        if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
            return 403

        if 'channel' not in data :
            return 'The "channel" field is required', 400
        else:
            channel_name = data['channel']

        if 'quality' in data:
            quality = data['quality']
        else:
            quality = 'best'

        twitch = await TwitchClient.get_twitch()
        channel = await first(twitch.get_users(logins=[channel_name]))

    except Exception as e:
        return 500
    
    return 200


@api.route("/channel/<channel>", methods=['DELETE'])
async def delete_channel(channel: str):

    if 'secret' not in request.headers or request.headers['secret'] != current_app.secret_key:
        return 'Get outta here ya bum', 403
    
    channel = channel.lower()
    vodloader: VODLoader = current_app.config['vodloader']
    try:
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
