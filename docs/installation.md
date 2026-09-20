# Installation

Install from a checkout with Python 3.11 or newer:

```powershell
python -m pip install .
```

For AI or rendering support use extras: `python -m pip install ".[ai]"` and `python -m pip install ".[render]"`. Rendering also needs FFmpeg, ffprobe, Chromium installed by Playwright, and a local self-hosted Ruffle bundle. Run `captivate doctor --ruffle-dir .\ruffle` before a render job.

