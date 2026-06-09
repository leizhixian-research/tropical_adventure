from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
from pathlib import Path
from typing import Any

from .game import cancel_action, disconnect_player, join_player, new_world, start_action, tick_world, world_snapshot
from .models import log_event
from .persistence import _save_world_data, load_world, save_world
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
        self._save_task: asyncio.Task[Path] | None = None
        self._stopping = asyncio.Event()

    async def serve(self, host: str, port: int) -> None:
        server = await asyncio.start_server(self.handle_client, host, port)
        tick_task = asyncio.create_task(self.tick_loop())
        async with server:
            await self._stopping.wait()
            async with self._lock:
                clients = list(self.clients.items())
                self.clients.clear()
                for name, _writer in clients:
                    disconnect_player(self.world, name)
            await asyncio.gather(
                *(write_json_line(writer, {"type": "exit", "message": "server shutting down"}) for _name, writer in clients),
                return_exceptions=True,
            )
            for _name, writer in clients:
                writer.close()
            await asyncio.gather(*(writer.wait_closed() for _name, writer in clients), return_exceptions=True)
            server.close()
            await server.wait_closed()
        tick_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tick_task
        await self.save_current_world(wait=True)

    def stop(self) -> None:
        self._stopping.set()

    async def tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self.tick_interval)
            async with self._lock:
                day_changed = tick_world(self.world)
            if day_changed:
                try:
                    await self.save_current_world()
                except Exception as exc:
                    print(f"autosave failed: {exc}")
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
                disconnected = await self.remove_client_if_current(player_name, writer)
                if disconnected and not self._stopping.is_set():
                    await self.broadcast({"type": "event", "message": f"{player_name} disconnected"})
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def handle_message(self, player_name: str, writer: asyncio.StreamWriter, msg: dict[str, Any]) -> bool:
        kind = msg.get("type")
        broadcast_message: dict[str, Any] | None = None
        response: dict[str, Any] | None = None
        should_save = False
        should_broadcast_snapshot = False
        close_after_response = kind == "exit"

        async with self._lock:
            if kind == "chat":
                text = str(msg.get("text", ""))[:500]
                log_event(self.world, f"{player_name}: {text}")
                broadcast_message = {"type": "chat", "player": player_name, "text": text}
            elif kind == "start_action":
                start_action(self.world, player_name, str(msg.get("action")), dict(msg.get("args", {})))
                broadcast_message = {"type": "event", "message": f"{player_name} started {msg.get('action')}"}
                should_broadcast_snapshot = True
            elif kind == "cancel_action":
                cancel_action(self.world, player_name)
                broadcast_message = {"type": "event", "message": f"{player_name} cancelled action"}
                should_broadcast_snapshot = True
            elif kind == "pause":
                self.world.paused = True
                log_event(self.world, f"{player_name} paused the world.")
                broadcast_message = {"type": "event", "message": "world paused"}
                should_broadcast_snapshot = True
            elif kind == "resume":
                self.world.paused = False
                log_event(self.world, f"{player_name} resumed the world.")
                broadcast_message = {"type": "event", "message": "world resumed"}
                should_broadcast_snapshot = True
            elif kind == "save":
                should_save = True
            elif kind == "exit":
                should_save = True
            elif kind == "inspect":
                response = {"type": "snapshot", "snapshot": world_snapshot(self.world, player_name)}
            else:
                response = {"type": "error", "message": f"unknown message type: {kind}"}

        if should_save:
            try:
                await self.save_current_world(wait=True)
            except Exception as exc:
                await write_json_line(writer, {"type": "error", "message": f"save failed: {exc}"})
                return True
            if kind == "save":
                broadcast_message = {"type": "event", "message": "manual save complete"}
            elif kind == "exit":
                response = {"type": "exit", "message": "saved; exiting"}
        if response:
            await write_json_line(writer, response)
            return not close_after_response
        if broadcast_message:
            await self.broadcast(broadcast_message)
            if should_broadcast_snapshot:
                await self.broadcast_snapshots()
        return True

    async def save_current_world(self, *, wait: bool = False) -> Path | None:
        while self._save_task is not None:
            if not wait:
                return None
            with contextlib.suppress(Exception):
                await asyncio.shield(self._save_task)

        async def save() -> Path:
            async with self._lock:
                data = self.world.to_dict()
                day = self.world.day
                minute = self.world.minute
            return await asyncio.to_thread(_save_world_data, data, self.save_path, day=day, minute=minute)

        self._save_task = asyncio.create_task(save())
        self._save_task.add_done_callback(self._clear_save_task)
        return await asyncio.shield(self._save_task)

    def _clear_save_task(self, task: asyncio.Task[Path]) -> None:
        if self._save_task is task:
            self._save_task = None
        with contextlib.suppress(asyncio.CancelledError, Exception):
            task.exception()

    async def remove_client_if_current(self, name: str, writer: asyncio.StreamWriter) -> bool:
        async with self._lock:
            if self.clients.get(name) is not writer:
                return False
            del self.clients[name]
            disconnect_player(self.world, name)
            return True

    async def drop_client_if_current(self, name: str, writer: asyncio.StreamWriter) -> None:
        if await self.remove_client_if_current(name, writer):
            with contextlib.suppress(Exception):
                writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self.clients.items())

        await asyncio.gather(*(self.send_or_drop(name, writer, message) for name, writer in clients))

    async def broadcast_snapshots(self) -> None:
        async with self._lock:
            messages = [
                (name, writer, {"type": "snapshot", "snapshot": world_snapshot(self.world, name)})
                for name, writer in self.clients.items()
            ]

        await asyncio.gather(*(self.send_or_drop(name, writer, message) for name, writer, message in messages))

    async def send_or_drop(self, name: str, writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        try:
            await write_json_line(writer, message)
        except Exception:
            await self.drop_client_if_current(name, writer)


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
