# Video Uniqueizer Operations

Application directory:

```bash
/opt/video-uniqueizer
```

Data directory:

```bash
/opt/video-uniqueizer-data
```

## Status

```bash
systemctl is-active video-uniqueizer-bot video-uniqueizer-worker redis-server
systemctl status video-uniqueizer-bot video-uniqueizer-worker --no-pager
redis-cli llen uniqueizer:jobs
```

## Logs

```bash
journalctl -u video-uniqueizer-bot -f
journalctl -u video-uniqueizer-worker -f
journalctl -u video-uniqueizer-bot -u video-uniqueizer-worker --no-pager -n 120
```

## Restart

```bash
systemctl restart video-uniqueizer-bot video-uniqueizer-worker
```

## Current Safe Starter Settings

```text
COPIES_COUNT=10
WORKER_COUNT=3
FFMPEG_THREADS=2
MAX_ACTIVE_JOBS_PER_USER=3
ALLOW_ALL_USERS=1
USE_GPU=0
MAX_VIDEO_MB=19
SEND_RESULTS_AS_DOCUMENT=1
```

## Tune Worker Count

Edit:

```bash
nano /opt/video-uniqueizer/.env
```

Then restart:

```bash
systemctl restart video-uniqueizer-bot video-uniqueizer-worker
```

For the Ryzen 7 9700X server, start at `WORKER_COUNT=3`.
If real videos process smoothly and CPU/load stay reasonable, try `WORKER_COUNT=4`.

## Smoke Test Result

2026-08-24: Codex sent a 2-second synthetic video to the bot.
The service returned 10 videos and finished with `completed=10; errors=0`.

Real benchmark is still required with normal user videos.

## Telegram File Size Note

The production bot currently uses the regular Telegram Bot API.
Keep input videos under `19 MB` for reliable downloads. Generated results are
encoded toward a `47 MB` target and sent as Telegram documents. Larger source
uploads require a self-hosted Telegram Bot API server or an MTProto intake
service; changing the environment variable alone cannot bypass Telegram's
cloud `getFile` limit.

The render uses a 1080x1920 canvas, a 540x960 source panel, a generated
rights-safe motion loop on the other panel, randomized left/right placement,
random horizontal mirroring of the satisfying panel, and metadata removal.
The motion pack is generated from FFmpeg primitives, so it is reproducible
and does not contain third-party footage.

Users must choose `standard` or `satisfying` from inline bot buttons before
each upload. The standard mode renders the source full-frame; satisfying mode
uses the split layout with a project-owned source bank. Keep project media
outside the public repository and record its provenance in a local manifest.

Results are sent as Telegram documents by default. This preserves the generated
MP4 file more reliably than the in-chat video preview path.
