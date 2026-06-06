from __future__ import annotations

import asyncio
import json
from typing import Any


async def read_json_line(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    line = await reader.readline()
    if not line:
        return None
    try:
        data = json.loads(line.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON line: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("protocol messages must be JSON objects")
    return data


async def write_json_line(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    writer.write(json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n")
    await writer.drain()
