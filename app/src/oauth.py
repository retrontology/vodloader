from twitchAPI.oauth import UserAuthenticator, UserAuthenticationStorageHelper
from twitchAPI.type import AuthScope
from twitchAPI.twitch import Twitch
from twitchAPI.helper import TWITCH_AUTH_BASE_URL
from .models import TwitchAuth
from typing import List, Tuple
import logging

TWITCHAPI_URL = 'http://localhost:17563'
VODLOADER_URL = 'http://localhost'

class DBUserAuthenticationStorageHelper(UserAuthenticationStorageHelper):

    def __init__(self,
                 twitch: 'Twitch',
                 scopes: List[AuthScope],
                 auth_base_url: str = TWITCH_AUTH_BASE_URL):
        self.twitch = twitch
        self.logger = logging.getLogger('vodloader.oauth.db_storage_helper')
        self._target_scopes = scopes
        self.auth_generator = self._default_auth_gen
        self.auth_base_url: str = auth_base_url
    
    async def _default_auth_gen(self, twitch: Twitch, scopes: List[AuthScope]) -> Tuple[str, str]:
        auth = UserAuthenticator(
            twitch,
            scopes,
            force_verify=False,
            url=VODLOADER_URL,
            auth_base_url=self.auth_base_url,
        )
        print(auth.return_auth_url())
        code = input('Enter the code: ')
        return await auth.authenticate(user_token=code)
    
    async def _update_stored_tokens(self, token: str, refresh_token: str):
        await TwitchAuth.set_auth(token, refresh_token)
        self.logger.info('user token got refreshed and stored')

    async def bind(self):

        self.twitch.user_auth_refresh_callback = self._update_stored_tokens
        needs_auth = True
        tokens = await TwitchAuth.get_auth()

        if not tokens or not all(tokens):
            self.logger.info('tokens not found in database, refreshing...')
        else:
            try:
                await self.twitch.set_user_authentication(tokens[0], self._target_scopes, tokens[1])
            except:
                self.logger.info('stored token invalid, refreshing...')
            else:
                needs_auth = False

        if needs_auth:
            token, refresh_token = await self.auth_generator(self.twitch, self._target_scopes)
            await TwitchAuth.set_auth(token, refresh_token)
            await self.twitch.set_user_authentication(token, self._target_scopes, refresh_token)