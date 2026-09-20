"""Compatibility launcher for the v0.1.0 ``captivate`` CLI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from captivate_toolkit.cli import main


def _translate_legacy_args(argv: list[str]) -> list[str]:
    if not argv or argv[0].startswith("-"):
        return argv
    translated = ["run"]
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--render-seconds":
            translated.extend(["--seconds", argv[index + 1]])
            index += 2
        elif value == "--ruffle-url":
            raise SystemExit("--ruffle-url sudah tidak didukung; gunakan --ruffle-dir.")
        else:
            translated.append(value)
            index += 1
    return translated


if __name__ == "__main__":
    raise SystemExit(main(_translate_legacy_args(sys.argv[1:])))
