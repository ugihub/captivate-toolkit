# Configuration

The CLI reads an explicitly selected `--env-file`, then process environment variables override values from that file. Importing the package does not load `.env` or mutate the process environment.

Supported keys are `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `TRANSCRIPTION_MODEL`, `VISION_MODEL`, and `TEXT_MODEL`. The key is required only for `analyze` or `run --analyze`. `TEXT_MODEL` falls back to `VISION_MODEL` when omitted. URLs with embedded credentials are rejected.

