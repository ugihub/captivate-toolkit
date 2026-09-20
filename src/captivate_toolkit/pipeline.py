from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__


def unique_job_dir(root: Path, input_path: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(input_path).stem).strip("._") or "captivate_job"
    for index in range(1, 10000):
        candidate = root / (stem if index == 1 else f"{stem}_{index:02d}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"Tidak dapat membuat folder job unik di {root}.")


def new_manifest(input_path: Path, options: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool_version": __version__,
        "job_id": os.urandom(8).hex(),
        "created_at": datetime.now(UTC).isoformat(),
        "input": {"path": str(Path(input_path).resolve()), "sha256": None},
        "options": options or {},
        "stages": {},
        "artifacts": [],
        "warnings": [],
    }


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def set_stage(manifest: dict[str, Any], name: str, status: str, **details: Any) -> None:
    manifest.setdefault("stages", {})[name] = {
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
        **details,
    }


def add_artifact(manifest: dict[str, Any], path: Path, *, root: Path) -> None:
    try:
        relative = str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        relative = str(path)
    if relative not in manifest.setdefault("artifacts", []):
        manifest["artifacts"].append(relative)
