# Video Uniqueizer Service

Production-oriented Telegram bot package for a video uniqueizer.

This repository contains the application code and deployment scaffolding.
User media, Telegram credentials, generated packs, and runtime data are
intentionally excluded.

## What It Runs

- `bot`: receives Telegram videos, downloads them, puts jobs into Redis.
- `worker`: takes jobs from Redis, renders copies through `ffmpeg`, sends files back.
- `redis`: durable queue state.

The satisfying mode uses a local source bank, randomly places the source on
the left or right panel, and randomly mirrors the satisfying panel. The
source bank is supplied separately by the operator and is never committed to
this repository.

## Run Without Telegram

The rendering core can run as a local CLI. Telegram, Redis, and a bot token are
not needed for this path.

```bash
python -m uniqueizer.cli ./input.mp4 \
  --mode standard \
  --copies 3 \
  --output ./output
```

For satisfying mode, provide a local asset directory containing the generated
background pack and a project-owned `curated_source_bank`:

```bash
python scripts/build_assets.py ./assets
python -m uniqueizer.cli ./input.mp4 \
  --mode satisfying \
  --asset-dir ./assets \
  --copies 3 \
  --output ./output
```

Users choose a mode before each upload. Default access allows all Telegram
users, but limits active jobs per user.

## Server Start

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f
```

Required `.env` value:

```bash
BOT_TOKEN=...
```

Recommended first server settings:

```bash
COPIES_COUNT=10
WORKER_COUNT=4
FFMPEG_THREADS=2
MAX_ACTIVE_JOBS_PER_USER=3
ALLOW_ALL_USERS=1
USE_GPU=0
```

For the Xeon E5-2680v2 starter server, begin with `WORKER_COUNT=3` or `4`.
Increase only after real benchmark videos confirm the CPU load is stable.

## Operations

```bash
docker compose ps
docker compose logs -f bot
docker compose logs -f worker
docker compose restart
docker compose down
```

## Security

- Do not put the Telegram token in source code.
- Store the token only in `.env` on the server.
- Change any password that was visible in screenshots.
- Prefer SSH keys after initial setup.
