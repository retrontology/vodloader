from vodloader_config import vodloader_config
from vodloader import vodloader
from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
import sys
import os
import logging
import logging.handlers
import ssl
import time
import pytz

config_file = os.path.join(os.path.dirname('__file__'), 'config.yaml')

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
            sys.exit(f'timezone entry for {channel} in {config_file} is invalid!')
    config.save()
    return config

def setup_logger(logname, logpath=""):
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
    file_handler.setLevel(logging.INFO)
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

def setup_twitch(client_id, client_secret):
    twitch = Twitch(client_id, client_secret)
    twitch.authenticate_app([])
    return twitch

def setup_webhook(host, port, client_id, cert, key, twitch):
    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile=cert, keyfile=key)
    hook = TwitchWebHook('https://' + host + ":" + str(port), client_id, port, ssl_context=ssl_context)
    hook.authenticate(twitch)
    hook.start()
    return hook

def main():
    logger = setup_logger('vodloader')
    logger.info(f'Loading configuration from {config_file}')
    config = load_config(config_file)
    logger.info(f'Logging into Twitch and initiating webhook')
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_webhook(config['twitch']['webhook']['host'], config['twitch']['webhook']['port'], config['twitch']['client_id'], config['twitch']['webhook']['ssl_cert'], config['twitch']['webhook']['ssl_key'], twitch)
    logger.info(f'Initiating vodloaders')
    vodloaders = []
    for channel in config['twitch']['channels']:
        vodloaders.append(vodloader(channel, twitch, hook, config['twitch']['channels'][channel], config['youtube']['json'], config['download']['directory'], config['download']['keep'], config['youtube']['upload'], config['download']['quota_pause'], pytz.timezone(config['twitch']['channels'][channel]['timezone'])))
    try:
        while True:
            time.sleep(600)
    except:
        logger.info(f'Shutting down')
        for v in vodloaders:
            v.end = True
            v.webhook_unsubscribe()
        hook.stop()

if __name__ == '__main__':
    main()