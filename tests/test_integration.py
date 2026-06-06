import asyncio
import contextlib

import pytest

from tropical_adventure.protocol import read_json_line, write_json_line
from tropical_adventure.server import GameServer
from tropical_adventure.game import join_player


class FailingWriter:
    def write(self, _data):
        raise ConnectionError("gone")

    async def drain(self):
        raise AssertionError("write should fail before drain")


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
