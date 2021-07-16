from vodloader_config import vodloader_config
from vodloader import vodloader
from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from streamlink import Streamlink
import sys
import os
import logging
import logging.handlers
import ssl
import time
import pytz
import argparse


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
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    sl_logger = logging.getLogger()
    for handler in sl_logger.handlers:
        sl_logger.removeHandler(handler)
    sl_logger.addHandler(file_handler)
    sl_logger.addHandler(stream_handler)
    logging.getLoggerClass()
    return logger

def setup_streamlink():
    return Streamlink()

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
    args = parse_args()
    logger = setup_logger('vodloader', debug=args.debug)
    logger.info(f'Loading configuration from {args.config}')
    config = load_config(args.config)
    logger.info(f'Logging into Twitch and initiating webhook')
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_webhook(config['twitch']['webhook']['host'], config['twitch']['webhook']['port'], config['twitch']['client_id'], config['twitch']['webhook']['ssl_cert'], config['twitch']['webhook']['ssl_key'], twitch)
    logger.info(f'Initiating vodloaders')
    sl = setup_streamlink()
    vodloaders = []
    for channel in config['twitch']['channels']:
        vodloaders.append(vodloader(sl, channel, twitch, hook, config['twitch']['channels'][channel], config['youtube']['json'], config['download']['directory'], config['download']['keep'], config['youtube']['upload'], config['youtube']['sort'], config['download']['quota_pause'], pytz.timezone(config['twitch']['channels'][channel]['timezone'])))
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