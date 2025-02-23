from vodloader.database import *
from vodloader.util import *
from vodloader.models import BaseModel


class TwitchClient(BaseModel):

    table_name = 'twitch_client'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT NOT NULL UNIQUE,
            client_id VARCHAR(30) NOT NULL,
            client_secret VARCHAR(30) NOT NULL,
            PRIMARY KEY (id)
        );
        """

    id: int
    client_id: str
    client_secret: str

    def __init__(
            self,
            id: int|str,
            client_id: str,
            client_secret: str
    ) -> None:
        
        super().__init__()
        self.id = int(id)
        self.client_id = client_id
        self.client_secret = client_secret
    
    @classmethod
    async def set_client(cls, client_id:str, client_secret:str) -> None:
        client = cls(0, client_id, client_secret)
        await client.save()
    
    @classmethod
    async def get_client(self) -> tuple[str, str]|None:
        client = await self.get(id=0)
        if client:
            return (client.client_id, client.client_secret)
        else:
            return None
