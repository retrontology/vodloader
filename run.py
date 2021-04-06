from vodloader_config import vodloader_config
from vodloader import vodloader
from webhook_ssl import proxy_request_handler
from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
from functools import partial
import sys
import os
import _thread
import logging
import logging.handlers
import http.server
import ssl
import time

config_file = os.path.join(os.path.dirname('__file__'), 'config.yaml')

def load_config(filename):
    config = vodloader_config(filename)
    if not config['download']['directory'] or config['download']['directory'] == "":
        config['download']['directory'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'videos')
    return config


def setup_logger(logname, logpath=""):
    if not logpath or logpath == "":
        logpath = os.path.join(os.path.dirname(__file__), 'logs')
    else:
        logpath = os.path.abspath(logpath)
    if not os.path.exists(logpath):
        os.mkdir(logpath)
    logger = logging.getLogger(logname)
    file_handler = logging.handlers.TimedRotatingFileHandler(os.path.join(logpath, logname), when='midnight')
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    stream_handler.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def setup_twitch(client_id, client_secret):
    twitch = Twitch(client_id, client_secret)
    twitch.authenticate_app([])
    return twitch


def setup_ssl_reverse_proxy(host, ssl_port, http_port, certfile):
    handler = partial(proxy_request_handler, http_port)
    httpd = http.server.HTTPServer((host, ssl_port), handler)
    httpd.socket = ssl.wrap_socket(httpd.socket, certfile=certfile, server_side=True)
    _thread.start_new_thread(httpd.serve_forever, ())
    return httpd


def setup_webhook(host, ssl_port, client_id, port, twitch):
    hook = TwitchWebHook('https://' + host + ":" + str(ssl_port), client_id, port)
    hook.authenticate(twitch) 
    hook.start()
    return hook


def main():
    logger = setup_logger('vodloader')
    logger.info(f'Loading configuration from {config_file}')
    config = load_config(config_file)
    logger.info(f'Setting up HTTPS server for reverse proxy to webhook')
    ssl_httpd = setup_ssl_reverse_proxy(config['twitch']['webhook']['host'], config['twitch']['webhook']['ssl_port'], config['twitch']['webhook']['port'], config['twitch']['webhook']['ssl_cert'])
    logger.info(f'Logging into Twitch and initiating webhook')
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_webhook(config['twitch']['webhook']['host'], config['twitch']['webhook']['ssl_port'], config['twitch']['client_id'], config['twitch']['webhook']['port'], twitch)
    logger.info(f'Initiating vodloaders')
    vodloaders = []
    for channel in config['twitch']['channels']:
        vodloaders.append(vodloader(config['twitch']['channels'][channel]['name'], twitch, hook, config['youtube']['json'], config['twitch']['channels'][channel]['youtube_param'], config['download']['directory']))
    try:
        while True:
            time.sleep(600)
    except:
        logger.info(f'Shutting down')
        for v in vodloaders:
            v.webhook_unsubscribe()
        hook.stop()
        ssl_httpd.shutdown()
        ssl_httpd.socket.close()


if __name__ == '__main__':
    main()