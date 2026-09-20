# Contributing

Create a focused branch from `feature/v0.1.0` or the current release line. Keep tests offline and never add customer EXE, MP4, SWF, transcript, API key, or private endpoint to a commit.

For behavior changes, write a failing regression test first, implement the smallest change, then run the full test and lint commands from the README. Changes to CLI flags, environment keys, exit codes, manifest schema, or supported formats require an entry in `CHANGELOG.md` and the relevant documentation.

