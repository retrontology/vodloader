# Vodloader (app)

Python application that captures Twitch streams (upload to YouTube is not implemented yet). Runs as the main service behind the Docker stack; see the [repository root README](../README.md) for deployment.

## Requirements

- Python 3.8+
- [Playwright](https://playwright.dev/python/) browsers (for chat rendering): `playwright install` after installing dependencies

## Local development

From the `app/` directory:

```bash
python -m venv .venv
source .venv/bin/activate   # or `.venv\Scripts\activate` on Windows
pip install -e .
playwright install
```

Create a `.env` (or copy from repo root `example.env`) and set at least:

- `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` – Twitch app credentials
- `WEBHOOK_HOST` – public hostname for Twitch webhooks (e.g. your domain)
- `API_KEY` – secret used to authenticate API requests

Run the app:

```bash
python -m vodloader.run
```

Optional: `-d` / `--debug` for debug logging.

## Configuration (environment)

| Variable | Description | Default |
|----------|-------------|---------|
| `DOWNLOAD_DIR` | Directory for captured VODs | `videos` |
| `TWITCH_CLIENT_ID` | Twitch application client ID | — |
| `TWITCH_CLIENT_SECRET` | Twitch application client secret | — |
| `WEBHOOK_HOST` | Public host for Twitch webhook callbacks | — |
| `WEBHOOK_PORT` | Port Twitch webhooks are served on (e.g. behind proxy) | `8000` |
| `API_HOST` | Bind address for the API server | `0.0.0.0` |
| `API_PORT` | API server port (internal; nginx proxies to this) | `8001` |
| `API_KEY` | API authentication secret | — |
| `DB_TYPE` | Database type: `sqlite` or `mysql` | `sqlite` |
| `DB_PATH` | SQLite database file path | `test.sqlite` |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_SCHEMA` | MySQL connection (when `DB_TYPE=mysql`) | — |

## Project layout

```
app/
├── vodloader/
│   ├── run.py           # Entry point: API, webhooks, chat bot, transcoding
│   ├── config.py        # Environment/config loading
│   ├── database.py      # DB access layer
│   ├── twitch.py        # Twitch API and webhook handling
│   ├── vodloader.py     # Stream subscription and download
│   ├── chat.py          # Twitch chat bot
│   ├── api/             # Quart REST API (channels, chat config)
│   ├── models/          # Data models (channels, videos, etc.)
│   ├── post/            # Post-processing: transcoding, chat overlay (YouTube upload not implemented)
│   │   ├── transcoding.py
│   │   ├── chat_video.py
│   │   ├── chat/        # Chat renderer (Playwright)
│   │   └── ...
│   └── ffmpeg/          # FFmpeg helpers
├── pyproject.toml
├── __about__.py         # Version
└── README.md            # This file
```

- **API** (`vodloader.api`): Quart app; channel management and chat overlay config. Served by Hypercorn on `API_HOST:API_PORT`; in Docker, nginx proxies external traffic to it.
- **Twitch**: App auth, webhook server for stream online/offline, and IRC-style chat bot for live chat.
- **Post**: After a stream is captured, videos are queued for transcoding and optional chat overlay rendering. Upload to YouTube is not implemented yet.

## API

The REST API is served on `API_HOST:API_PORT` (in Docker, nginx proxies port 8000 to it). All endpoints require authentication via the `secret` header set to your `API_KEY` value.

Responses are JSON with a `status` field: `"success"`, `"error"`, or `"info"`. Errors include a `message`; success responses may include `message`, `channels`, `config`, or `updated_fields`.

### Channels

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/channels` | List all channels with config (`login`, `name`, `active`, `quality`, `delete_original_video`). |
| `POST` | `/channel/<name>` | Add or activate a channel. Body (optional): `quality`, `delete_original_video`. |
| `PUT` | `/channel/<name>` | Update channel config. Body: any of `quality`, `delete_original_video`. |
| `DELETE` | `/channel/<name>` | Deactivate a channel. |

`<name>` is the Twitch channel login (case-insensitive). Valid `quality`: `best`, `worst`, `source`, `1080p`, `720p`, `480p`, `360p`, `160p`. `delete_original_video` is a boolean.

### Chat overlay config

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/channels/<channel_name>/config/chat` | Get chat overlay config for the channel. |
| `PUT` | `/channels/<channel_name>/config/chat` | Update chat overlay config. Body: any of the fields below. |
| `POST` | `/channels/<channel_name>/config/chat/reset` | Reset chat overlay config to defaults. |

**PUT body fields** (all optional): `font_family` (string, max 100 chars), `font_size` (int, 8–72), `font_style` (`normal`, `italic`, `oblique`), `font_weight` (`normal`, `bold`, or `100`–`900`), `text_color`, `text_shadow_color` (hex e.g. `#ffffff`), `text_shadow_size` (int, 0–10), `overlay_width`, `overlay_height` (int, 100–3840), `position` (`top-left`, `top-right`, `bottom-left`, `bottom-right`, `left`, `right`), `padding` (int, 0–200), `message_duration` (number, 5–300 seconds), `keep_chat_overlay` (boolean).

## Running

- **Production (Docker):** The image runs `python -m vodloader.run`. Use the root `compose.yml` and `.env` at repo root.
- **Local:** Same command after `pip install -e .` and configuring `.env` in `app/` (or env vars). Ensure `WEBHOOK_HOST` is reachable by Twitch.
