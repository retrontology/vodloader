from vodloader_config import vodloader_config
from vodloader import vodloader
from twitchAPI import Twitch, EventSub
from streamlink import Streamlink
import sys
import os
import logging
import logging.handlers
import time
import pytz
import argparse

DEFAULT_RETRIES = 10

def parse_args():
    parser = argparse.ArgumentParser(prog='vodloader', description='Automate uploading Twitch streams to YouTube')
    parser.add_argument('-c', '--config', default=os.path.join(os.path.dirname('__file__'), 'config.yaml'), metavar='config.yaml')
    parser.add_argument('-d', '--debug', action='store_true')
    return parser.parse_args()

def load_config(filename):
    config = vodloader_config(filename)
    if not config['download']['directory'] or config['download']['directory'] == "":
        config['download']['directory'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'videos')
    if not os.path.isdir(config['download']['directory']):
        os.mkdir(config['download']['directory'])
    for channel in config['twitch']['channels']:
        if not 'timezone' in config['twitch']['channels'][channel] or config['twitch']['channels'][channel]['timezone'] == '':
            config['twitch']['channels'][channel]['timezone'] ='UTC'
        if not config['twitch']['channels'][channel]['timezone'] in pytz.all_timezones:
            sys.exit(f'timezone entry for {channel} in {filename} is invalid!')
    if not 'sort' in config['youtube']:
        config['youtube']['sort'] = True
    config.save()
    return config

def setup_logger(logname, logpath="", debug=False):
    if not logpath or logpath == "":
        logpath = os.path.join(os.path.dirname(__file__), 'logs')
    else:
        logpath = os.path.abspath(logpath)
    if not os.path.exists(logpath):
        os.mkdir(logpath)
    logger = logging.getLogger(logname)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.handlers.TimedRotatingFileHandler(os.path.join(logpath, logname), when='midnight')
    stream_handler = logging.StreamHandler()
    form = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(form)
    stream_handler.setFormatter(form)
    if debug:
        file_handler.setLevel(logging.DEBUG)
        stream_handler.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
        stream_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    twitchapi_logger = logging.getLogger('twitchAPI')
    twitchapi_logger.addHandler(file_handler)
    twitchapi_logger.addHandler(stream_handler)
    return logger
    
def setup_streamlink():
    return Streamlink()

def setup_twitch(client_id, client_secret):
    twitch = Twitch(client_id, client_secret)
    twitch.authenticate_app([])
    return twitch

def setup_eventsub(host, client_id, twitch:Twitch):
    webhook_retries = 0
    while True:
        try:
            hook = EventSub('https://' + host + ":443", client_id, 80, twitch)
            break
        except Exception as e:
            logger.error(e)
            if webhook_retries > DEFAULT_RETRIES:
                raise RetryExceeded()
            else:
                time.sleep(1)
                webhook_retries += 1
    hook.unsubscribe_all()
    hook.start()
    return hook

def renew_webhook(webhook:EventSub, twitch:Twitch, vodloaders):
    host = webhook._host
    port = webhook._port
    client_id = twitch.app_id
    for vl in vodloaders:
        vl.webhook_unsubscribe()
    webhook.stop()
    webhook = setup_eventsub(host, client_id, twitch)
    for vl in vodloaders:
        vl.webhook = webhook
        vl.webhook_subscribe()

def main():
    logger.info(f'Loading configuration from {args.config}')
    config = load_config(args.config)
    logger.info(f'Logging into Twitch and initiating webhook')
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_eventsub(config['twitch']['webhook']['host'], config['twitch']['client_id'], twitch)
    logger.info(f'Initiating vodloaders')
    sl = setup_streamlink()
    vodloaders = []
    for channel in config['twitch']['channels']:
        vodloaders.append(
            vodloader(
                sl,
                channel,
                twitch,
                hook,
                config['twitch']['channels'][channel],
                config['youtube']['json'],
                config['download']['directory'],
                config['download']['keep'], config['youtube']['upload'],
                config['youtube']['sort'], config['download']['quota_pause'],
                pytz.timezone(config['twitch']['channels'][channel]['timezone'])
            )
        )
    try:
        while True:
            time.sleep(600)
    except:
        logger.info(f'Shutting down')
        for v in vodloaders:
            v.end = True
            v.webhook_unsubscribe()
        hook.stop()
        
class RetryExceeded(Exception): pass

if __name__ == '__main__':
    args = parse_args()
    logger = setup_logger('vodloader', debug=args.debug)
    main()