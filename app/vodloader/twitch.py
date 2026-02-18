from vodloader import config
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
import logging


logger = logging.getLogger('vodloader.twitch')
twitch = Twitch(config.TWITCH_CLIENT_ID, config.TWITCH_CLIENT_SECRET)
webhook = EventSubWebhook(f"https://{config.WEBHOOK_HOST}", config.WEBHOOK_PORT, twitch)
