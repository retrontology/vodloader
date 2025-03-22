from vodloader.database import *
from vodloader.util import *
from vodloader.models import SingleModel
from twitchAPI.twitch import Twitch


class TwitchClient(SingleModel):

    table_name = 'twitch_client'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            client_id VARCHAR(30) NOT NULL,
            client_secret VARCHAR(30) NOT NULL,
            PRIMARY KEY (client_id)
        );
        """

    client_id: str
    client_secret: str

    def __init__(
            self,
            client_id: str,
            client_secret: str
    ) -> None:
        
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
    
    @classmethod
    async def set_client(cls, client_id:str, client_secret:str) -> None:
        client = cls(client_id, client_secret)
        await client.save()
    
    @classmethod
    async def get_client(cls) -> tuple[str, str]|None:
        client = await cls.get()
        if client:
            return (client.client_id, client.client_secret)
        else:
            return None

    @classmethod
    async def get_twitch(cls) -> Twitch:
        client = await cls.get_client()
        twitch = await Twitch(*client)
        return twitch

