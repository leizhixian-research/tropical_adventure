from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


MAX_EVENT_LOG = 5

DEFAULT_NEEDS = {
    "thirst": 20,
    "hunger": 20,
    "fatigue": 10,
    "health": 100,
    "morale": 50,
    "stress": 10,
}
DEFAULT_CONDITIONS = {"wounds": 0, "pain": 0, "wetness": 0}
DEFAULT_SKILLS = {
    "crafting": 0,
    "woodworking": 0,
    "knapping": 0,
    "herbology": 0,
    "cooking": 0,
    "fishing": 0,
    "swimming": 0,
    "climbing": 0,
}

BLUEPRINTS = {"sharp stone", "fire", "shelter", "raincatcher", "cook fish", "boil water"}
STARTING_BLUEPRINTS = {"sharp stone"}


@dataclass
class ItemStack:
    item: str
    qty: int = 1
    age_minutes: int = 0
    exposed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemStack":
        return cls(**data)


@dataclass
class PlacedObject:
    kind: str
    fuel: int = 0
    active: bool = True
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlacedObject":
        return cls(**data)


@dataclass
class Location:
    name: str
    discovered: bool = False
    features: list[str] = field(default_factory=list)
    ground: list[ItemStack] = field(default_factory=list)
    placed: list[PlacedObject] = field(default_factory=list)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "discovered": self.discovered,
            "features": list(self.features),
            "ground": [i.to_dict() for i in self.ground],
            "placed": [p.to_dict() for p in self.placed],
            "resources": {name: dict(data) for name, data in self.resources.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Location":
        return cls(
            name=data["name"],
            discovered=bool(data.get("discovered", False)),
            features=list(data.get("features", [])),
            ground=[ItemStack.from_dict(i) for i in data.get("ground", [])],
            placed=[PlacedObject.from_dict(p) for p in data.get("placed", [])],
            resources={name: dict(resource) for name, resource in data.get("resources", {}).items()},
        )


@dataclass
class Action:
    name: str
    remaining_minutes: int
    total_minutes: int
    args: dict[str, Any] = field(default_factory=dict)
    reserved: list[ItemStack] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "remaining_minutes": self.remaining_minutes,
            "total_minutes": self.total_minutes,
            "args": dict(self.args),
            "reserved": [i.to_dict() for i in self.reserved],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        return cls(
            name=data["name"],
            remaining_minutes=int(data["remaining_minutes"]),
            total_minutes=int(data.get("total_minutes", data["remaining_minutes"])),
            args=dict(data.get("args", {})),
            reserved=[ItemStack.from_dict(i) for i in data.get("reserved", [])],
        )


@dataclass
class Player:
    name: str
    location: str = "beach"
    connected: bool = False
    needs: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_NEEDS))
    conditions: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CONDITIONS))
    skills: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_SKILLS))
    carried: list[ItemStack] = field(default_factory=list)
    known_blueprints: set[str] = field(default_factory=lambda: set(STARTING_BLUEPRINTS))
    current_action: Action | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "connected": self.connected,
            "needs": dict(self.needs),
            "conditions": dict(self.conditions),
            "skills": dict(self.skills),
            "carried": [i.to_dict() for i in self.carried],
            "known_blueprints": sorted(self.known_blueprints),
            "current_action": self.current_action.to_dict() if self.current_action else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Player":
        player = cls(name=data["name"])
        player.location = data.get("location", "beach")
        # A save file is a campaign snapshot, not a live socket registry. On
        # restart every player begins disconnected and can reconnect by name.
        player.connected = False
        player.needs.update(data.get("needs", {}))
        player.conditions.update(data.get("conditions", {}))
        player.skills.update(data.get("skills", {}))
        player.carried = [ItemStack.from_dict(i) for i in data.get("carried", [])]
        player.known_blueprints = set(data.get("known_blueprints", STARTING_BLUEPRINTS))
        action = data.get("current_action")
        player.current_action = Action.from_dict(action) if action else None
        return player


@dataclass
class WorldProcess:
    kind: str
    location: str
    remaining_minutes: int
    item: str | None = None
    output: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldProcess":
        return cls(**data)


@dataclass
class World:
    seed: int = 1
    day: int = 1
    minute: int = 6 * 60
    tick: int = 0
    minutes_per_tick: int = 3
    weather: str = "clear"
    season: str = "dry"
    paused: bool = False
    locations: dict[str, Location] = field(default_factory=dict)
    players: dict[str, Player] = field(default_factory=dict)
    processes: list[WorldProcess] = field(default_factory=list)
    event_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "day": self.day,
            "minute": self.minute,
            "tick": self.tick,
            "minutes_per_tick": self.minutes_per_tick,
            "weather": self.weather,
            "season": self.season,
            "locations": {k: v.to_dict() for k, v in self.locations.items()},
            "players": {k: v.to_dict() for k, v in self.players.items()},
            "processes": [p.to_dict() for p in self.processes],
            "event_log": self.event_log[-MAX_EVENT_LOG:],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "World":
        world = cls(seed=int(data.get("seed", 1)))
        world.day = int(data.get("day", 1))
        world.minute = int(data.get("minute", 360))
        world.tick = int(data.get("tick", 0))
        world.minutes_per_tick = int(data.get("minutes_per_tick", 3))
        world.weather = data.get("weather", "clear")
        world.season = data.get("season", "dry")
        world.locations = {k: Location.from_dict(v) for k, v in data.get("locations", {}).items()}
        world.players = {k: Player.from_dict(v) for k, v in data.get("players", {}).items()}
        world.processes = [WorldProcess.from_dict(p) for p in data.get("processes", [])]
        world.event_log = list(data.get("event_log", []))[-MAX_EVENT_LOG:]
        world.paused = False
        return world


def log_event(world: World, message: str) -> None:
    world.event_log.append(message)
    del world.event_log[:-MAX_EVENT_LOG]


def add_items(stacks: list[ItemStack], item: str, qty: int = 1, *, age_minutes: int = 0, exposed: bool = True) -> None:
    if qty <= 0:
        return
    for stack in list(stacks):
        if stack.item == item and stack.age_minutes == age_minutes and stack.exposed == exposed:
            stack.qty += qty
            stacks.remove(stack)
            stacks.append(stack)
            return
    stacks.append(ItemStack(item=item, qty=qty, age_minutes=age_minutes, exposed=exposed))


def remove_items(stacks: list[ItemStack], item: str, qty: int = 1) -> list[ItemStack]:
    if qty <= 0:
        return []
    removed: list[ItemStack] = []
    need = qty
    for stack in list(stacks):
        if stack.item != item or need <= 0:
            continue
        take = min(stack.qty, need)
        stack.qty -= take
        need -= take
        removed.append(ItemStack(stack.item, take, stack.age_minutes, stack.exposed))
        if stack.qty == 0:
            stacks.remove(stack)
    if need:
        for stack in removed:
            add_items(stacks, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed)
        raise ValueError(f"missing {qty} {item}")
    return removed


def count_item(stacks: list[ItemStack], item: str) -> int:
    return sum(stack.qty for stack in stacks if stack.item == item)


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))
