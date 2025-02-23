from vodloader.models import BaseModel


class TwitchAuth(BaseModel):

    table_name = 'twitch_auth'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT NOT NULL UNIQUE,
            auth_token VARCHAR(30) DEFAULT NULL,
            refresh_token VARCHAR(50) DEFAULT NULL,
            PRIMARY KEY (id)
        );
        """

    id: int
    auth_token: str
    refresh_token: str

    def __init__(
            self,
            id: int|str,
            auth_token: str,
            refresh_token: str
    ) -> None:
        
        super().__init__()
        self.id = int(id)
        self.auth_token = auth_token
        self.refresh_token = refresh_token

    @classmethod
    async def set_auth(cls, auth_token:str, refresh_token:str) -> None:
        client = cls(0, auth_token, refresh_token)
        await client.save()
    
    @classmethod
    async def get_auth(self) -> tuple[str, str]|None:
        client = await self.get(id=0)
        if client:
            return (client.auth_token, client.refresh_token)
        else:
            return None
