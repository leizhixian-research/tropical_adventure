from __future__ import annotations

from copy import deepcopy
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
DEFAULT_CONDITIONS = {
    "wounds": 0,
    "pain": 0,
    "wetness": 0,
    "filth": 10,
    "sunburn": 0,
    "back_pain": 0,
    "bug_bites": 0,
    "foot_damage": 0,
    "hand_damage": 0,
    "blood_loss": 0,
    "bruising": 0,
    "burns": 0,
    "eye_damage": 0,
    "lung_damage": 0,
    "hyperthermia": 0,
    "hypothermia": 0,
    "blood_pressure": 0,
    "fever": 0,
    "nausea": 0,
    "diarrhea": 0,
    "headache": 0,
    "bug_repellent": 0,
    "altered_mind_state": 0,
    "mania": 0,
    "derealization": 0,
    "isolation": 0,
    "food_poisoning": 0,
    "parasites": 0,
    "malaria": 0,
    "bacterial_infection": 0,
    "alcohol": 0,
    "sodium_imbalance": 0,
    "quinine": 0,
    "caffeine": 0,
    "capsaicin": 0,
    "psilocybin": 0,
    "venom_krait": 0,
}
PLAYER_STAT_GROUPS = {
    "core": (
        "health",
        "hydration",
        "satiation",
        "stamina",
        "morale",
        "calm",
        "wakefulness",
        "comfort",
        "dryness",
        "cleanliness",
        "wound_recovery",
    ),
    "mental": (
        "appetite",
        "entertainment",
        "courage",
        "companionship",
        "mental_clarity",
        "altered_mind_stability",
        "mania_control",
        "derealization_control",
        "mental_structure",
        "isolation_resilience",
    ),
    "physical": (
        "healthy_weight",
        "skin_integrity",
        "tanning",
        "foot_callouses",
        "hand_callouses",
        "eyesight",
    ),
    "damage": (
        "sun_safety",
        "back_comfort",
        "bite_comfort",
        "foot_health",
        "hand_health",
        "blood_volume",
        "bruise_recovery",
        "burn_recovery",
        "eye_health",
        "lung_health",
    ),
    "internal": (
        "heat_balance",
        "cold_balance",
        "blood_pressure_stability",
        "parasite_control",
        "malaria_resistance",
        "infection_control",
        "fever_control",
        "stomach_stability",
        "digestion",
        "immunity",
        "headache_comfort",
    ),
    "chemical": (
        "analgesia_coverage",
        "spider_lily_recovery",
        "ginger_settledness",
        "antibiotic_coverage",
        "sobriety",
        "sodium_balance",
        "quinine_safety",
        "caffeine_balance",
        "capsaicin_cooling",
        "psilocybin_grounding",
        "jasmine_restfulness",
        "food_poisoning_recovery",
        "china_rose_balance",
        "rice_tolerance",
        "venom_krait_resistance",
    ),
    "protection": (
        "heat_protection",
        "cold_protection",
        "sun_protection",
        "rain_protection",
        "bug_protection",
        "foot_protection",
        "armor",
    ),
    "saturation": (
        "coconut_appetite",
        "crustacean_appetite",
        "mollusk_appetite",
        "fish_appetite",
        "bird_appetite",
        "meat_appetite",
        "reptile_appetite",
        "banana_appetite",
        "fruit_appetite",
        "vegetable_appetite",
        "sago_appetite",
        "sugar_appetite",
        "rice_appetite",
        "nut_appetite",
        "ration_appetite",
        "egg_appetite",
        "dairy_appetite",
        "mushroom_appetite",
        "yam_appetite",
    ),
}
PLAYER_STAT_KEYS = tuple(key for keys in PLAYER_STAT_GROUPS.values() for key in keys)
SATURATION_STAT_KEYS = PLAYER_STAT_GROUPS["saturation"]
DEFAULT_STATS = {
    "wakefulness": 90,
    "appetite": 80,
    "entertainment": 50,
    "courage": 60,
    "companionship": 65,
    "mental_clarity": 100,
    "mental_structure": 100,
    "healthy_weight": 75,
    "skin_integrity": 100,
    "tanning": 75,
    "foot_callouses": 70,
    "hand_callouses": 70,
    "eyesight": 100,
    "immunity": 85,
    "heat_protection": 100,
    "cold_protection": 100,
    "sun_protection": 100,
    "rain_protection": 100,
    "bug_protection": 100,
    "foot_protection": 100,
    "armor": 100,
    **{key: 100 for key in SATURATION_STAT_KEYS},
}
DEFAULT_SKILLS = {
    "crafting": 0,
    "woodworking": 0,
    "knapping": 0,
    "herbology": 0,
    "cooking": 0,
    "metalworking": 0,
    "fishing": 0,
    "spear_fishing": 0,
    "swimming": 0,
    "climbing": 0,
    "trapping": 0,
}

@dataclass
class ItemStack:
    item: str
    qty: int = 1
    age_minutes: int = 0
    exposed: bool = True
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemStack":
        return cls(
            item=data["item"],
            qty=int(data.get("qty", 1)),
            age_minutes=int(data.get("age_minutes", 0)),
            exposed=bool(data.get("exposed", True)),
            data=dict(data.get("data", {})),
        )


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
    location_cards: list[str] = field(default_factory=list)
    ground: list[ItemStack] = field(default_factory=list)
    placed: list[PlacedObject] = field(default_factory=list)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    explore_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "discovered": self.discovered,
            "features": list(self.features),
            "location_cards": list(self.location_cards),
            "ground": [i.to_dict() for i in self.ground],
            "placed": [p.to_dict() for p in self.placed],
            "resources": {name: dict(data) for name, data in self.resources.items()},
            "explore_counts": dict(self.explore_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Location":
        return cls(
            name=data["name"],
            discovered=bool(data.get("discovered", False)),
            features=list(data.get("features", [])),
            location_cards=list(data.get("location_cards", [])),
            ground=[ItemStack.from_dict(i) for i in data.get("ground", [])],
            placed=[PlacedObject.from_dict(p) for p in data.get("placed", [])],
            resources={name: dict(resource) for name, resource in data.get("resources", {}).items()},
            explore_counts={str(name): int(count) for name, count in data.get("explore_counts", {}).items()},
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
    status: str = "alive"
    outcome_reason: str | None = None
    ended_day: int | None = None
    ended_minute: int | None = None
    needs: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_NEEDS))
    conditions: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CONDITIONS))
    stats: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_STATS))
    skills: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_SKILLS))
    carried: list[ItemStack] = field(default_factory=list)
    current_action: Action | None = None
    action_history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "connected": self.connected,
            "status": self.status,
            "outcome_reason": self.outcome_reason,
            "ended_day": self.ended_day,
            "ended_minute": self.ended_minute,
            "needs": dict(self.needs),
            "conditions": dict(self.conditions),
            "stats": dict(self.stats),
            "skills": dict(self.skills),
            "carried": [i.to_dict() for i in self.carried],
            "current_action": self.current_action.to_dict() if self.current_action else None,
            "action_history": list(self.action_history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Player":
        player = cls(name=data["name"])
        player.location = data.get("location", "beach")
        # A save file is a campaign snapshot, not a live socket registry. On
        # restart every player begins disconnected and can reconnect by name.
        player.connected = False
        player.status = str(data.get("status", "alive"))
        player.outcome_reason = data.get("outcome_reason")
        player.ended_day = data.get("ended_day")
        player.ended_minute = data.get("ended_minute")
        player.needs.update(data.get("needs", {}))
        player.conditions.update(data.get("conditions", {}))
        player.stats.update(data.get("stats", {}))
        player.skills.update(data.get("skills", {}))
        player.carried = [ItemStack.from_dict(i) for i in data.get("carried", [])]
        action = data.get("current_action")
        player.current_action = Action.from_dict(action) if action else None
        player.action_history = [str(action) for action in data.get("action_history", [])]
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
    rain_counter: int = 400
    weather_remaining_minutes: int = 360
    paused: bool = False
    outcome: str | None = None
    outcome_player: str | None = None
    outcome_reason: str | None = None
    outcome_day: int | None = None
    outcome_minute: int | None = None
    raft_distance: int = 0
    raft_event: str | None = None
    raft_event_remaining_minutes: int = 0
    raft_signal_progress: int = 0
    raft_missed_ships: int = 0
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
            "rain_counter": self.rain_counter,
            "weather_remaining_minutes": self.weather_remaining_minutes,
            "outcome": self.outcome,
            "outcome_player": self.outcome_player,
            "outcome_reason": self.outcome_reason,
            "outcome_day": self.outcome_day,
            "outcome_minute": self.outcome_minute,
            "raft_distance": self.raft_distance,
            "raft_event": self.raft_event,
            "raft_event_remaining_minutes": self.raft_event_remaining_minutes,
            "raft_signal_progress": self.raft_signal_progress,
            "raft_missed_ships": self.raft_missed_ships,
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
        world.rain_counter = int(data.get("rain_counter", 400))
        world.weather_remaining_minutes = int(data.get("weather_remaining_minutes", 360))
        world.outcome = data.get("outcome")
        world.outcome_player = data.get("outcome_player")
        world.outcome_reason = data.get("outcome_reason")
        world.outcome_day = data.get("outcome_day")
        world.outcome_minute = data.get("outcome_minute")
        world.raft_distance = int(data.get("raft_distance", 0))
        world.raft_event = data.get("raft_event")
        world.raft_event_remaining_minutes = int(data.get("raft_event_remaining_minutes", 0))
        world.raft_signal_progress = int(data.get("raft_signal_progress", 0))
        world.raft_missed_ships = int(data.get("raft_missed_ships", 0))
        world.locations = {k: Location.from_dict(v) for k, v in data.get("locations", {}).items()}
        world.players = {k: Player.from_dict(v) for k, v in data.get("players", {}).items()}
        world.processes = [WorldProcess.from_dict(p) for p in data.get("processes", [])]
        world.event_log = list(data.get("event_log", []))[-MAX_EVENT_LOG:]
        world.paused = False
        return world


def log_event(world: World, message: str) -> None:
    world.event_log.append(message)
    del world.event_log[:-MAX_EVENT_LOG]


def add_items(
    stacks: list[ItemStack],
    item: str,
    qty: int = 1,
    *,
    age_minutes: int = 0,
    exposed: bool = True,
    data: dict[str, Any] | None = None,
) -> None:
    if qty <= 0:
        return
    stack_data = deepcopy(data or {})
    if "storage_capacity" in stack_data:
        for _ in range(qty):
            stacks.append(ItemStack(item=item, qty=1, age_minutes=age_minutes, exposed=exposed, data=deepcopy(stack_data)))
        return
    for stack in list(stacks):
        if stack.item == item and stack.age_minutes == age_minutes and stack.exposed == exposed and stack.data == stack_data:
            stack.qty += qty
            stacks.remove(stack)
            stacks.append(stack)
            return
    stacks.append(ItemStack(item=item, qty=qty, age_minutes=age_minutes, exposed=exposed, data=stack_data))


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
        removed.append(ItemStack(stack.item, take, stack.age_minutes, stack.exposed, deepcopy(stack.data)))
        if stack.qty == 0:
            stacks.remove(stack)
    if need:
        for stack in removed:
            add_items(stacks, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
        raise ValueError(f"missing {qty} {item}")
    return removed


def count_item(stacks: list[ItemStack], item: str) -> int:
    return sum(stack.qty for stack in stacks if stack.item == item)


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))
