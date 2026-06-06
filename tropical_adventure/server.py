from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
from pathlib import Path
from typing import Any

from .game import cancel_action, disconnect_player, join_player, new_world, start_action, tick_world, world_snapshot
from .persistence import load_world, save_world
from .protocol import read_json_line, write_json_line


class GameServer:
    def __init__(self, save_path: str | None, invite: str | None = None, tick_interval: float = 1.0, save_dir: str | Path = "saves"):
        self.save_path = Path(save_path) if save_path is not None else Path(save_dir) / "island_0_0.json"
        self.invite = invite
        self.tick_interval = tick_interval
        if save_path is None:
            self.world = new_world()
            save_world(self.world, self.save_path, day=0, minute=0)
        else:
            self.world = load_world(self.save_path)
        self.clients: dict[str, asyncio.StreamWriter] = {}
        self._lock = asyncio.Lock()
        self._stopping = asyncio.Event()

    async def serve(self, host: str, port: int) -> None:
        server = await asyncio.start_server(self.handle_client, host, port)
        tick_task = asyncio.create_task(self.tick_loop())
        async with server:
            await self._stopping.wait()
            server.close()
            await server.wait_closed()
        tick_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tick_task
        async with self._lock:
            save_world(self.world, self.save_path)

    def stop(self) -> None:
        self._stopping.set()

    async def tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self.tick_interval)
            async with self._lock:
                day_changed = tick_world(self.world)
                if day_changed:
                    save_world(self.world, self.save_path)
            await self.broadcast_snapshots()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        player_name: str | None = None
        try:
            hello = await read_json_line(reader)
            if not hello or hello.get("type") != "join":
                await write_json_line(writer, {"type": "error", "message": "first message must be join"})
                return
            if self.invite is not None and hello.get("invite") != self.invite:
                await write_json_line(writer, {"type": "error", "message": "bad invite"})
                return
            requested_name = str(hello.get("name", "")).strip()
            async with self._lock:
                player = join_player(self.world, requested_name)
                player_name = player.name
                self.clients[player.name] = writer
                snapshot = world_snapshot(self.world, player.name)
            await write_json_line(writer, {"type": "joined", "player": player.name, "snapshot": snapshot})
            await self.broadcast({"type": "event", "message": f"{player.name} joined"})
            while True:
                try:
                    msg = await read_json_line(reader)
                    if msg is None:
                        break
                    if not await self.handle_message(player.name, writer, msg):
                        break
                except ValueError as exc:
                    await write_json_line(writer, {"type": "error", "message": str(exc)})
        except ValueError as exc:
            await write_json_line(writer, {"type": "error", "message": str(exc)})
        finally:
            if player_name:
                async with self._lock:
                    disconnect_player(self.world, player_name)
                    if self.clients.get(player_name) is writer:
                        del self.clients[player_name]
                await self.broadcast({"type": "event", "message": f"{player_name} disconnected"})
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def handle_message(self, player_name: str, writer: asyncio.StreamWriter, msg: dict[str, Any]) -> bool:
        kind = msg.get("type")
        async with self._lock:
            if kind == "chat":
                text = str(msg.get("text", ""))[:500]
                self.world.event_log.append(f"{player_name}: {text}")
                out = {"type": "chat", "player": player_name, "text": text}
            elif kind == "start_action":
                start_action(self.world, player_name, str(msg.get("action")), dict(msg.get("args", {})))
                out = {"type": "event", "message": f"{player_name} started {msg.get('action')}"}
            elif kind == "cancel_action":
                cancel_action(self.world, player_name)
                out = {"type": "event", "message": f"{player_name} cancelled action"}
            elif kind == "pause":
                self.world.paused = True
                self.world.event_log.append(f"{player_name} paused the world.")
                out = {"type": "event", "message": "world paused"}
            elif kind == "resume":
                self.world.paused = False
                self.world.event_log.append(f"{player_name} resumed the world.")
                out = {"type": "event", "message": "world resumed"}
            elif kind == "save":
                save_world(self.world, self.save_path)
                out = {"type": "event", "message": "manual save complete"}
            elif kind == "exit":
                save_world(self.world, self.save_path)
                await write_json_line(writer, {"type": "exit", "message": "saved; exiting"})
                return False
            elif kind == "inspect":
                await write_json_line(writer, {"type": "snapshot", "snapshot": world_snapshot(self.world, player_name)})
                return True
            else:
                await write_json_line(writer, {"type": "error", "message": f"unknown message type: {kind}"})
                return True
        await self.broadcast(out)
        await self.broadcast_snapshots()
        return True

    async def broadcast(self, message: dict[str, Any]) -> None:
        for name, writer in list(self.clients.items()):
            try:
                await write_json_line(writer, message)
            except Exception:
                self.clients.pop(name, None)

    async def broadcast_snapshots(self) -> None:
        async with self._lock:
            payloads = [(name, world_snapshot(self.world, name)) for name in self.clients]
        for name, snapshot in payloads:
            writer = self.clients.get(name)
            if writer:
                try:
                    await write_json_line(writer, {"type": "snapshot", "snapshot": snapshot})
                except Exception:
                    self.clients.pop(name, None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Tropical Adventure server")
    parser.add_argument("--save")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--invite")
    parser.add_argument("--tick-interval", type=float, default=1.0)
    return parser


async def amain(args: argparse.Namespace) -> None:
    server = GameServer(args.save, invite=args.invite, tick_interval=args.tick_interval)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, server.stop)
    print(f"Serving Tropical Adventure on {args.host}:{args.port}; save={server.save_path}")
    await server.serve(args.host, args.port)


def main() -> None:
    asyncio.run(amain(build_parser().parse_args()))


if __name__ == "__main__":
    main()
