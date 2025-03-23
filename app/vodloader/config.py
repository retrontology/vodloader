import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "videos"))
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST")
WEBHOOK_PORT = os.environ.get("WEBHOOK_PORT", "8000")
DB_TYPE = os.environ.get("DB_TYPE", "sqlite")
DB_PATH = os.environ.get("DB_PATH", "test.sqlite")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_SCHEMA = os.environ.get("DB_SCHEMA", "vodloader")
API_KEY = os.environ.get("API_KEY")


if not DOWNLOAD_DIR.exists():
    DOWNLOAD_DIR.mkdir()
