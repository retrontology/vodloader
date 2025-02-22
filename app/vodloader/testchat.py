from .chat import *
from .run import setup_logger
import logging

logget = setup_logger(logging.DEBUG)
chat = Bot()

def welcome_callback(conn=None, event=None):
    #chat.join_channel('lronhoyabembeh')
    chat.join_channel('iodiopt')

def on_clearmsg(conn: irc.client.ServerConnection = None, event: irc.client.Event = None) -> None:
    print(event)

def on_clearchat(conn: irc.client.ServerConnection = None, event: irc.client.Event = None) -> None:
    print(event)

def main():
    chat.welcome_callback = welcome_callback
    chat.on_clearmsg = on_clearmsg
    chat.on_clearchat = on_clearchat
    chat.start()

if __name__ == '__main__':
    main()
