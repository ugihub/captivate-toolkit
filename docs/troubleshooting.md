# Troubleshooting

Run `captivate doctor` first. Missing `ffmpeg` or `ffprobe` means extraction can still work, but render and analysis cannot. Missing Playwright Chromium affects rendering only. A missing `ruffle.js` means the selected Ruffle directory is incomplete or points to the wrong level.

If a render times out, try `--headed`, inspect the generated job directory, and verify that the SWF opens in the pinned Ruffle build. If analysis fails, preserve `vision_notes.txt` and `transcript.txt` when present; the provider error should identify the failed stage without exposing a key.

