# Compatibility matrix

The 0.1.0 contract covers Python 3.11+, FWS/CWS embedded SWF extraction, and local Windows development. Core extraction is designed to be portable; render support is only claimed on an OS/Chromium/Ruffle combination after its smoke test passes.

Known limits:

- ZWS/LZMA is detected and rejected with a specific message.
- Browser renders are visual-only unless audio is provided by another workflow.
- Captivate content requiring unavailable network resources, external JavaScript, or user interaction may not render correctly.
- AI provider capabilities vary; compatible base URLs must support the requested transcription, vision, and text operations.

The manual Windows smoke test used the official `nightly-2026-09-20` self-hosted bundle from the Ruffle releases page. The downloaded archive SHA-256 was `833BB4FE7DC672BDFF3D65A8AB84E035C68F949EAE03D2FB8193E4101535D1BC`; the archive stayed outside this repository. Re-run the smoke test when changing the Ruffle asset or browser version.
