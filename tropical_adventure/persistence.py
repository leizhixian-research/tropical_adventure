from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .game import new_world
from .models import World


def load_world(path: str | Path) -> World:
    save_path = Path(path)
    if not save_path.exists():
        return new_world()
    try:
        data = json.loads(save_path.read_text(encoding="utf-8"))
        return World.from_dict(data)
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"bad save file {save_path}: {exc}") from exc


def save_world(world: World, path: str | Path, *, day: int | None = None, minute: int | None = None) -> Path:
    return _save_world_data(
        world.to_dict(),
        path,
        day=world.day if day is None else day,
        minute=world.minute if minute is None else minute,
    )


def _save_world_data(data: dict, path: str | Path, *, day: int, minute: int) -> Path:
    requested_path = Path(path)
    save_path = requested_path.parent / f"island_{day}_{minute}.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True)
    fd, tmp = tempfile.mkstemp(prefix=save_path.name + ".", suffix=".tmp", dir=str(save_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, save_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return save_path
