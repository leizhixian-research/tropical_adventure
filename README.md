# Tropical Adventure

A self-hosted multiplayer terminal survival game inspired by detailed island survival sims.

## Run

```bash
uv run python -m tropical_adventure.server --save saves/island.json --host 127.0.0.1 --port 8765
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Alice
```

Use `--host 0.0.0.0` only for intentional LAN/trusted hosting. Prefer `--invite` when binding beyond localhost.
