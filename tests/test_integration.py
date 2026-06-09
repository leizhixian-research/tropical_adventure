import asyncio
import contextlib
import json
import socket
import threading

import pytest

from tropical_adventure.protocol import read_json_line, write_json_line
from tropical_adventure import server as server_module
from tropical_adventure.server import GameServer
from tropical_adventure.game import join_player
from tropical_adventure.client import NetworkClient


class FailingWriter:
    def write(self, _data):
        raise ConnectionError("gone")

    async def drain(self):
        raise AssertionError("write should fail before drain")


class BlockingWriter:
    def __init__(self):
        self.drain_started = asyncio.Event()
        self.release_drain = asyncio.Event()

    def write(self, _data):
        pass

    async def drain(self):
        self.drain_started.set()
        await self.release_drain.wait()


class DelayedFailingWriter:
    def __init__(self):
        self.drain_started = asyncio.Event()
        self.release_drain = asyncio.Event()

    def write(self, _data):
        pass

    async def drain(self):
        self.drain_started.set()
        await self.release_drain.wait()
        raise ConnectionError("gone")


class RecordingWriter:
    def __init__(self):
        self.messages = []

    def write(self, data):
        self.messages.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


async def connect_client(port, name, invite=None):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    await write_json_line(writer, {"type": "join", "name": name, "invite": invite})
    return reader, writer, await read_json_line(reader)


@pytest.fixture
async def running_server(tmp_path):
    server = GameServer(str(tmp_path / "load-file.json"), invite="secret", tick_interval=0.02)
    srv = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    tick_task = asyncio.create_task(server.tick_loop())
    try:
        yield server, port, tmp_path
    finally:
        srv.close()
        await srv.wait_closed()
        tick_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tick_task


@pytest.mark.asyncio
async def test_broadcast_snapshots_drops_failed_writers(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    player = join_player(server.world, "Alice")
    server.clients[player.name] = FailingWriter()

    await server.broadcast_snapshots()

    assert server.clients == {}
    assert not player.connected


@pytest.mark.asyncio
async def test_inspect_response_does_not_hold_world_lock_while_network_drain_blocks(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    join_player(server.world, "Alice")
    writer = BlockingWriter()

    task = asyncio.create_task(server.handle_message("Alice", writer, {"type": "inspect"}))
    await asyncio.wait_for(writer.drain_started.wait(), timeout=1)

    async with asyncio.timeout(0.1):
        async with server._lock:
            pass

    writer.release_drain.set()
    assert await asyncio.wait_for(task, timeout=1) is True


@pytest.mark.asyncio
async def test_failed_old_broadcast_writer_does_not_remove_newer_connection(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    player = join_player(server.world, "Alice")
    old_writer = DelayedFailingWriter()
    new_writer = BlockingWriter()
    server.clients[player.name] = old_writer

    task = asyncio.create_task(server.broadcast_snapshots())
    await asyncio.wait_for(old_writer.drain_started.wait(), timeout=1)
    server.clients[player.name] = new_writer
    old_writer.release_drain.set()
    await asyncio.wait_for(task, timeout=1)

    assert server.clients[player.name] is new_writer
    assert player.connected


@pytest.mark.asyncio
async def test_broadcast_snapshots_sends_player_dependent_payloads(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    alice = join_player(server.world, "Alice")
    bob = join_player(server.world, "Bob")
    bob.location = "rocks"
    server.world.locations["rocks"].discovered = True
    alice_writer = RecordingWriter()
    bob_writer = RecordingWriter()
    server.clients = {alice.name: alice_writer, bob.name: bob_writer}

    await server.broadcast_snapshots()

    alice_snapshot = alice_writer.messages[-1]["snapshot"]
    bob_snapshot = bob_writer.messages[-1]["snapshot"]
    assert set(alice_snapshot["players"]) == {"Alice"}
    assert set(bob_snapshot["players"]) == {"Bob"}
    assert alice_snapshot["players"]["Alice"]["location"] == "beach"
    assert bob_snapshot["players"]["Bob"]["location"] == "rocks"
    assert alice_snapshot != bob_snapshot


@pytest.mark.asyncio
async def test_stale_client_cleanup_does_not_disconnect_newer_connection(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    srv = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    try:
        _reader, old_writer, joined = await connect_client(port, "Alice")
        assert joined["type"] == "joined"
        new_writer = object()
        async with server._lock:
            server.clients["Alice"] = new_writer
            server.world.players["Alice"].connected = True

        old_writer.close()
        await old_writer.wait_closed()
        await asyncio.sleep(0.05)

        assert server.clients["Alice"] is new_writer
        assert server.world.players["Alice"].connected
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_overlapping_saves_skip_instead_of_queuing(monkeypatch, tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def blocking_save(*args, **kwargs):
        nonlocal calls
        calls += 1
        started.set()
        release.wait(timeout=1)
        return tmp_path / "saved.json"

    monkeypatch.setattr(server_module, "_save_world_data", blocking_save)

    first = asyncio.create_task(server.save_current_world())
    assert await asyncio.to_thread(started.wait, 1)

    assert await server.save_current_world() is None

    release.set()
    assert await asyncio.wait_for(first, timeout=1) == tmp_path / "saved.json"
    assert calls == 1


@pytest.mark.asyncio
async def test_overlapping_saves_waiting_for_world_lock_still_skip(monkeypatch, tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    calls = 0

    def save_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        return tmp_path / "saved.json"

    monkeypatch.setattr(server_module, "_save_world_data", save_once)

    async with server._lock:
        first = asyncio.create_task(server.save_current_world())
        second = asyncio.create_task(server.save_current_world())
        await asyncio.sleep(0)

    results = await asyncio.gather(first, second)

    assert sorted(results, key=lambda value: str(value)) == [tmp_path / "saved.json", None]
    assert calls == 1


@pytest.mark.asyncio
async def test_waiting_save_retries_after_in_progress_save_fails(monkeypatch, tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def fail_then_save(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            release.wait(timeout=1)
            raise OSError("disk busy")
        return tmp_path / "saved.json"

    monkeypatch.setattr(server_module, "_save_world_data", fail_then_save)

    first = asyncio.create_task(server.save_current_world())
    assert await asyncio.to_thread(started.wait, 1)
    second = asyncio.create_task(server.save_current_world(wait=True))

    release.set()
    with pytest.raises(OSError):
        await asyncio.wait_for(first, timeout=1)
    assert await asyncio.wait_for(second, timeout=1) == tmp_path / "saved.json"
    assert calls == 2


@pytest.mark.asyncio
async def test_manual_save_waits_for_in_progress_save(monkeypatch, tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    player = join_player(server.world, "Alice")
    writer = RecordingWriter()
    server.clients[player.name] = writer
    started = threading.Event()
    release = threading.Event()

    def blocking_save(*args, **kwargs):
        started.set()
        release.wait(timeout=1)
        return tmp_path / "saved.json"

    monkeypatch.setattr(server_module, "_save_world_data", blocking_save)

    first = asyncio.create_task(server.save_current_world())
    assert await asyncio.to_thread(started.wait, 1)

    manual_save = asyncio.create_task(server.handle_message("Alice", writer, {"type": "save"}))
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.wait_for(first, timeout=1) == tmp_path / "saved.json"
    assert await asyncio.wait_for(manual_save, timeout=1) is True
    assert server._save_task is None
    assert {"type": "event", "message": "manual save complete"} in writer.messages


@pytest.mark.asyncio
async def test_exit_waits_for_in_progress_save(monkeypatch, tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    player = join_player(server.world, "Alice")
    writer = RecordingWriter()
    started = threading.Event()
    release = threading.Event()

    def blocking_save(*args, **kwargs):
        started.set()
        release.wait(timeout=1)
        return tmp_path / "saved.json"

    monkeypatch.setattr(server_module, "_save_world_data", blocking_save)

    first = asyncio.create_task(server.save_current_world())
    assert await asyncio.to_thread(started.wait, 1)

    exit_task = asyncio.create_task(server.handle_message(player.name, writer, {"type": "exit"}))
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.wait_for(first, timeout=1) == tmp_path / "saved.json"
    assert await asyncio.wait_for(exit_task, timeout=1) is False
    assert {"type": "exit", "message": "saved; exiting"} in writer.messages


@pytest.mark.asyncio
async def test_chat_events_do_not_grow_world_event_log_without_ticks(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    player = join_player(server.world, "Alice")
    writer = RecordingWriter()
    server.clients[player.name] = writer

    for index in range(20):
        assert await server.handle_message("Alice", writer, {"type": "chat", "text": f"msg {index}"}) is True

    assert server.world.event_log == [f"Alice: msg {index}" for index in range(15, 20)]


@pytest.mark.asyncio
async def test_network_client_exits_when_server_disconnects_without_exit_message():
    async def handle(reader, writer):
        await read_json_line(reader)
        writer.close()
        await writer.wait_closed()

    srv = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    client = NetworkClient("127.0.0.1", port, "Alice")
    try:
        await client.connect()
        assert await asyncio.wait_for(client.queue.get(), timeout=1) == {
            "type": "exit",
            "message": "server disconnected",
        }
    finally:
        await client.close()
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_server_shutdown_tells_connected_clients_to_exit(tmp_path):
    server = GameServer(str(tmp_path / "island.json"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    serve_task = asyncio.create_task(server.serve("127.0.0.1", port))
    try:
        for _ in range(20):
            try:
                reader, writer, joined = await connect_client(port, "Alice")
                break
            except OSError:
                await asyncio.sleep(0.01)
        else:
            raise AssertionError("server did not start")
        assert joined["type"] == "joined"

        server.stop()

        exit_seen = False
        for _ in range(5):
            msg = await asyncio.wait_for(read_json_line(reader), timeout=1)
            if msg and msg.get("type") == "exit":
                assert msg == {"type": "exit", "message": "server shutting down"}
                exit_seen = True
                break
        assert exit_seen
        assert await asyncio.wait_for(read_json_line(reader), timeout=1) is None
        assert server.clients == {}
        assert not server.world.players["Alice"].connected
        await asyncio.wait_for(serve_task, timeout=1)
        writer.close()
        await writer.wait_closed()
    finally:
        server.stop()
        if not serve_task.done():
            serve_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await serve_task


def test_server_without_save_file_starts_fresh_and_creates_initial_island_0_0(tmp_path):
    stale = tmp_path / "island_0_0.json"
    stale.write_text("stale content that must be truncated", encoding="utf-8")

    server = GameServer(None, save_dir=tmp_path)

    assert server.save_path == tmp_path / "island_0_0.json"
    assert stale.read_text(encoding="utf-8").startswith("{\n")
    assert server.world.day == 1
    assert server.world.minute == 6 * 60


@pytest.mark.asyncio
async def test_server_rejects_bad_invite(running_server):
    _, port, _ = running_server
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    await write_json_line(writer, {"type": "join", "name": "Alice", "invite": "wrong"})
    msg = await read_json_line(reader)
    writer.close()
    await writer.wait_closed()
    assert msg == {"type": "error", "message": "bad invite"}


@pytest.mark.asyncio
async def test_two_clients_join_chat_actions_pause_resume_and_save(running_server):
    _, port, save_dir = running_server
    r1, w1, joined1 = await connect_client(port, "Alice", "secret")
    r2, w2, joined2 = await connect_client(port, "Bob", "secret")
    assert joined1["type"] == "joined"
    assert joined2["type"] == "joined"

    # Duplicate active name is rejected.
    rdup, wdup = await asyncio.open_connection("127.0.0.1", port)
    await write_json_line(wdup, {"type": "join", "name": "Alice", "invite": "secret"})
    assert (await read_json_line(rdup))["message"] == "player name already connected"
    wdup.close()
    await wdup.wait_closed()

    await write_json_line(w1, {"type": "chat", "text": "hello"})
    messages = [await read_json_line(r2) for _ in range(4)]
    assert any(m and m.get("type") == "chat" and m.get("text") == "hello" for m in messages)

    long_text = "x" * 1200
    await write_json_line(w1, {"type": "chat", "text": long_text})
    long_chat_seen = False
    for _ in range(8):
        msg = await read_json_line(r2)
        if msg and msg.get("type") == "chat":
            assert msg.get("text") == long_text[:500]
            long_chat_seen = True
            break
    assert long_chat_seen

    await write_json_line(w1, {"type": "start_action", "action": "gather", "args": {"item": "cooked fish"}})
    error_seen = False
    for _ in range(8):
        msg = await read_json_line(r1)
        if msg and msg.get("type") == "error" and "cannot gather cooked fish" in msg.get("message", ""):
            error_seen = True
            break
    assert error_seen

    await write_json_line(w1, {"type": "start_action", "action": "forage", "args": {}})
    await write_json_line(w2, {"type": "start_action", "action": "forage", "args": {}})
    await asyncio.sleep(0.12)
    await write_json_line(w1, {"type": "pause"})
    await asyncio.sleep(0.05)
    await write_json_line(w2, {"type": "resume"})
    await write_json_line(w1, {"type": "save"})
    await asyncio.sleep(0.05)
    first_saves = sorted(p.name for p in save_dir.glob("island_*.json"))
    assert first_saves
    assert all(name.startswith("island_") for name in first_saves)

    await write_json_line(w1, {"type": "exit"})
    exit_seen = False
    for _ in range(50):
        msg = await asyncio.wait_for(read_json_line(r1), timeout=2)
        if msg and msg.get("type") == "exit":
            assert msg == {"type": "exit", "message": "saved; exiting"}
            exit_seen = True
            break
    assert exit_seen
    assert await asyncio.wait_for(read_json_line(r1), timeout=2) is None
    assert sorted(p.name for p in save_dir.glob("island_*.json"))

    w2.close()
    await w2.wait_closed()


@pytest.mark.asyncio
async def test_move_completion_updates_location_and_event_log(running_server):
    _, port, _ = running_server
    reader, writer, joined = await connect_client(port, "Alice", "secret")
    assert joined["type"] == "joined"

    await write_json_line(writer, {"type": "start_action", "action": "explore", "args": {}})
    for _ in range(30):
        msg = await asyncio.wait_for(read_json_line(reader), timeout=2)
        if msg and msg.get("type") == "snapshot" and "move" in msg["snapshot"]["players"]["Alice"]["available_actions"]:
            break
    else:
        raise AssertionError("explore did not unlock move")

    await write_json_line(writer, {"type": "start_action", "action": "move", "args": {"location": "jungle outskirts"}})
    for _ in range(30):
        msg = await asyncio.wait_for(read_json_line(reader), timeout=2)
        if msg and msg.get("type") == "snapshot":
            player = msg["snapshot"]["players"]["Alice"]
            if player["location"] == "jungle outskirts":
                assert "Alice completed move." in msg["snapshot"]["event_log"]
                break
    else:
        raise AssertionError("move completion snapshot did not arrive")

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_reconnect_by_name_resumes_saved_state(tmp_path):
    server = GameServer(str(tmp_path / "island.json"), tick_interval=0.02)
    srv = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    tick_task = asyncio.create_task(server.tick_loop())
    try:
        r1, w1, joined = await connect_client(port, "Alice")
        assert joined["snapshot"]["players"]["Alice"]["location"] == "beach"
        w1.close()
        await w1.wait_closed()
        await asyncio.sleep(0.05)
        r2, w2, joined2 = await connect_client(port, "Alice")
        assert joined2["type"] == "joined"
        assert joined2["snapshot"]["players"]["Alice"]["name"] == "Alice"
        w2.close()
        await w2.wait_closed()
    finally:
        srv.close()
        await srv.wait_closed()
        tick_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tick_task
