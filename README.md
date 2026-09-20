# Captivate Toolkit

Captivate Toolkit extracts embedded FWS/CWS SWF files from legacy Adobe Captivate or Flash projector EXE files. It can optionally render a SWF through a local, pinned Ruffle build and analyze an existing MP4 with an OpenAI-compatible API.

The tool runs locally. Extraction and rendering do not require an API key. AI analysis is opt-in, uses the endpoint configured by the user, and may incur provider charges.

## Quickstart

Python 3.11 or newer is required. FFmpeg/ffprobe are required for media work. Rendering additionally requires a local Ruffle self-hosted build and Playwright Chromium.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
captivate doctor
captivate extract .\lesson.exe --out output
```

Install rendering support separately:

```powershell
python -m pip install -e ".[render]"
playwright install chromium
captivate render output\lesson\swf\main.swf --seconds 90 --ruffle-dir .\ruffle --out rendered
```

The `--ruffle-dir` directory must contain a tested self-hosted `ruffle.js` build and its companion assets. Keep the Ruffle version and checksum with your deployment documentation; this project does not download an unpinned CDN asset during a job.

## AI analysis

Copy `.env.example` to a private file and fill in the values supplied by your provider. The existing MVP names remain supported:

```powershell
python -m pip install -e ".[ai]"
captivate analyze .\lesson.mp4 --env-file .\.env --preset sap --language id --out analysis
```

The analysis command writes `vision_notes.txt`, `summary.md`, and `transcript.txt` when audio transcription succeeds. A video without an audio stream is reported as a skipped transcription stage. Input frames, audio, and text are sent only when the analysis command is explicitly invoked.

## Batch pipeline

```powershell
captivate run lesson-a.exe lesson-b.exe --out output
captivate run lesson.exe --seconds 90 --ruffle-dir .\ruffle --analyze --env-file .\.env
```

Each job has its own directory and `manifest.json`. A batch returns exit code `1` if any requested job or stage fails, even when another job succeeds. Existing output is never overwritten.

## Compatibility limits

Version 0.1.0 supports FWS and CWS SWF extraction. ZWS/LZMA, all Captivate versions, arbitrary interactive content, and audio capture from the browser render are outside the supported contract. The produced render is visual-only unless a separate media workflow supplies audio.

Ruffle and Adobe Captivate are separate projects with their own licenses. Review the licenses of Ruffle, FFmpeg, Chromium, and any supplied training content before redistribution. Do not commit `.env`, API keys, EXE files, MP4 files, SWF files, transcripts, or customer material.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
python -m build
```

See [docs/compatibility.md](docs/compatibility.md), [docs/configuration.md](docs/configuration.md), and [docs/troubleshooting.md](docs/troubleshooting.md) for operational details.

