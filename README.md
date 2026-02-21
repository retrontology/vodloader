# Vodloader

Captures Twitch streams (upload to YouTube not implemented yet). Runs as a Docker stack: the vodloader app plus nginx as a reverse proxy.

## Quick start

1. Clone the repo.
2. Copy `example.env` to `.env` and set your values (Twitch credentials, `WEBHOOK_HOST`, `API_KEY`, etc.). See [app/README.md](app/README.md) for all environment variables.
3. Optionally edit `compose.yml` to change the videos volume (default: `/mnt/media/Capture/vodloader`).
4. Run:

   ```bash
   docker compose up -d
   ```

The API and web UI are served on **port 8000** (nginx). See [app/README.md](app/README.md#api) for API endpoint documentation. Database and captured videos are stored in `./database` and the mounted videos volume respectively.

### NVIDIA GPU

The stack is configured to pass all NVIDIA GPUs into the vodloader container (`deploy.resources.reservations.devices`). Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on the host so Docker can use the GPU. The vodloader service also uses `ipc: host` and `init: true` (recommended for Playwright Chromium). The app currently uses software encoding (libx264); to use hardware encoding (e.g. `h264_nvenc`) you would need to configure the transcoding pipeline accordingly.

## Repository layout

| Path | Description |
|------|-------------|
| `app/` | Main Python application. See [app/README.md](app/README.md) for setup, config, and development. |
| `nginx/` | Nginx reverse proxy; forwards traffic to the app. |
| `compose.yml` | Docker Compose stack (vodloader + nginx). |
| `example.env` | Example environment file; copy to `.env` and configure. |

## License

See [LICENSE](LICENSE).
