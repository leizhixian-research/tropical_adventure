from __future__ import annotations

from copy import deepcopy
import random
from typing import Any

from .content import (
    ACTION_BLOCKS_PLAYER,
    ACTION_DURATIONS,
    ACTION_INPUTS,
    AREA_DEFS,
    AREA_EXPLORE_AREAS,
    AREA_EXPLORE_CARDS,
    AREA_EXPLORE_ITEMS,
    AREA_NEIGHBORS,
    COPPER_CASTING_OUTPUTS,
    COPPER_CRAFT_OUTPUTS,
    COPPER_CRAFT_QUANTITIES,
    COPPER_MOLD_OUTPUTS,
    COPPER_VESSEL_DATA,
    COOKING_POT_MEALS,
    DEFAULT_FORAGE_OUTPUTS,
    DISCOVERY_ORDER,
    DRINK_VALUES,
    FISH_TRAP_OUTPUTS,
    FISH_TRAP_SOAK_RANGE,
    FISH_LOCATIONS,
    FOOD_SATURATION_VALUES,
    FOOD_SATURATION_STATS,
    FOOD_VALUES,
    DEFAULT_ITEM_WEIGHT,
    ITEM_WEIGHTS,
    KILN_FIRING,
    KILN_FUEL_VALUES,
    PREREQUISITE_ACTIONS,
    RAFT_EVENT_PASSING_SHIP,
    RAFT_PASSING_SHIP_DISTANCE_TRIGGERS,
    RAFT_PASSING_SHIP_WINDOW_MINUTES,
    RAFT_RESCUE_DISTANCE,
    RAFT_SIGNAL_PROGRESS_RANGES,
    RESOURCE_HARVESTS,
    SKILL_BY_ACTION,
    SNARE_TRAP_OUTPUTS,
    SNARE_TRAP_SOAK_RANGE,
    SPOIL_MINUTES,
    TIDE_POOL_OUTPUTS,
    TOOL_DURABILITY,
    TOOL_REQUIREMENTS,
    TOOL_WEAR,
    WATER_LOCATIONS,
    build_locations,
)
from .models import (
    Action,
    DEFAULT_STATS,
    ItemStack,
    Location,
    MAX_EVENT_LOG,
    PLAYER_STAT_KEYS,
    PlacedObject,
    Player,
    SATURATION_STAT_KEYS,
    World,
    WorldProcess,
    add_items,
    clamp,
    count_item,
    log_event,
    remove_items,
)


def new_world(seed: int = 1) -> World:
    world = World(seed=seed)
    world.locations = build_locations()
    for location_name, data in AREA_DEFS.items():
        for item, qty in data.get("ground", {}).items():
            add_items(world.locations[location_name].ground, item, int(qty))
    log_event(world, "Day 1 dawns on the beach.")
    return world


def world_snapshot(world: World, player_name: str) -> dict[str, Any]:
    player = world.players[player_name]
    current_location = world.locations[player.location]
    hour = world.minute // 60
    daylight = 6 <= hour < 18
    player_data = {
        "name": player.name,
        "location": player.location,
        "connected": player.connected,
        "status": player.status,
        "outcome_reason": player.outcome_reason,
        "ended_day": player.ended_day,
        "ended_minute": player.ended_minute,
        "needs": dict(player.needs),
        "stats": player_stat_values(world, player),
        "carrying": carrying_load(player),
        "carried": [item.to_dict() for item in player.carried],
        "current_action": player.current_action.to_dict() if player.current_action else None,
    }
    actions = available_actions(world, player_name)
    player_data["available_actions"] = actions
    players = {player_name: player_data}
    for other in world.players.values():
        if other.name == player_name or not other.connected or other.location != player.location:
            continue
        players[other.name] = public_player_data(other)
    current_location_data = current_location.to_dict()
    current_location_data["neighbors"] = list(AREA_NEIGHBORS.get(player.location, []))
    locations = {player.location: current_location_data}
    for name, location in world.locations.items():
        if name != player.location and location.discovered:
            locations[name] = {
                "name": name,
                "discovered": True,
                "features": [],
                "location_cards": [],
                "ground": [],
                "placed": [],
                "resources": {},
            }
    return {
        "day": world.day,
        "minute": world.minute,
        "weather": world.weather,
        "locations": locations,
        "players": players,
        "event_log": world.event_log[-MAX_EVENT_LOG:],
        "light": "daylight" if daylight else "firelit" if active_fire(current_location) else "dark",
        "paused": world.paused,
        "outcome": outcome_data(world),
        "raft": raft_data(world),
        "available_actions": actions,
    }


def public_player_data(player: Player) -> dict[str, Any]:
    return {
        "name": player.name,
        "location": player.location,
        "connected": player.connected,
        "status": player.status,
        "current_action": public_action_data(player.current_action),
    }


def public_action_data(action: Action | None) -> dict[str, Any] | None:
    if action is None:
        return None
    return {
        "name": action.name,
        "remaining_minutes": action.remaining_minutes,
        "total_minutes": action.total_minutes,
    }


def join_player(world: World, name: str) -> Player:
    if not name or "\n" in name:
        raise ValueError("invalid player name")
    existing = world.players.get(name)
    if existing and existing.connected:
        raise ValueError("player name already connected")
    if existing:
        existing.connected = True
        log_event(world, f"{name} reconnected.")
        return existing
    player = Player(name=name, connected=True)
    world.players[name] = player
    log_event(world, f"{name} joined the island.")
    return player


def disconnect_player(world: World, name: str) -> None:
    if name in world.players:
        world.players[name].connected = False
        log_event(world, f"{name} disconnected; their personal state is frozen.")


def outcome_data(world: World) -> dict[str, Any] | None:
    if world.outcome is None:
        return None
    return {
        "kind": world.outcome,
        "player": world.outcome_player,
        "reason": world.outcome_reason,
        "day": world.outcome_day,
        "minute": world.outcome_minute,
    }


def raft_data(world: World) -> dict[str, Any]:
    return {
        "distance": world.raft_distance,
        "rescue_distance": RAFT_RESCUE_DISTANCE,
        "event": world.raft_event,
        "event_remaining_minutes": world.raft_event_remaining_minutes,
        "signal_progress": world.raft_signal_progress,
        "missed_ships": world.raft_missed_ships,
    }


def finish_world(world: World, player: Player, outcome: str, status: str, reason: str) -> None:
    if player.status != "alive" or world.outcome is not None:
        return
    player.status = status
    player.outcome_reason = reason
    player.ended_day = world.day
    player.ended_minute = world.minute
    for other in world.players.values():
        other.current_action = None
    world.outcome = outcome
    world.outcome_player = player.name
    world.outcome_reason = reason
    world.outcome_day = world.day
    world.outcome_minute = world.minute
    if outcome == "win":
        log_event(world, f"{player.name} was rescued by a ship.")
    else:
        log_event(world, f"{player.name} died from {reason}.")


def death_reason(player: Player) -> str:
    thirsty = player.needs.get("thirst", 0) >= 90
    hungry = player.needs.get("hunger", 0) >= 95
    if thirsty and hungry:
        return "dehydration and starvation"
    if thirsty:
        return "dehydration"
    if hungry:
        return "starvation"
    return "injuries and exhaustion"


FISH_TRAP_LOCATIONS = {
    "atoll",
    "bay",
    "beach",
    "bird rock",
    "desolate beach",
    "mangrove forest",
    "rocks",
    "secret cove",
    "tidal cave",
}
FIRE_REQUIRED_ACTIONS = {
    "boil salt water",
    "boil water",
    "brew coffee",
    "brew ginger tea",
    "brew jasmine tea",
    "brew spider lily tea",
    "cook coconut fish",
    "cook fish",
    "cook meat",
    "cook sago cake",
    "cook sago flatbread",
    "cook yam curry",
    "fry puffballs",
    "prepare yam",
    "roast coffee beans",
}
SALT_BED_LIQUID_CAPACITY = 9600
SALT_BED_SALT_CAPACITY = 1920
SALT_BED_FILL_LIQUID = 1200
SALT_BED_TP_MINUTES = 15
KILN_TP_MINUTES = 15
KILN_MAX_FUEL = 96
KILN_MAX_TEMPERATURE = 900
HEAT_STRUCTURE_KINDS = {"kiln", "advanced kiln", "forge"}
HEAT_STRUCTURE_MAX_TEMPERATURES = {"kiln": 900, "advanced kiln": 1200, "forge": 1800}
HEAT_STRUCTURE_HEAT_GAINS = {"kiln": 8, "advanced kiln": 16, "forge": 24}
COPPER_SMELT_TEMPERATURE = 1100
COPPER_VEIN_USES = 3
VESSEL_DRINK_AMOUNT = 150
RAIN_VESSEL_FILL_AMOUNT = 50
WATER_RESERVOIR_CAPACITY = 12000
WATER_RESERVOIR_TP_MINUTES = 15
WATER_RESERVOIR_RAIN_FILL = 50
WELL_CAPACITY = 6000
WELL_TP_MINUTES = 15
WELL_BASE_FILL = 4
WELL_RAIN_FILL = 50
CISTERN_CAPACITY = 24000
CISTERN_TP_MINUTES = 15
CISTERN_RAIN_FILL = 50
TOOL_ALTERNATIVES = {
    "sharp stone": ("sharp stone", "copper knife"),
    "stone axe": ("stone axe", "copper axe"),
    "digging stick": ("digging stick", "copper shovel"),
    "heavy stone": ("heavy stone", "copper knife", "axe head", "shovel head", "spear head", "copper axe", "copper shovel"),
    "cooking pot": ("cooking pot", "copper jar"),
}
SHELTER_KINDS = {"shelter", "shed", "mud hut", "stone hut", "cellar"}
STORAGE_DATA = {
    "basket": {"storage_capacity": 1000, "slots": 4, "weight_reduction": 1000},
    "woven backpack": {
        "storage_capacity": 1000,
        "slots": 4,
        "weight_reduction": 1000,
        "equipped_weight_reduction": 250,
    },
    "storage chest": {"storage_capacity": 4000, "slots": 1, "weight_reduction": 4000},
    "supply chest": {"storage_capacity": 3000, "weight_reduction": 3000, "durability": 480, "max_durability": 480},
}
BASE_CARRY_CAPACITY = 2500
MAX_EFFECTIVE_CARRY = 4000
LOAD_BLOCKED_ACTIONS = {
    "explore",
    "forage",
    "forage tide pool",
    "gather",
    "harvest coconuts",
    "move",
    "sail raft",
    "swim",
    *RESOURCE_HARVESTS,
}
PICKABLE_STORAGE_KINDS = {"basket", "storage chest", "supply chest"}
SHELTER_STORAGE_CAPACITY = {"shed": 15000, "mud hut": 60000, "cellar": 30000}
SHELTER_PROTECTION = {
    "shed": {"rain_protection": 5, "heat_insulation": 3, "sun_protection": 6},
    "mud hut": {"rain_protection": 5, "heat_insulation": 3, "perceived_temperature": -1, "sun_protection": 6},
    "cellar": {"rain_protection": 5, "heat_insulation": 6, "perceived_temperature": -4, "sun_protection": 6, "cool_storage": 1},
}


def active_fire(location: Location) -> PlacedObject | None:
    return next((p for p in location.placed if p.kind in {"fire", "campfire"} and p.active and p.fuel > 0), None)


def kiln_at(location: Location) -> PlacedObject | None:
    return next((p for p in location.placed if p.kind in HEAT_STRUCTURE_KINDS), None)


def fuelable_kiln_at(location: Location) -> PlacedObject | None:
    return next(
        (
            p
            for p in location.placed
            if p.kind in HEAT_STRUCTURE_KINDS and int(p.data.get("fuel", 0)) < int(p.data.get("max_fuel", KILN_MAX_FUEL))
        ),
        None,
    )


def lightable_kiln_at(location: Location) -> PlacedObject | None:
    return next(
        (
            p
            for p in location.placed
            if p.kind in HEAT_STRUCTURE_KINDS and int(p.data.get("fuel", 0)) > 0
        ),
        None,
    )


def hot_kiln_at(location: Location, temperature: int = 600) -> PlacedObject | None:
    return next(
        (
            p
            for p in location.placed
            if p.kind in HEAT_STRUCTURE_KINDS and p.active and int(p.data.get("temperature", 0)) >= temperature
        ),
        None,
    )


def player_stat_values(world: World, player: Player) -> dict[str, int]:
    loc = world.locations[player.location]
    sheltered = sheltered_at(loc)
    conditions = player.conditions
    stats = dict(DEFAULT_STATS)
    stats.update(player.stats)
    stats.update(
        {
            "health": player.needs.get("health", 100),
            "hydration": 100 - player.needs.get("thirst", 0),
            "satiation": 100 - player.needs.get("hunger", 0),
            "stamina": 100 - player.needs.get("fatigue", 0),
            "morale": player.needs.get("morale", 50),
            "calm": 100 - player.needs.get("stress", 0),
            "wakefulness": 100 - player.needs.get("fatigue", 0),
            "comfort": 100 - conditions.get("pain", 0),
            "dryness": 100 - conditions.get("wetness", 0),
            "cleanliness": 100 - conditions.get("filth", 0),
            "wound_recovery": 100 - conditions.get("wounds", 0) * 25,
            "sun_safety": 100 - conditions.get("sunburn", 0),
            "back_comfort": 100 - conditions.get("back_pain", 0),
            "bite_comfort": 100 - conditions.get("bug_bites", 0),
            "foot_health": 100 - conditions.get("foot_damage", 0),
            "hand_health": 100 - conditions.get("hand_damage", 0),
            "blood_volume": 100 - conditions.get("blood_loss", 0),
            "bruise_recovery": 100 - conditions.get("bruising", 0),
            "burn_recovery": 100 - conditions.get("burns", 0),
            "eye_health": 100 - conditions.get("eye_damage", 0),
            "lung_health": 100 - conditions.get("lung_damage", 0),
            "heat_balance": 100 - conditions.get("hyperthermia", 0),
            "cold_balance": 100 - conditions.get("hypothermia", 0),
            "blood_pressure_stability": 100 - conditions.get("blood_pressure", 0),
            "fever_control": 100 - conditions.get("fever", 0),
            "stomach_stability": 100 - conditions.get("nausea", 0),
            "digestion": 100 - conditions.get("diarrhea", 0),
            "headache_comfort": 100 - conditions.get("headache", 0),
            "altered_mind_stability": 100 - conditions.get("altered_mind_state", 0),
            "mania_control": 100 - conditions.get("mania", 0),
            "derealization_control": 100 - conditions.get("derealization", 0),
            "isolation_resilience": 100 - conditions.get("isolation", 0),
            "sobriety": 100 - conditions.get("alcohol", 0),
            "sodium_balance": 100 - conditions.get("sodium_imbalance", 0),
            "quinine_safety": 100 - conditions.get("quinine", 0),
            "caffeine_balance": 100 - conditions.get("caffeine", 0),
            "capsaicin_cooling": 100 - conditions.get("capsaicin", 0),
            "psilocybin_grounding": 100 - conditions.get("psilocybin", 0),
            "food_poisoning_recovery": 100 - conditions.get("food_poisoning", 0),
            "venom_krait_resistance": 100 - conditions.get("venom_krait", 0),
        }
    )
    stats["appetite"] = min(stats.get("appetite", 80), 100 - conditions.get("nausea", 0))
    stats["mental_clarity"] = min(
        stats.get("mental_clarity", 100),
        100 - player.needs.get("stress", 0) // 3 - conditions.get("headache", 0) // 2,
    )
    stats["mental_structure"] = min(stats.get("mental_structure", 100), 100 - player.needs.get("stress", 0) // 2)
    stats["skin_integrity"] = min(
        stats.get("skin_integrity", 100),
        100 - conditions.get("sunburn", 0) // 2 - conditions.get("burns", 0) - conditions.get("filth", 0) // 4,
    )
    stats["blood_pressure_stability"] = min(stats["blood_pressure_stability"], stats["blood_volume"])
    stats["analgesia_coverage"] = min(stats.get("analgesia_coverage", 100), stats["comfort"])
    stats["spider_lily_recovery"] = min(stats.get("spider_lily_recovery", 100), stats["fever_control"], stats["immunity"])
    stats["ginger_settledness"] = min(stats.get("ginger_settledness", 100), stats["stomach_stability"], stats["digestion"])
    stats["antibiotic_coverage"] = min(stats.get("antibiotic_coverage", 100), stats["immunity"])
    stats["jasmine_restfulness"] = min(stats.get("jasmine_restfulness", 100), stats["calm"], stats["wakefulness"])
    if 10 <= world.minute // 60 < 17 and not sheltered and sun_exposed(player.location, loc):
        stats["sun_protection"] = min(stats.get("sun_protection", 100), 45 + stats.get("tanning", 75) // 4)
        stats["heat_protection"] = min(stats.get("heat_protection", 100), 70)
    if world.weather in {"rain", "storm"} and not sheltered:
        stats["rain_protection"] = min(stats.get("rain_protection", 100), 35)
    if (
        player.location in {"jungle", "deep jungle", "mangrove forest", "wetlands"}
        or (world.weather == "clear" and water_reservoir_mosquito_pressure(loc))
    ) and not active_fire(loc):
        repellent_floor = clamp(55 + conditions.get("bug_repellent", 0) // 2, 0, 100)
        stats["bug_protection"] = min(stats.get("bug_protection", 100), repellent_floor)
    stats["foot_protection"] = min(stats.get("foot_protection", 100), 100 - conditions.get("foot_damage", 0) // 2)
    return {key: clamp(int(stats.get(key, 100)), 0, 100) for key in PLAYER_STAT_KEYS}


def sun_exposed(location_name: str, location: Location) -> bool:
    return location_name in {"atoll", "bay", "beach", "bird rock", "desolate beach", "rocks"} or any(
        feature in location.features for feature in {"open sun", "sand", "hot ground", "cliffs"}
    )


def sheltered_at(location: Location) -> bool:
    return (
        any(p.kind in SHELTER_KINDS and p.active for p in location.placed)
        or "shelter walls" in location.features
    )


def has_object(location: Location, kind: str) -> bool:
    return any(p.kind == kind and p.active for p in location.placed)


def has_location_card(location: Location, *cards: str) -> bool:
    return any(card in location.location_cards for card in cards)


def salt_water_here(location: Location) -> bool:
    return any(feature in location.features for feature in {"sea", "seawater"}) or has_location_card(
        location, "sea", "seawater", "tide pool", "flooded tide pool"
    )


def unsafe_water_here(location_name: str, location: Location) -> bool:
    return (
        location_name in WATER_LOCATIONS
        or resource_available(location, "unsafe water")
        or has_location_card(location, "puddle", "dry puddle", "dry cave pond")
    )


def water_reservoir_with_water(location: Location) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in location.placed
            if obj.kind == "water reservoir" and obj.active and int(obj.data.get("liquid", 0)) > 0
        ),
        None,
    )


def cistern_with_water(location: Location) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in location.placed
            if obj.kind == "cistern" and obj.active and int(obj.data.get("liquid", 0)) > 0
        ),
        None,
    )


def well_with_water(location: Location) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in location.placed
            if obj.kind == "well" and obj.active and int(obj.data.get("liquid", 0)) > 0
        ),
        None,
    )


def water_reservoir_mosquito_pressure(location: Location) -> bool:
    reservoir = water_reservoir_with_water(location)
    if not reservoir:
        return False
    liquid = int(reservoir.data.get("liquid", 0))
    return 50 <= liquid < WATER_RESERVOIR_CAPACITY and int(reservoir.data.get("mosquito_protection", 0)) <= 0


def vessel_liquid_capacity(stack: ItemStack) -> int:
    return int(stack.data.get("liquid_capacity", 0))


def split_one_stack(stacks: list[ItemStack], stack: ItemStack) -> ItemStack:
    if stack.qty == 1:
        return stack
    stack.qty -= 1
    single = ItemStack(stack.item, 1, stack.age_minutes, stack.exposed, dict(stack.data))
    stacks.append(single)
    return single


def mark_carried_recent(player: Player, stack: ItemStack) -> None:
    for index, carried in enumerate(player.carried):
        if carried is stack:
            player.carried.append(player.carried.pop(index))
            return


def item_unit_weight(item: str) -> int:
    return int(ITEM_WEIGHTS.get(item, DEFAULT_ITEM_WEIGHT))


def stack_weight(stack: ItemStack) -> int:
    weight = item_unit_weight(stack.item) * stack.qty
    if stack.data.get("liquid"):
        weight += int(stack.data.get("liquid", 0)) * stack.qty
    return weight


def storage_contents(data: dict[str, Any]) -> list[ItemStack]:
    return [ItemStack.from_dict(stack) for stack in data.get("contents", [])]


def set_storage_contents(data: dict[str, Any], contents: list[ItemStack]) -> None:
    if contents:
        data["contents"] = [stack.to_dict() for stack in contents]
    else:
        data.pop("contents", None)


def storage_content_weight(data: dict[str, Any]) -> int:
    return sum(stack_weight(stack) for stack in storage_contents(data))


def stack_is_storage(stack: ItemStack) -> bool:
    return "storage_capacity" in stack.data


def stack_matches_storage_content(existing: ItemStack, incoming: ItemStack) -> bool:
    return (
        existing.item == incoming.item
        and existing.age_minutes == incoming.age_minutes
        and existing.exposed == incoming.exposed
        and existing.data == incoming.data
    )


def storage_can_accept_stack(data: dict[str, Any], stack: ItemStack) -> bool:
    if "storage_capacity" not in data or stack_is_storage(stack):
        return False
    if stack.data.get("liquid") and not stack.data.get("sealed"):
        return False
    contents = storage_contents(data)
    slots = data.get("slots")
    uses_new_slot = not any(stack_matches_storage_content(existing, stack) for existing in contents)
    if slots is not None and uses_new_slot and len(contents) >= int(slots):
        return False
    return storage_content_weight(data) + stack_weight(stack) <= int(data.get("storage_capacity", 0))


def add_stack_to_storage(data: dict[str, Any], stack: ItemStack) -> None:
    contents = storage_contents(data)
    add_items(contents, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
    set_storage_contents(data, contents)


def remove_stack_from_storage(data: dict[str, Any], item: str, qty: int = 1) -> list[ItemStack]:
    contents = storage_contents(data)
    removed = remove_items(contents, item, qty)
    set_storage_contents(data, contents)
    return removed


def carried_storage_for_stack(player: Player, stack: ItemStack) -> ItemStack | None:
    return next(
        (container for container in player.carried if stack_is_storage(container) and storage_can_accept_stack(container.data, stack)),
        None,
    )


def carried_storage_with_item(player: Player, item: str) -> ItemStack | None:
    return next(
        (
            container
            for container in player.carried
            if stack_is_storage(container) and any(stack.item == item for stack in storage_contents(container.data))
        ),
        None,
    )


def placed_storage_objects(location: Location) -> list[PlacedObject]:
    return [
        obj
        for obj in location.placed
        if obj.active and isinstance(obj.data, dict) and "storage_capacity" in obj.data
    ]


def pickable_storage_objects(location: Location) -> list[PlacedObject]:
    return [obj for obj in placed_storage_objects(location) if obj.kind in PICKABLE_STORAGE_KINDS]


def placed_storage_for_stack(location: Location, stack: ItemStack) -> PlacedObject | None:
    return next((obj for obj in placed_storage_objects(location) if storage_can_accept_stack(obj.data, stack)), None)


def placed_storage_with_item(location: Location, item: str) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in placed_storage_objects(location)
            if any(stack.item == item for stack in storage_contents(obj.data))
        ),
        None,
    )


def packable_carried_stacks(player: Player) -> list[ItemStack]:
    return [stack for stack in player.carried if not stack_is_storage(stack)]


def carrying_load(player: Player) -> dict[str, int | str | bool]:
    loose_weight = 0
    container_weight = 0
    packed_weight = 0
    relief = 0
    for stack in player.carried:
        if stack_is_storage(stack):
            own_weight = item_unit_weight(stack.item) * stack.qty
            container_weight += own_weight
            content_weight = storage_content_weight(stack.data)
            packed_weight += content_weight
            relief += min(content_weight, int(stack.data.get("weight_reduction", 0)))
            relief += min(own_weight, int(stack.data.get("equipped_weight_reduction", 0)))
        else:
            loose_weight += stack_weight(stack)
    raw_weight = loose_weight + container_weight + packed_weight
    effective_weight = max(0, raw_weight - relief)
    burden = max(0, min(100, effective_weight * 100 // BASE_CARRY_CAPACITY))
    status = "overburdened" if effective_weight > MAX_EFFECTIVE_CARRY else "heavy" if burden >= 100 else "loaded" if burden >= 70 else "light"
    return {
        "loose_weight": loose_weight,
        "container_weight": container_weight,
        "packed_weight": packed_weight,
        "relief": relief,
        "raw_weight": raw_weight,
        "effective_weight": effective_weight,
        "capacity": BASE_CARRY_CAPACITY,
        "max_effective_weight": MAX_EFFECTIVE_CARRY,
        "burden": burden,
        "status": status,
        "overburdened": effective_weight > MAX_EFFECTIVE_CARRY,
    }


def effective_weight_for_carried_stack(stack: ItemStack) -> int:
    if not stack_is_storage(stack):
        return stack_weight(stack)
    own_weight = item_unit_weight(stack.item) * stack.qty
    content_weight = storage_content_weight(stack.data)
    relief = min(content_weight, int(stack.data.get("weight_reduction", 0)))
    relief += min(own_weight, int(stack.data.get("equipped_weight_reduction", 0)))
    return max(0, own_weight + content_weight - relief)


def can_carry_loose_stack(player: Player, stack: ItemStack) -> bool:
    return int(carrying_load(player)["effective_weight"]) + effective_weight_for_carried_stack(stack) <= MAX_EFFECTIVE_CARRY


def vessel_fill_source(world: World, player: Player) -> tuple[str, int | None, str] | None:
    loc = world.locations[player.location]
    if cistern_with_water(loc):
        return "clean water", None, "cistern"
    if water_reservoir_with_water(loc):
        return "clean water", None, "water reservoir"
    if world.weather in {"rain", "storm"}:
        return "clean water", RAIN_VESSEL_FILL_AMOUNT, "rain"
    if well_with_water(loc):
        return "unsafe water", None, "well"
    if salt_water_here(loc):
        return "salt water", None, "salt water"
    if unsafe_water_here(player.location, loc):
        return "unsafe water", None, "unsafe water"
    return None


def carried_vessel_for_fill(player: Player, liquid_type: str) -> ItemStack | None:
    for stack in player.carried:
        capacity = vessel_liquid_capacity(stack)
        if not capacity:
            continue
        liquid = int(stack.data.get("liquid", 0))
        if liquid >= capacity:
            continue
        if liquid and stack.data.get("liquid_type") != liquid_type:
            continue
        return stack
    return None


def carried_vessel_with_liquid(player: Player) -> ItemStack | None:
    return next(
        (
            stack
            for stack in player.carried
            if vessel_liquid_capacity(stack) and int(stack.data.get("liquid", 0)) > 0
        ),
        None,
    )


def salt_bed_at(location: Location) -> PlacedObject | None:
    return next((p for p in location.placed if p.kind == "salt bed" and p.active), None)


def salt_bed_with_salt(location: Location) -> PlacedObject | None:
    return next(
        (
            p
            for p in location.placed
            if p.kind == "salt bed" and p.active and int(p.data.get("salt", 0)) >= 48
        ),
        None,
    )


def fish_trap_can_be_built(location_name: str, location: Location) -> bool:
    return location_name in FISH_TRAP_LOCATIONS or has_location_card(location, "sea", "tide pool", "flooded tide pool")


def snare_trap_can_be_built(location: Location) -> bool:
    return any(
        feature in location.features
        for feature in {"coconut palms", "trees", "dense trees", "small trees", "vines", "grass", "dry grass"}
    ) or has_location_card(location, "palm tree", "large tree", "small tree")


def sand_here(location: Location) -> bool:
    return "sand" in location.features or has_location_card(location, "sand")


def copper_vein_can_be_mined(location: Location) -> bool:
    return has_location_card(location, "copper vein") and int(location.explore_counts.get("copper_vein_uses", 0)) < COPPER_VEIN_USES


def advanced_kiln_can_be_built(location: Location) -> bool:
    return not any(obj.kind == "advanced kiln" for obj in location.placed)


def forge_can_be_built(location: Location) -> bool:
    return not any(obj.kind == "forge" for obj in location.placed)


def stone_hut_can_be_built(location: Location) -> bool:
    return not any(obj.kind == "stone hut" for obj in location.placed) and "shelter walls" not in location.features


def placed_structure_can_be_built(location: Location, kind: str) -> bool:
    return not any(obj.kind == kind and obj.active for obj in location.placed) and "shelter walls" not in location.features


def well_can_be_built(location_name: str, location: Location) -> bool:
    return location_name == "wetlands" and not any(obj.kind == "well" and obj.active for obj in location.placed)


def cistern_can_be_built(location: Location) -> bool:
    return not any(obj.kind == "cistern" and obj.active for obj in location.placed)


def ready_fish_trap(location: Location) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in location.placed
            if obj.kind == "fish trap" and obj.active and obj.data.get("ready") and obj.data.get("catch")
        ),
        None,
    )


def baitable_snare_trap(location: Location) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in location.placed
            if obj.kind == "snare trap" and obj.active and not obj.data.get("ready") and not obj.data.get("baited")
        ),
        None,
    )


def ready_snare_trap(location: Location) -> PlacedObject | None:
    return next(
        (
            obj
            for obj in location.placed
            if obj.kind == "snare trap" and obj.active and obj.data.get("ready") and obj.data.get("catch")
        ),
        None,
    )


def trap_soak_target(world: World, location_name: str, kind: str) -> int:
    low, high = FISH_TRAP_SOAK_RANGE if kind == "fish trap" else SNARE_TRAP_SOAK_RANGE
    step = max(1, world.minutes_per_tick)
    low_step = (low + step - 1) // step
    high_step = high // step
    rng = random.Random(f"{world.seed}:{kind}:{location_name}:{world.day}:{world.tick}")
    return rng.randint(low_step, high_step) * step


def available_actions(world: World, player_name: str) -> list[str]:
    player = world.players[player_name]
    if world.outcome is not None or player.status != "alive":
        return []
    loc = world.locations[player.location]
    actions = ["explore", "forage", "gather", "rest", "leisure"]
    actions.extend(["drop"] if player.carried else [])
    actions.extend(["pick up"] if loc.ground or pickable_storage_objects(loc) else [])
    if any(carried_storage_for_stack(player, stack) for stack in packable_carried_stacks(player)):
        actions.append("pack")
    if any(stack_is_storage(stack) and storage_contents(stack.data) for stack in player.carried):
        actions.append("unpack")
    if placed_storage_objects(loc) and any(placed_storage_for_stack(loc, stack) for stack in packable_carried_stacks(player)):
        actions.append("store")
    if any(storage_contents(obj.data) for obj in placed_storage_objects(loc)):
        actions.append("retrieve")
    water_here = player.location in WATER_LOCATIONS or has_location_card(
        loc, "sea", "seawater", "tide pool", "flooded tide pool"
    )
    actions.extend(["wash", "swim"] if water_here else [])
    actions.extend(
        ["move"] if discovered_neighbor_names(world, player.location) else []
    )
    if any(count_item(player.carried, item) for item in DRINK_VALUES):
        actions.append("drink")
    if any(count_item(player.carried, item) for item in FOOD_VALUES):
        actions.append("eat")
    if player.conditions.get("wounds", 0) and count_item(player.carried, "bandage leaves"):
        actions.append("treat wound")
    if player.location == "raft":
        if world.raft_event == RAFT_EVENT_PASSING_SHIP:
            actions.append("wave and shout")
            if player_has_tool_inputs(player, "signal with mirror"):
                actions.append("signal with mirror")
        else:
            actions.append("sail raft")
    if resource_available(loc, "coconut"):
        actions.append("harvest coconuts")
    for action, data in RESOURCE_HARVESTS.items():
        if resource_available(loc, str(data["resource"])) and action_prerequisites_met(world, player, action):
            actions.append(action)
    tide_pool_here = has_location_card(loc, "tide pool", "flooded tide pool")
    if tide_pool_here:
        actions.append("forage tide pool")
    if ready_fish_trap(loc):
        actions.append("check fish trap")
    if ready_snare_trap(loc):
        actions.append("check snare trap")
    for action in PREREQUISITE_ACTIONS:
        if action_prerequisites_met(world, player, action):
            actions.append(action)
    fish_here = player.location in FISH_LOCATIONS or tide_pool_here
    if fish_here and count_item(player.carried, "sharp stone"):
        actions.append("fish")
    if active_fire(loc):
        if count_item(player.carried, "sticks"):
            actions.append("tend fire")
    if carrying_load(player)["overburdened"]:
        actions = [action for action in actions if action not in LOAD_BLOCKED_ACTIONS]
    return order_actions_by_recent(actions, player.action_history)


def order_actions_by_recent(actions: list[str], action_history: list[str]) -> list[str]:
    available = list(dict.fromkeys(actions))
    available_set = set(available)
    recent = [action for action in dict.fromkeys(action_history) if action in available_set]
    return recent + [action for action in available if action not in recent]


def resource_available(location: Location, resource_name: str) -> bool:
    resource = location.resources.get(resource_name)
    if not resource:
        return False
    return bool(resource.get("infinite")) or int(resource.get("qty", 0)) > 0


def action_prerequisites_met(world: World, player: Player, action_name: str) -> bool:
    if not player_has_action_inputs(player, action_name):
        return False
    if not player_has_tool_inputs(player, action_name):
        return False
    loc = world.locations[player.location]
    if action_name in FIRE_REQUIRED_ACTIONS:
        return active_fire(loc) is not None
    if action_name == "collect salt water":
        return salt_water_here(loc)
    if action_name == "collect sand":
        return sand_here(loc)
    if action_name == "make quicklime":
        return hot_kiln_at(loc, 600) is not None
    if action_name == "mine copper ore":
        return copper_vein_can_be_mined(loc)
    if action_name == "smelt copper":
        return hot_kiln_at(loc, COPPER_SMELT_TEMPERATURE) is not None
    if action_name in COPPER_CASTING_OUTPUTS:
        return hot_kiln_at(loc, COPPER_SMELT_TEMPERATURE) is not None
    if action_name == "build advanced kiln":
        return advanced_kiln_can_be_built(loc)
    if action_name == "build forge":
        return forge_can_be_built(loc)
    if action_name == "build shed":
        return placed_structure_can_be_built(loc, "shed")
    if action_name == "build mud hut":
        return placed_structure_can_be_built(loc, "mud hut")
    if action_name == "build stone hut":
        return stone_hut_can_be_built(loc)
    if action_name == "build cellar":
        return placed_structure_can_be_built(loc, "cellar")
    if action_name == "build well":
        return well_can_be_built(player.location, loc)
    if action_name == "build cistern":
        return cistern_can_be_built(loc)
    if action_name == "fill vessel":
        source = vessel_fill_source(world, player)
        return source is not None and carried_vessel_for_fill(player, source[0]) is not None
    if action_name == "drink from vessel":
        return carried_vessel_with_liquid(player) is not None
    if action_name == "empty vessel":
        return carried_vessel_with_liquid(player) is not None
    if action_name in RAFT_SIGNAL_PROGRESS_RANGES:
        return world.raft_event == RAFT_EVENT_PASSING_SHIP and player.location == "raft"
    if action_name == "fill salt bed":
        bed = salt_bed_at(loc)
        return bed is not None and int(bed.data.get("liquid", 0)) < SALT_BED_LIQUID_CAPACITY
    if action_name == "scrape salt":
        return salt_bed_with_salt(loc) is not None
    if action_name == "dry fish":
        return has_object(loc, "drying rack")
    if action_name == "filter water":
        return has_object(loc, "water filter")
    if action_name == "build fish trap":
        return fish_trap_can_be_built(player.location, loc)
    if action_name == "build snare trap":
        return snare_trap_can_be_built(loc)
    if action_name == "bait snare trap":
        return baitable_snare_trap(loc) is not None
    if action_name == "fuel kiln":
        kiln = fuelable_kiln_at(loc)
        return kiln is not None and int(kiln.data.get("fuel", 0)) < int(kiln.data.get("max_fuel", KILN_MAX_FUEL)) and player_has_kiln_fuel(player)
    if action_name == "light kiln":
        kiln = lightable_kiln_at(loc)
        return kiln is not None and int(kiln.data.get("fuel", 0)) > 0 and active_fire(loc) is not None
    if action_name in KILN_FIRING:
        firing = KILN_FIRING[action_name]
        if firing["heat"] == "kiln":
            return hot_kiln_at(loc, int(firing["temperature"])) is not None
        return active_fire(loc) is not None or hot_kiln_at(loc, int(firing["temperature"])) is not None
    return True


def player_has_action_inputs(player: Player, action_name: str) -> bool:
    return all(count_item(player.carried, item) >= qty for item, qty in ACTION_INPUTS.get(action_name, {}).items())


def player_has_tool_inputs(player: Player, action_name: str) -> bool:
    return all(count_tool(player.carried, item) >= qty for item, qty in TOOL_REQUIREMENTS.get(action_name, {}).items())


def tool_options(item: str) -> tuple[str, ...]:
    return TOOL_ALTERNATIVES.get(item, (item,))


def count_tool(stacks: list[ItemStack], item: str) -> int:
    options = set(tool_options(item))
    return sum(stack.qty for stack in stacks if stack.item in options)


def player_has_kiln_fuel(player: Player) -> bool:
    return any(count_item(player.carried, item) for item in KILN_FUEL_VALUES)


def start_action(world: World, player_name: str, action_name: str, args: dict[str, Any] | None = None) -> None:
    args = args or {}
    if world.paused:
        raise ValueError("world is paused")
    player = world.players[player_name]
    if not player.connected:
        raise ValueError("player is disconnected")
    if world.outcome is not None:
        raise ValueError("game is over")
    if player.status != "alive":
        raise ValueError(f"player is {player.status}")
    if action_name not in ACTION_DURATIONS:
        raise ValueError(f"unknown action: {action_name}")
    blocks_player = ACTION_BLOCKS_PLAYER[action_name]
    if player.current_action and blocks_player:
        raise ValueError("player already has an action")
    if action_name not in available_actions(world, player_name):
        raise ValueError(f"action unavailable: {action_name}")
    loc = world.locations[player.location]
    if action_name in LOAD_BLOCKED_ACTIONS and carrying_load(player)["overburdened"]:
        raise ValueError("too overburdened for that action")
    if action_name == "gather":
        requested = args.get("item")
        allowed = gather_items_for_location(loc)
        if requested is not None and requested not in allowed:
            raise ValueError(f"cannot gather {requested} at {player.location}")
        args["item"] = str(requested or allowed[0])
    if action_name == "forage" and args.get("item") is not None:
        requested = str(args["item"])
        if requested not in loc.resources:
            raise ValueError(f"cannot forage {requested} at {player.location}")
        resource = loc.resources[requested]
        if resource.get("action", "forage") != "forage":
            raise ValueError(f"cannot forage {requested} at {player.location}")
        if not resource.get("infinite"):
            if int(resource.get("qty", 0)) <= 0:
                raise ValueError(f"{args['item']} is depleted")
            resource["qty"] = int(resource.get("qty", 0)) - 1
            args["reserved_resource"] = requested
    if action_name == "harvest coconuts":
        resource = loc.resources.get("coconut")
        if not resource or (not resource.get("infinite") and int(resource.get("qty", 0)) <= 0):
            raise ValueError(f"coconut is depleted at {player.location}")
        if not resource.get("infinite"):
            resource["qty"] = int(resource.get("qty", 0)) - 1
            args["reserved_resource"] = "coconut"
    if action_name in RESOURCE_HARVESTS:
        resource_name = str(RESOURCE_HARVESTS[action_name]["resource"])
        resource = loc.resources.get(resource_name)
        if not resource or (not resource.get("infinite") and int(resource.get("qty", 0)) <= 0):
            raise ValueError(f"{resource_name} is depleted at {player.location}")
        if not resource.get("infinite"):
            resource["qty"] = int(resource.get("qty", 0)) - 1
            args["reserved_resource"] = resource_name
    if action_name == "move" and "location" in args:
        destination = str(args["location"])
        if destination not in discovered_neighbor_names(world, player.location):
            raise ValueError("destination is not a discovered neighbor")
    if action_name == "fuel kiln":
        requested = args.get("item")
        fuel_items = [item for item in KILN_FUEL_VALUES if count_item(player.carried, item)]
        if requested is not None and requested not in fuel_items:
            raise ValueError(f"cannot fuel kiln with {requested}")
        args["item"] = str(requested or fuel_items[0])
    if action_name == "fill vessel":
        source = vessel_fill_source(world, player)
        if source is None:
            raise ValueError("no water source for vessel")
        requested = args.get("liquid_type")
        if requested is not None and requested != source[0]:
            raise ValueError(f"cannot fill vessel with {requested}")
        args["liquid_type"] = source[0]
        args["fill_amount"] = source[1]
        args["source"] = source[2]
    if action_name in {"pack", "store"}:
        item = args.get("item") or next((stack.item for stack in packable_carried_stacks(player)), None)
        qty = int(args.get("qty", 1))
        source = next((stack for stack in player.carried if stack.item == item and not stack_is_storage(stack)), None)
        if source is None:
            raise ValueError(f"missing {item}")
        candidate = ItemStack(source.item, min(qty, source.qty), source.age_minutes, source.exposed, deepcopy(source.data))
        if action_name == "pack" and carried_storage_for_stack(player, candidate) is None:
            raise ValueError(f"no carried container can hold {item}")
        if action_name == "store" and placed_storage_for_stack(loc, candidate) is None:
            raise ValueError(f"no placed storage can hold {item}")
        args["item"] = str(item)
        args["qty"] = candidate.qty
    if action_name == "unpack":
        item = args.get("item") or next(
            (
                content.item
                for container in player.carried
                if stack_is_storage(container)
                for content in storage_contents(container.data)
            ),
            None,
        )
        if item is None or carried_storage_with_item(player, str(item)) is None:
            raise ValueError(f"no carried container has {item}")
        args["item"] = str(item)
        args["qty"] = int(args.get("qty", 1))
    if action_name == "retrieve":
        item = args.get("item") or next(
            (content.item for obj in placed_storage_objects(loc) for content in storage_contents(obj.data)),
            None,
        )
        source_storage = placed_storage_with_item(loc, str(item)) if item is not None else None
        if source_storage is None:
            raise ValueError(f"no placed storage has {item}")
        stack = next(content for content in storage_contents(source_storage.data) if content.item == item)
        candidate = ItemStack(stack.item, min(int(args.get("qty", 1)), stack.qty), stack.age_minutes, stack.exposed, deepcopy(stack.data))
        if not can_carry_loose_stack(player, candidate):
            raise ValueError(f"{item} is too heavy to retrieve")
        args["item"] = str(item)
        args["qty"] = candidate.qty
    reserved = []
    if action_name in ACTION_INPUTS:
        for item, qty in ACTION_INPUTS[action_name].items():
            if action_name == "fish":
                if count_item(player.carried, item) < qty:
                    raise ValueError(f"missing {item}")
                continue
            reserved.extend(remove_items(player.carried, item, qty))
    if action_name == "pick up":
        item = args.get("item") or (loc.ground[0].item if loc.ground else pickable_storage_objects(loc)[0].kind if pickable_storage_objects(loc) else None)
        source = next((stack for stack in loc.ground if stack.item == item), None)
        if source is not None:
            candidate = ItemStack(source.item, min(int(args.get("qty", 1)), source.qty), source.age_minutes, source.exposed, deepcopy(source.data))
            if not can_carry_loose_stack(player, candidate):
                raise ValueError(f"{item} is too heavy to pick up")
            reserved.extend(remove_items(loc.ground, item, int(args.get("qty", 1))))
        else:
            obj = next((placed for placed in pickable_storage_objects(loc) if placed.kind == item), None)
            if obj is None:
                raise ValueError(f"missing {item}")
            candidate = ItemStack(obj.kind, 1, data=deepcopy(obj.data))
            if not can_carry_loose_stack(player, candidate):
                raise ValueError(f"{item} is too heavy to pick up")
            loc.placed.remove(obj)
            args["placed_storage"] = True
            reserved.append(candidate)
    if action_name == "drop":
        item = args.get("item") or (player.carried[0].item if player.carried else None)
        reserved.extend(remove_items(player.carried, item, int(args.get("qty", 1))))
    if action_name in {"pack", "store"}:
        reserved.extend(remove_items(player.carried, str(args["item"]), int(args.get("qty", 1))))
    if action_name == "fuel kiln":
        reserved.extend(remove_items(player.carried, str(args["item"]), 1))
    total = ACTION_DURATIONS[action_name]
    action = Action(action_name, total, total, args, reserved)
    player.action_history = [action_name, *[action for action in player.action_history if action != action_name]]
    log_event(world, f"{player.name} started {action_name}.")
    if blocks_player:
        player.current_action = action
    else:
        complete_action(world, player, action)


def cancel_action(world: World, player_name: str) -> None:
    player = world.players[player_name]
    action = player.current_action
    if not action:
        return
    loc = world.locations[player.location]
    target = loc.ground if action.name == "pick up" else player.carried
    if action.name == "drop":
        target = player.carried
    if action.args.get("reserved_resource"):
        resource = loc.resources[action.args["reserved_resource"]]
        resource["qty"] = min(int(resource.get("capacity", resource.get("qty", 0))), int(resource.get("qty", 0)) + 1)
    for stack in action.reserved:
        if action.name == "pick up" and action.args.get("placed_storage"):
            loc.placed.append(PlacedObject(stack.item, active=True, data=deepcopy(stack.data)))
            continue
        add_items(target, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
    player.current_action = None
    log_event(world, f"{player.name} cancelled {action.name}.")


def tick_world(world: World) -> bool:
    if world.paused or world.outcome is not None or not any(player.connected for player in world.players.values()):
        return False
    dt = world.minutes_per_tick
    old_day = world.day
    world.tick += 1
    world.minute += dt
    while world.minute >= 1440:
        world.minute -= 1440
        world.day += 1
        log_event(world, f"Day {world.day} begins.")
    update_weather(world)
    raft_event_was_active = world.raft_event == RAFT_EVENT_PASSING_SHIP
    for player in list(world.players.values()):
        if player.connected:
            update_player_needs(world, player, dt)
            if world.outcome is not None:
                break
            advance_action(world, player, dt)
            if world.outcome is not None:
                break
    if world.outcome is not None:
        world.event_log = world.event_log[-MAX_EVENT_LOG:]
        return world.day != old_day
    update_world_processes(world, dt)
    update_raft_event(world, dt, was_active=raft_event_was_active)
    update_location_resources(world, dt)
    update_items(world, dt)
    world.event_log = world.event_log[-MAX_EVENT_LOG:]
    return world.day != old_day


def update_weather(world: World) -> None:
    slot = (world.day * 1440 + world.minute) // 180
    rng = random.Random(world.seed + slot)
    rain_chance = 0.45 if world.season == "wet" else 0.18
    if rng.random() < rain_chance:
        world.weather = "rain"
    elif rng.random() < 0.15:
        world.weather = "storm"
    else:
        world.weather = "clear"
    world.season = "wet" if (world.day // 7) % 2 else "dry"


def update_player_needs(world: World, player: Player, dt: int) -> None:
    if player.needs.get("health", 100) <= 0:
        finish_world(world, player, "loss", "dead", death_reason(player))
        return
    current_time = world.day * 1440 + world.minute
    previous_time = current_time - dt
    player.needs["thirst"] = clamp(player.needs["thirst"] + current_time // 3 - previous_time // 3, 0, 100)
    player.needs["hunger"] = clamp(player.needs["hunger"] + current_time // 6 - previous_time // 6, 0, 100)
    player.needs["fatigue"] = clamp(player.needs["fatigue"] + current_time // 12 - previous_time // 12, 0, 100)
    if player.needs["thirst"] >= 90 or player.needs["hunger"] >= 95:
        interval = 180 if player.needs["thirst"] >= 90 and player.needs["hunger"] >= 95 else 360
        health_loss = current_time // interval - previous_time // interval
        player.needs["health"] = clamp(player.needs["health"] - health_loss)
    if player.needs["health"] <= 0:
        finish_world(world, player, "loss", "dead", death_reason(player))
        return
    loc = world.locations[player.location]
    sheltered = sheltered_at(loc)
    if world.weather in {"rain", "storm"} and not sheltered:
        player.conditions["wetness"] = clamp(player.conditions["wetness"] + 2)
    if world.minute % 60 == 0:
        dry = 10 if sheltered or active_fire(loc) else 4
        player.conditions["wetness"] = clamp(player.conditions["wetness"] - dry)
        player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + (0 if sheltered else 1))
        if sun_exposed(player.location, loc) and 10 <= world.minute // 60 < 17 and not sheltered:
            player.conditions["sunburn"] = clamp(player.conditions.get("sunburn", 0) + 2)
            player.conditions["hyperthermia"] = clamp(player.conditions.get("hyperthermia", 0) + 1)
            player.conditions["headache"] = clamp(player.conditions.get("headache", 0) + 1)
            player.stats["tanning"] = clamp(player.stats.get("tanning", 75) + 1)
        else:
            player.conditions["sunburn"] = clamp(player.conditions.get("sunburn", 0) - 1)
            player.conditions["hyperthermia"] = clamp(player.conditions.get("hyperthermia", 0) - 2)
        if world.weather in {"rain", "storm"} and player.conditions.get("wetness", 0) >= 60:
            player.conditions["hypothermia"] = clamp(player.conditions.get("hypothermia", 0) + 1)
        else:
            player.conditions["hypothermia"] = clamp(player.conditions.get("hypothermia", 0) - (2 if active_fire(loc) else 1))
        if (
            player.location in {"jungle", "deep jungle", "mangrove forest", "wetlands"}
            or (world.weather == "clear" and water_reservoir_mosquito_pressure(loc))
        ) and not active_fire(loc):
            player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) + 2)
        else:
            player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) - 1)
        if player.conditions.get("nausea", 0):
            player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) - 1)
        if player.conditions.get("diarrhea", 0):
            player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) - 1)
        if player.conditions.get("food_poisoning", 0):
            player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) - 2)
        if player.conditions.get("bug_repellent", 0):
            player.conditions["bug_repellent"] = clamp(player.conditions.get("bug_repellent", 0) - 4)
        for condition in [
            "altered_mind_state",
            "mania",
            "derealization",
            "isolation",
            "alcohol",
            "sodium_imbalance",
            "quinine",
            "caffeine",
            "capsaicin",
            "psilocybin",
            "venom_krait",
        ]:
            if player.conditions.get(condition, 0):
                player.conditions[condition] = clamp(player.conditions.get(condition, 0) - 1)
        if player.conditions.get("headache", 0) and not sun_exposed(player.location, loc):
            player.conditions["headache"] = clamp(player.conditions.get("headache", 0) - 1)
        if player.conditions.get("blood_loss", 0):
            player.conditions["blood_pressure"] = clamp(player.conditions.get("blood_loss", 0) + player.conditions.get("pain", 0) // 3)
        else:
            player.conditions["blood_pressure"] = clamp(player.conditions.get("blood_pressure", 0) - 2)
        player.stats["entertainment"] = clamp(player.stats.get("entertainment", 50) - 1)
        connected_players = sum(1 for other in world.players.values() if other.connected)
        companionship_delta = 2 if connected_players > 1 else -1
        player.stats["companionship"] = clamp(player.stats.get("companionship", 65) + companionship_delta)
        player.stats["courage"] = clamp(player.stats.get("courage", 60) + (1 if 6 <= world.minute // 60 < 18 else -1))
        if player.conditions.get("wounds", 0) or player.conditions.get("filth", 0) >= 50:
            player.stats["immunity"] = clamp(player.stats.get("immunity", 85) - 1)
        else:
            player.stats["immunity"] = clamp(player.stats.get("immunity", 85) + 1)
        for stat in SATURATION_STAT_KEYS:
            player.stats[stat] = clamp(player.stats.get(stat, 100) + 3)
        if player.conditions.get("wounds", 0) and not player.conditions.get("treated_wound", 0):
            player.conditions["pain"] = clamp(player.conditions.get("pain", 0) + 3)
    if world.minute == 6 * 60 and player.conditions.get("treated_wound", 0):
        player.conditions["wounds"] = clamp(player.conditions.get("wounds", 0) - 1)
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 10)
        player.conditions["blood_loss"] = clamp(player.conditions.get("blood_loss", 0) - 15)
        player.conditions["treated_wound"] = 0


def advance_action(world: World, player: Player, dt: int) -> None:
    action = player.current_action
    if not action:
        return
    action.remaining_minutes -= dt
    if action.remaining_minutes <= 0:
        complete_action(world, player, action)
        player.current_action = None


def start_passing_ship_event(world: World, player: Player) -> None:
    world.raft_event = RAFT_EVENT_PASSING_SHIP
    world.raft_event_remaining_minutes = RAFT_PASSING_SHIP_WINDOW_MINUTES
    world.raft_signal_progress = 0
    player.needs["morale"] = clamp(player.needs.get("morale", 50) + 4)
    log_event(world, "A passing ship appeared near the raft.")


def update_raft_event(world: World, dt: int, *, was_active: bool) -> None:
    if not was_active or world.raft_event != RAFT_EVENT_PASSING_SHIP:
        return
    world.raft_event_remaining_minutes = max(0, world.raft_event_remaining_minutes - dt)
    if world.raft_event_remaining_minutes <= 0:
        world.raft_event = None
        world.raft_signal_progress = 0
        world.raft_missed_ships += 1
        log_event(world, "The passing ship slipped beyond signaling range.")


def advance_raft_voyage(world: World, player: Player, minutes: int) -> None:
    previous_distance = world.raft_distance
    world.raft_distance = min(RAFT_RESCUE_DISTANCE, world.raft_distance + minutes)
    log_event(world, f"{player.name} sailed the raft to distance {world.raft_distance}.")
    if world.raft_distance >= RAFT_RESCUE_DISTANCE:
        log_event(world, "A ship is coming straight toward the raft, horn sounding.")
        finish_world(world, player, "win", "escaped", "rescued after completing raft voyage")
        return
    if world.raft_event is None:
        for marker in RAFT_PASSING_SHIP_DISTANCE_TRIGGERS:
            if previous_distance < marker <= world.raft_distance:
                start_passing_ship_event(world, player)
                return


def signal_passing_ship(world: World, player: Player, action_name: str) -> None:
    low, high = RAFT_SIGNAL_PROGRESS_RANGES[action_name]
    rng = random.Random(f"{world.seed}:raft-signal:{world.day}:{world.tick}:{player.name}:{action_name}")
    gain = rng.randint(low, high)
    world.raft_signal_progress = min(100, world.raft_signal_progress + gain)
    log_event(world, f"{player.name} signaled the passing ship ({world.raft_signal_progress}/100).")
    if world.raft_signal_progress >= 100:
        finish_world(world, player, "win", "escaped", "rescued by passing ship")


def complete_action(world: World, player: Player, action: Action) -> None:
    loc = world.locations[player.location]
    name = action.name
    for stack in action.reserved:
        if name == "pick up":
            add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
        elif name == "drop":
            add_items(loc.ground, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
        elif name == "pack":
            container = carried_storage_for_stack(player, stack)
            if container:
                add_stack_to_storage(container.data, stack)
                mark_carried_recent(player, container)
        elif name == "store":
            storage = placed_storage_for_stack(loc, stack)
            if storage:
                add_stack_to_storage(storage.data, stack)
    if name == "unpack":
        container = carried_storage_with_item(player, str(action.args["item"]))
        if container:
            for stack in remove_stack_from_storage(container.data, str(action.args["item"]), int(action.args.get("qty", 1))):
                add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
            mark_carried_recent(player, container)
    elif name == "retrieve":
        storage = placed_storage_with_item(loc, str(action.args["item"]))
        if storage:
            for stack in remove_stack_from_storage(storage.data, str(action.args["item"]), int(action.args.get("qty", 1))):
                add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
    player.needs["fatigue"] = clamp(
        player.needs["fatigue"]
        + {
            "forage": 5,
            "gather": 4,
            "explore": 8,
            "move": 4,
            "sail raft": 10,
            "wave and shout": 3,
            "signal with mirror": 2,
            "wash": 2,
            "swim": 8,
            "rest": 0,
            "leisure": 1,
            "forage tide pool": 4,
            "harvest coconuts": 9,
            "harvest aloe vera": 2,
            "harvest lemongrass": 2,
            "harvest ginger": 3,
            "harvest spider lily": 4,
            "harvest snakegrass": 5,
            "dig wild yam": 12,
            "collect bananas": 4,
            "cut nipa fruit": 4,
            "cut sago palm": 25,
            "dig up mud": 4,
            "dig up dirt": 4,
            "harvest coffee berries": 4,
            "harvest chilies": 3,
            "harvest jasmine": 1,
            "harvest assorted mushrooms": 2,
            "harvest puffballs": 2,
            "harvest magic mushrooms": 2,
            "craft sharp stone": 3,
            "crack coconut": 2,
            "weave cord": 3,
            "weave rope": 5,
            "weave palm fronds": 4,
            "craft woven basket": 5,
            "craft woven backpack": 5,
            "add rope to basket": 2,
            "detach rope from woven backpack": 1,
            "place basket": 1,
            "pack": 1,
            "unpack": 1,
            "store": 1,
            "retrieve": 1,
            "craft stone axe": 4,
            "craft digging stick": 4,
            "make wood shavings": 2,
            "make aloe gel": 2,
            "brew ginger tea": 1,
            "brew spider lily tea": 1,
            "brew jasmine tea": 1,
            "make bug repellent": 2,
            "prepare yam": 3,
            "extract nipa seeds": 2,
            "extract coffee beans": 1,
            "roast coffee beans": 1,
            "brew coffee": 1,
            "split sago log": 25,
            "scrape sago pith": 9,
            "soak sago sawdust": 1,
            "grind soaked sago": 2,
            "dry sago pulp": 1,
            "cook sago flatbread": 1,
            "collect sand": 1,
            "make quicklime": 1,
            "mix mortar": 5,
            "make clay": 2,
            "make mud brick": 2,
            "make mud": 1,
            "crush dirt": 3,
            "mix clay": 1,
            "mine copper ore": 20,
            "smelt copper": 1,
            "shape knife mold": 3,
            "shape axe mold": 4,
            "shape shovel mold": 4,
            "shape spear mold": 3,
            "cast copper knife": 1,
            "cast axe head": 1,
            "cast shovel head": 1,
            "cast spear head": 1,
            "craft copper axe": 8,
            "craft copper shovel": 5,
            "craft copper spear": 5,
            "hammer copper sheet": 10,
            "make copper needles": 4,
            "craft copper bottle": 8,
            "craft copper jar": 8,
            "shape clay bowl": 2,
            "shape clay jar": 3,
            "shape cooking pot": 4,
            "shape clay vase": 6,
            "build kiln": 18,
            "build advanced kiln": 8,
            "build forge": 8,
            "build water reservoir": 18,
            "build well": 35,
            "build cistern": 45,
            "fuel kiln": 1,
            "light kiln": 2,
            "fire clay bowl": 1,
            "fire clay jar": 1,
            "fire cooking pot": 1,
            "fire clay vase": 1,
            "collect salt water": 2,
            "boil salt water": 1,
            "build salt bed": 12,
            "fill salt bed": 2,
            "scrape salt": 2,
            "salt fish": 2,
            "salt meat": 2,
            "start fire": 6,
            "fish": 8,
            "cook meat": 1,
            "dry fish": 2,
            "filter water": 1,
            "build campfire": 8,
            "craft leaf bed": 4,
            "build raincatcher": 10,
            "build shelter": 14,
            "build shed": 30,
            "build mud hut": 45,
            "build stone hut": 42,
            "build cellar": 55,
            "build drying rack": 10,
            "build storage chest": 8,
            "build supply chest": 12,
            "build fish trap": 10,
            "check fish trap": 2,
            "build snare trap": 6,
            "bait snare trap": 1,
            "check snare trap": 2,
            "build water filter": 10,
            "build solar still": 12,
        }.get(name, 0)
    )
    load = carrying_load(player)
    if int(load["burden"]) >= 70 and name not in {"rest", "leisure"}:
        player.needs["fatigue"] = clamp(player.needs["fatigue"] + max(1, (int(load["burden"]) - 60) // 20))
    if name == "sail raft":
        advance_raft_voyage(world, player, action.total_minutes)
    elif name in RAFT_SIGNAL_PROGRESS_RANGES:
        signal_passing_ship(world, player, name)
    if world.outcome is not None:
        return
    player.conditions["filth"] = clamp(
        player.conditions.get("filth", 0)
        + {
            "forage": 4,
            "gather": 3,
            "explore": 5,
            "move": 2,
            "harvest coconuts": 3,
            "harvest aloe vera": 1,
            "harvest lemongrass": 1,
            "harvest ginger": 2,
            "harvest spider lily": 2,
            "harvest snakegrass": 4,
            "dig wild yam": 40,
            "collect bananas": 2,
            "cut nipa fruit": 2,
            "cut sago palm": 6,
            "dig up mud": 10,
            "dig up dirt": 10,
            "collect sand": 2,
            "mix mortar": 12,
            "make clay": 15,
            "make mud brick": 15,
            "make mud": 10,
            "crush dirt": 15,
            "mix clay": 15,
            "mine copper ore": 8,
            "shape knife mold": 8,
            "shape axe mold": 10,
            "shape shovel mold": 10,
            "shape spear mold": 8,
            "cast copper knife": 4,
            "cast axe head": 4,
            "cast shovel head": 4,
            "cast spear head": 4,
            "craft copper axe": 6,
            "craft copper shovel": 6,
            "craft copper spear": 6,
            "hammer copper sheet": 8,
            "make copper needles": 4,
            "craft copper bottle": 8,
            "craft copper jar": 8,
            "shape clay bowl": 8,
            "shape clay jar": 8,
            "shape cooking pot": 10,
            "shape clay vase": 12,
            "build kiln": 10,
            "build advanced kiln": 10,
            "build forge": 10,
            "build water reservoir": 12,
            "build well": 35,
            "build cistern": 45,
            "fuel kiln": 3,
            "build salt bed": 4,
            "scrape salt": 2,
            "salt fish": 2,
            "salt meat": 2,
            "cut palm fronds": 2,
            "hew log": 6,
            "build shed": 8,
            "build mud hut": 25,
            "build cellar": 35,
            "harvest coffee berries": 2,
            "harvest chilies": 1,
            "harvest assorted mushrooms": 2,
            "harvest puffballs": 2,
            "harvest magic mushrooms": 2,
            "fish": 2,
            "build shelter": 5,
            "build stone hut": 10,
            "build raincatcher": 4,
            "build drying rack": 4,
            "build fish trap": 3,
            "build snare trap": 3,
            "build water filter": 3,
            "build solar still": 4,
        }.get(name, 0)
    )
    player.conditions["foot_damage"] = clamp(
        player.conditions.get("foot_damage", 0)
        + {
            "explore": 2,
            "move": 1,
            "harvest coconuts": 3,
            "cut sago palm": 2,
            "dig wild yam": 2,
            "dig up mud": 1,
            "dig up dirt": 1,
            "forage tide pool": 1,
        }.get(name, 0)
    )
    player.conditions["hand_damage"] = clamp(
        player.conditions.get("hand_damage", 0)
        + {
            "gather": 1,
            "harvest coconuts": 2,
            "harvest ginger": 1,
            "harvest spider lily": 1,
            "harvest snakegrass": 2,
            "dig wild yam": 25,
            "collect bananas": 1,
            "cut nipa fruit": 1,
            "cut sago palm": 8,
            "dig up mud": 2,
            "dig up dirt": 2,
            "make clay": 1,
            "make mud brick": 1,
            "crush dirt": 1,
            "mine copper ore": 25,
            "shape knife mold": 1,
            "shape axe mold": 2,
            "shape shovel mold": 2,
            "shape spear mold": 1,
            "hammer copper sheet": 60,
            "make copper needles": 2,
            "craft copper bottle": 2,
            "craft copper jar": 2,
            "scrape salt": 1,
            "harvest coffee berries": 1,
            "harvest chilies": 1,
            "harvest assorted mushrooms": 1,
            "harvest puffballs": 1,
            "harvest magic mushrooms": 1,
            "craft sharp stone": 1,
            "weave cord": 1,
            "weave palm fronds": 1,
            "craft woven basket": 1,
            "craft woven backpack": 1,
            "add rope to basket": 1,
            "detach rope from woven backpack": 1,
            "craft stone axe": 2,
            "make wood shavings": 1,
            "split sago log": 8,
            "grind soaked sago": 1,
            "build shelter": 2,
            "build shed": 5,
            "build mud hut": 10,
            "build stone hut": 4,
            "build cellar": 8,
            "build raincatcher": 2,
            "build drying rack": 2,
            "build storage chest": 2,
            "build supply chest": 3,
            "build fish trap": 2,
            "build snare trap": 1,
            "build water filter": 1,
            "build solar still": 2,
        }.get(name, 0)
    )
    if name in {"dig up mud", "make mud"}:
        player.conditions["wetness"] = clamp(player.conditions.get("wetness", 0) + 20)
    if name in {"explore", "move", "forage tide pool", "harvest coconuts"}:
        player.stats["foot_callouses"] = clamp(player.stats.get("foot_callouses", 70) + 1)
    if name in {
        "gather",
        "craft sharp stone",
            "weave cord",
            "weave rope",
            "weave palm fronds",
            "craft woven basket",
            "craft woven backpack",
            "add rope to basket",
            "detach rope from woven backpack",
            "place basket",
            "craft digging stick",
            "make wood shavings",
            "collect sand",
            "mix mortar",
            "shape clay bowl",
            "shape clay jar",
            "shape cooking pot",
            "shape clay vase",
            "shape knife mold",
            "shape axe mold",
            "shape shovel mold",
            "shape spear mold",
            "cast copper knife",
            "cast axe head",
            "cast shovel head",
            "cast spear head",
            "craft copper axe",
            "craft copper shovel",
            "craft copper spear",
            "hammer copper sheet",
            "make copper needles",
            "craft copper bottle",
            "craft copper jar",
            "fuel kiln",
        } or name.startswith("build ") or name in RESOURCE_HARVESTS:
        player.stats["hand_callouses"] = clamp(player.stats.get("hand_callouses", 70) + 1)
    skill = SKILL_BY_ACTION.get(name)
    if skill:
        player.skills[skill] = player.skills.get(skill, 0) + 1
    if name == "forage":
        forage_outputs = forage_outputs_for_location(loc)
        item = action.args.get("item") or forage_outputs[(world.tick + len(player.name)) % len(forage_outputs)]
        if item == "coconut" and not action.args.get("reserved_resource"):
            resource = loc.resources.get("coconut")
            if resource and not resource.get("infinite"):
                if int(resource.get("qty", 0)) <= 0:
                    item = "leaves"
                else:
                    resource["qty"] = int(resource.get("qty", 0)) - 1
        add_items(player.carried, item, 1)
        if world.weather == "storm":
            player.conditions["wounds"] = clamp(player.conditions.get("wounds", 0) + 1)
            player.conditions["pain"] = clamp(player.conditions.get("pain", 0) + 5)
            player.conditions["bruising"] = clamp(player.conditions.get("bruising", 0) + 5)
            player.conditions["blood_loss"] = clamp(player.conditions.get("blood_loss", 0) + 4)
    elif name == "forage tide pool":
        item = TIDE_POOL_OUTPUTS[(world.tick + len(player.name)) % len(TIDE_POOL_OUTPUTS)]
        add_items(player.carried, item, 1)
    elif name == "gather":
        item = action.args.get("item") or gather_items_for_location(loc)[0]
        add_items(player.carried, item, 1)
    elif name == "harvest coconuts":
        add_items(player.carried, "coconut", 1)
    elif name in RESOURCE_HARVESTS:
        rng = random.Random(f"{world.seed}:{world.tick}:{world.day}:{player.name}:{name}")
        for item, min_qty, max_qty in RESOURCE_HARVESTS[name]["outputs"]:
            qty = min_qty if min_qty == max_qty else rng.randint(min_qty, max_qty)
            add_items(player.carried, item, qty)
    elif name == "explore":
        discover_next(world, player)
    elif name == "move":
        dest = action.args.get("location")
        if not dest:
            dest = discovered_neighbor_names(world, player.location)[0]
        player.location = dest
    elif name in {"wash", "swim"}:
        player.needs["stress"] = clamp(player.needs["stress"] - 8)
        player.conditions["wetness"] = clamp(player.conditions["wetness"] + (25 if name == "swim" else 12))
        player.conditions["filth"] = clamp(player.conditions.get("filth", 0) - (45 if name == "wash" else 20))
        player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) - 4)
        player.conditions["hyperthermia"] = clamp(player.conditions.get("hyperthermia", 0) - (10 if name == "swim" else 4))
    elif name == "drink":
        consume_drink(player)
    elif name == "fill vessel":
        liquid_type = str(action.args["liquid_type"])
        fill_amount = action.args.get("fill_amount")
        vessel = carried_vessel_for_fill(player, liquid_type)
        if vessel:
            vessel = split_one_stack(player.carried, vessel)
            capacity = vessel_liquid_capacity(vessel)
            liquid = int(vessel.data.get("liquid", 0))
            amount = capacity - liquid if fill_amount is None else min(int(fill_amount), capacity - liquid)
            if action.args.get("source") == "water reservoir":
                reservoir = water_reservoir_with_water(loc)
                amount = min(amount, int(reservoir.data.get("liquid", 0)) if reservoir else 0)
            if action.args.get("source") == "cistern":
                cistern = cistern_with_water(loc)
                amount = min(amount, int(cistern.data.get("liquid", 0)) if cistern else 0)
            if action.args.get("source") == "well":
                well = well_with_water(loc)
                amount = min(amount, int(well.data.get("liquid", 0)) if well else 0)
            vessel.data["liquid_type"] = liquid_type
            vessel.data["liquid"] = liquid + amount
            vessel.data["liquid_capacity"] = capacity
            if action.args.get("source") == "water reservoir":
                reservoir = water_reservoir_with_water(loc)
                if reservoir:
                    reservoir.data["liquid"] = max(0, int(reservoir.data.get("liquid", 0)) - amount)
            if action.args.get("source") == "cistern":
                cistern = cistern_with_water(loc)
                if cistern:
                    cistern.data["liquid"] = max(0, int(cistern.data.get("liquid", 0)) - amount)
            if action.args.get("source") == "well":
                well = well_with_water(loc)
                if well:
                    well.data["liquid"] = max(0, int(well.data.get("liquid", 0)) - amount)
            mark_carried_recent(player, vessel)
    elif name == "drink from vessel":
        vessel = carried_vessel_with_liquid(player)
        if vessel:
            vessel = split_one_stack(player.carried, vessel)
            liquid_type = str(vessel.data.get("liquid_type", "clean water"))
            amount = min(VESSEL_DRINK_AMOUNT, int(vessel.data.get("liquid", 0)))
            vessel.data["liquid"] = int(vessel.data.get("liquid", 0)) - amount
            if vessel.data["liquid"] <= 0:
                vessel.data["liquid"] = 0
                vessel.data.pop("liquid_type", None)
            if liquid_type == "clean water":
                player.needs["thirst"] = clamp(player.needs["thirst"] - max(1, 35 * amount // VESSEL_DRINK_AMOUNT))
                player.conditions["headache"] = clamp(player.conditions.get("headache", 0) - 3)
            elif liquid_type == "unsafe water":
                player.needs["thirst"] = clamp(player.needs["thirst"] - max(1, 18 * amount // VESSEL_DRINK_AMOUNT))
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + 6)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 4)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) + 5)
            elif liquid_type == "salt water":
                player.needs["thirst"] = clamp(player.needs["thirst"] + max(1, 10 * amount // VESSEL_DRINK_AMOUNT))
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + 5)
                player.conditions["sodium_imbalance"] = clamp(player.conditions.get("sodium_imbalance", 0) + 12)
                player.needs["stress"] = clamp(player.needs["stress"] + 2)
            mark_carried_recent(player, vessel)
    elif name == "empty vessel":
        vessel = carried_vessel_with_liquid(player)
        if vessel:
            vessel = split_one_stack(player.carried, vessel)
            vessel.data["liquid"] = 0
            vessel.data.pop("liquid_type", None)
            mark_carried_recent(player, vessel)
    elif name == "eat":
        consume_food(player)
    elif name == "rest":
        sturdy_shelter = any(has_object(loc, kind) for kind in {"mud hut", "stone hut", "cellar"}) or "shelter walls" in loc.features
        shelter_bonus = 18 if sturdy_shelter else 12 if sheltered_at(loc) else 0
        bed_bonus = 8 if has_object(loc, "leaf bed") else 0
        player.needs["fatigue"] = clamp(player.needs["fatigue"] - 35 - shelter_bonus - bed_bonus)
        player.needs["health"] = clamp(player.needs["health"] + 2 + shelter_bonus // 6)
        player.needs["morale"] = clamp(player.needs["morale"] + shelter_bonus // 3 + bed_bonus // 4)
        player.conditions["back_pain"] = clamp(player.conditions.get("back_pain", 0) - 15 - bed_bonus)
        player.conditions["headache"] = clamp(player.conditions.get("headache", 0) - 8)
        player.conditions["foot_damage"] = clamp(player.conditions.get("foot_damage", 0) - 5)
        player.conditions["hand_damage"] = clamp(player.conditions.get("hand_damage", 0) - 5)
        player.stats["entertainment"] = clamp(player.stats.get("entertainment", 50) - 2)
    elif name == "leisure":
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.needs["stress"] = clamp(player.needs["stress"] - 6)
        player.stats["entertainment"] = clamp(player.stats.get("entertainment", 50) + 35)
        player.stats["courage"] = clamp(player.stats.get("courage", 60) + 4)
    elif name == "craft sharp stone":
        durability = TOOL_DURABILITY["sharp stone"]
        add_items(player.carried, "sharp stone", 1, data={"durability": durability, "max_durability": durability})
    elif name == "crack coconut":
        add_items(player.carried, "coconut water", 1, exposed=False)
        add_items(player.carried, "coconut meat", 1)
        add_items(player.carried, "coconut shell", 1)
    elif name == "weave cord":
        add_items(player.carried, "fiber cord", 1)
    elif name == "weave rope":
        add_items(player.carried, "rope", 1)
    elif name == "weave palm fronds":
        add_items(player.carried, "palm weave", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
    elif name == "craft woven basket":
        add_items(player.carried, "basket", 1, data=STORAGE_DATA["basket"])
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "craft woven backpack":
        add_items(player.carried, "woven backpack", 1, data=STORAGE_DATA["woven backpack"])
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "add rope to basket":
        add_items(player.carried, "woven backpack", 1, data=STORAGE_DATA["woven backpack"])
    elif name == "detach rope from woven backpack":
        add_items(player.carried, "basket", 1, data=STORAGE_DATA["basket"])
        add_items(player.carried, "rope", 1)
    elif name == "place basket":
        data = dict(action.reserved[0].data) if action.reserved else dict(STORAGE_DATA["basket"])
        loc.placed.append(PlacedObject("basket", active=True, data=data))
    elif name == "craft stone axe":
        durability = TOOL_DURABILITY["stone axe"]
        add_items(player.carried, "stone axe", 1, data={"durability": durability, "max_durability": durability})
    elif name == "craft digging stick":
        durability = TOOL_DURABILITY["digging stick"]
        add_items(player.carried, "digging stick", 1, data={"durability": durability, "max_durability": durability})
    elif name == "make wood shavings":
        add_items(player.carried, "wood shavings", 3)
    elif name == "start fire":
        fire = active_fire(loc)
        if fire:
            fire.fuel += 1
        else:
            loc.placed.append(PlacedObject("fire", fuel=1, active=True))
    elif name == "tend fire":
        fire = active_fire(loc)
        if not fire:
            loc.placed.append(PlacedObject("fire", fuel=1, active=True))
        else:
            fire.fuel += 1
    elif name == "build shelter":
        loc.placed.append(PlacedObject("shelter", active=True))
    elif name == "build shed":
        loc.placed.append(
            PlacedObject(
                "shed",
                active=True,
                data={**SHELTER_PROTECTION["shed"], "storage_capacity": SHELTER_STORAGE_CAPACITY["shed"]},
            )
        )
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 20)
        player.stats["courage"] = clamp(player.stats.get("courage", 60) + 6)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 4
    elif name == "build mud hut":
        loc.placed.append(
            PlacedObject(
                "mud hut",
                active=True,
                data={**SHELTER_PROTECTION["mud hut"], "storage_capacity": SHELTER_STORAGE_CAPACITY["mud hut"]},
            )
        )
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 50)
        player.stats["courage"] = clamp(player.stats.get("courage", 60) + 12)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 9
    elif name == "build stone hut":
        loc.placed.append(PlacedObject("stone hut", active=True))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 50)
        player.stats["courage"] = clamp(player.stats.get("courage", 60) + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 10
    elif name == "build cellar":
        loc.placed.append(
            PlacedObject(
                "cellar",
                active=True,
                data={**SHELTER_PROTECTION["cellar"], "storage_capacity": SHELTER_STORAGE_CAPACITY["cellar"]},
            )
        )
        add_items(loc.ground, "dirt pile", 16)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
    elif name == "craft leaf bed":
        loc.placed.append(PlacedObject("leaf bed", active=True))
    elif name == "build raincatcher":
        loc.placed.append(PlacedObject("raincatcher", active=True, data={"rain_minutes": 0}))
    elif name == "build campfire":
        loc.placed.append(PlacedObject("campfire", fuel=3, active=True, data={"burn_minutes": 0}))
    elif name == "build drying rack":
        loc.placed.append(PlacedObject("drying rack", active=True))
    elif name == "build storage chest":
        loc.placed.append(PlacedObject("storage chest", active=True, data=dict(STORAGE_DATA["storage chest"])))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "build supply chest":
        loc.placed.append(PlacedObject("supply chest", active=True, data=dict(STORAGE_DATA["supply chest"])))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 2
    elif name == "build fish trap":
        loc.placed.append(
            PlacedObject(
                "fish trap",
                active=True,
                data={"soak_minutes": 0, "target_minutes": trap_soak_target(world, player.location, "fish trap")},
            )
        )
    elif name == "check fish trap":
        trap = ready_fish_trap(loc)
        if trap:
            item = str(trap.data["catch"])
            add_items(player.carried, item, 1)
            trap.data = {"soak_minutes": 0, "target_minutes": trap_soak_target(world, player.location, "fish trap")}
    elif name == "build snare trap":
        loc.placed.append(PlacedObject("snare trap", active=True, data={"baited": 0, "soak_minutes": 0}))
    elif name == "bait snare trap":
        trap = baitable_snare_trap(loc)
        if trap:
            trap.data.update(
                {
                    "baited": 1,
                    "soak_minutes": 0,
                    "target_minutes": trap_soak_target(world, player.location, "snare trap"),
                }
            )
    elif name == "check snare trap":
        trap = ready_snare_trap(loc)
        if trap:
            item = str(trap.data["catch"])
            add_items(player.carried, item, 1)
            trap.data = {"baited": 0, "soak_minutes": 0}
    elif name == "build water filter":
        loc.placed.append(PlacedObject("water filter", active=True))
    elif name == "build solar still":
        loc.placed.append(PlacedObject("solar still", active=True, data={"sun_minutes": 0}))
    elif name == "fish":
        add_items(player.carried, "raw fish", 1)
    elif name == "cook fish":
        require_fire(loc)
        world.processes.append(WorldProcess("cooking", player.location, 45, item="raw fish", output="cooked fish"))
    elif name == "cook meat":
        require_fire(loc)
        world.processes.append(WorldProcess("cooking", player.location, 60, item="raw meat", output="cooked meat"))
    elif name == "boil water":
        require_fire(loc)
        world.processes.append(WorldProcess("boiling", player.location, 45, item="unsafe water", output="clean water"))
    elif name == "dry fish":
        world.processes.append(WorldProcess("drying", player.location, 12 * 60, item="raw fish", output="dried fish"))
    elif name == "filter water":
        world.processes.append(WorldProcess("filtering", player.location, 30, item="unsafe water", output="clean water"))
    elif name == "make aloe gel":
        add_items(player.carried, "aloe gel", 3)
    elif name == "apply aloe leaf":
        player.conditions["sunburn"] = clamp(player.conditions.get("sunburn", 0) - 10)
        player.conditions["back_pain"] = clamp(player.conditions.get("back_pain", 0) - 6)
        player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) - 8)
        player.conditions["burns"] = clamp(player.conditions.get("burns", 0) - 4)
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 4)
        player.stats["skin_integrity"] = clamp(player.stats.get("skin_integrity", 100) + 4)
    elif name == "apply aloe gel":
        player.conditions["sunburn"] = clamp(player.conditions.get("sunburn", 0) - 20)
        player.conditions["back_pain"] = clamp(player.conditions.get("back_pain", 0) - 10)
        player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) - 12)
        player.conditions["burns"] = clamp(player.conditions.get("burns", 0) - 10)
        player.conditions["hand_damage"] = clamp(player.conditions.get("hand_damage", 0) - 8)
        player.conditions["foot_damage"] = clamp(player.conditions.get("foot_damage", 0) - 8)
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 8)
        player.stats["skin_integrity"] = clamp(player.stats.get("skin_integrity", 100) + 8)
    elif name == "brew ginger tea":
        add_items(player.carried, "ginger tea", 1)
    elif name == "brew spider lily tea":
        add_items(player.carried, "spider lily tea", 1)
    elif name == "brew jasmine tea":
        add_items(player.carried, "jasmine tea", 1)
    elif name == "make bug repellent":
        add_items(player.carried, "bug repellent", 2)
    elif name == "apply bug repellent":
        player.conditions["bug_repellent"] = clamp(player.conditions.get("bug_repellent", 0) + 96)
        player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) - 8)
    elif name == "prepare yam":
        add_items(player.carried, "cooked yam", 1)
    elif name == "extract nipa seeds":
        add_items(player.carried, "nipa seeds", 4)
    elif name == "extract coffee beans":
        add_items(player.carried, "coffee beans", 2)
    elif name == "roast coffee beans":
        require_fire(loc)
        add_items(player.carried, "roasted coffee beans", 1)
    elif name == "brew coffee":
        require_fire(loc)
        add_items(player.carried, "coffee", 1)
    elif name == "split sago log":
        add_items(player.carried, "sago pith section", 16)
    elif name == "scrape sago pith":
        add_items(player.carried, "sago sawdust", 1)
    elif name == "soak sago sawdust":
        add_items(player.carried, "soaked sago", 1)
    elif name == "grind soaked sago":
        add_items(player.carried, "sago pulp", 1)
    elif name == "dry sago pulp":
        world.processes.append(WorldProcess("drying", player.location, 24 * 60, item="sago pulp", output="sago flour", data={"qty": 2}))
    elif name == "cook sago flatbread":
        require_fire(loc)
        add_items(player.carried, "sago flatbread", 1)
    elif name in COOKING_POT_MEALS:
        require_fire(loc)
        meal = COOKING_POT_MEALS[name]
        world.processes.append(
            WorldProcess("cooking", player.location, int(meal["minutes"]), output=str(meal["output"]))
        )
    elif name == "collect sand":
        add_items(player.carried, "sand", 4)
    elif name == "make quicklime":
        world.processes.append(
            WorldProcess("calcining", player.location, 4 * 60, item="pretty seashells", output="quicklime", data={"qty": 2, "temperature": 600})
        )
    elif name == "mix mortar":
        add_items(player.carried, "mortar", 4)
    elif name == "make clay":
        add_items(player.carried, "clay", 1)
    elif name == "make mud brick":
        add_items(player.carried, "mud brick", 1)
    elif name == "make mud":
        add_items(player.carried, "mud pile", 1)
    elif name == "crush dirt":
        add_items(player.carried, "fine dirt", 1)
    elif name == "mix clay":
        add_items(player.carried, "clay", 1)
    elif name == "shape clay bowl":
        add_items(player.carried, "unfired clay bowl", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "shape clay jar":
        add_items(player.carried, "unfired clay jar", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "shape cooking pot":
        add_items(player.carried, "unfired cooking pot", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "shape clay vase":
        add_items(player.carried, "unfired clay vase", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "build kiln":
        loc.placed.append(
            PlacedObject(
                "kiln",
                active=False,
                data={
                    "fuel": 0,
                    "max_fuel": KILN_MAX_FUEL,
                    "temperature": 0,
                    "max_temperature": HEAT_STRUCTURE_MAX_TEMPERATURES["kiln"],
                    "heat_gain": HEAT_STRUCTURE_HEAT_GAINS["kiln"],
                    "burn_minutes": 0,
                },
            )
        )
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 1
    elif name == "build advanced kiln":
        loc.placed.append(
            PlacedObject(
                "advanced kiln",
                active=False,
                data={
                    "fuel": 0,
                    "max_fuel": KILN_MAX_FUEL,
                    "temperature": 0,
                    "max_temperature": HEAT_STRUCTURE_MAX_TEMPERATURES["advanced kiln"],
                    "heat_gain": HEAT_STRUCTURE_HEAT_GAINS["advanced kiln"],
                    "burn_minutes": 0,
                },
            )
        )
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 2
    elif name == "build forge":
        loc.placed.append(
            PlacedObject(
                "forge",
                active=False,
                data={
                    "fuel": 0,
                    "max_fuel": KILN_MAX_FUEL,
                    "temperature": 0,
                    "max_temperature": HEAT_STRUCTURE_MAX_TEMPERATURES["forge"],
                    "heat_gain": HEAT_STRUCTURE_HEAT_GAINS["forge"],
                    "burn_minutes": 0,
                },
            )
        )
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 2
    elif name == "build water reservoir":
        loc.placed.append(
            PlacedObject(
                "water reservoir",
                active=True,
                data={"liquid": 0, "capacity": WATER_RESERVOIR_CAPACITY, "rain_minutes": 0, "mosquito_protection": 0},
            )
        )
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 1
    elif name == "build well":
        loc.placed.append(
            PlacedObject("well", active=True, data={"liquid": 0, "capacity": WELL_CAPACITY, "fill_minutes": 0})
        )
        add_items(loc.ground, "dirt pile", 10)
        add_items(loc.ground, "mud pile", 6)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 1
    elif name == "build cistern":
        loc.placed.append(
            PlacedObject("cistern", active=True, data={"liquid": 0, "capacity": CISTERN_CAPACITY, "rain_minutes": 0})
        )
        add_items(loc.ground, "dirt pile", 16)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 1
    elif name == "fuel kiln":
        kiln = fuelable_kiln_at(loc)
        if kiln:
            fuel_item = str(action.args["item"])
            max_fuel = int(kiln.data.get("max_fuel", KILN_MAX_FUEL))
            kiln.data["fuel"] = min(max_fuel, int(kiln.data.get("fuel", 0)) + KILN_FUEL_VALUES[fuel_item])
            kiln.data.setdefault("temperature", 0)
            kiln.data.setdefault("burn_minutes", 0)
    elif name == "light kiln":
        kiln = lightable_kiln_at(loc)
        if kiln:
            kiln.active = True
            kiln.data.setdefault("fuel", 0)
            kiln.data.setdefault("temperature", 0)
            kiln.data.setdefault("burn_minutes", 0)
    elif name in KILN_FIRING:
        firing = KILN_FIRING[name]
        world.processes.append(
            WorldProcess(
                "firing",
                player.location,
                int(firing["minutes"]),
                item=str(firing["input"]),
                output=str(firing["output"]),
                data={
                    "item_data": dict(firing.get("item_data", {})),
                    "heat": str(firing["heat"]),
                    "temperature": int(firing["temperature"]),
                },
            )
        )
    elif name == "mine copper ore":
        loc.explore_counts["copper_vein_uses"] = int(loc.explore_counts.get("copper_vein_uses", 0)) + 1
        add_items(player.carried, "copper ore", 1)
        if loc.explore_counts["copper_vein_uses"] >= COPPER_VEIN_USES and "copper vein" in loc.location_cards:
            loc.location_cards.remove("copper vein")
    elif name == "smelt copper":
        world.processes.append(
            WorldProcess(
                "smelting",
                player.location,
                2 * 60,
                item="copper ore",
                output="copper",
                data={"temperature": COPPER_SMELT_TEMPERATURE},
            )
        )
    elif name in COPPER_MOLD_OUTPUTS:
        add_items(player.carried, COPPER_MOLD_OUTPUTS[name], 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name in COPPER_CASTING_OUTPUTS:
        output = COPPER_CASTING_OUTPUTS[name]
        add_items(player.carried, output, 1, data=tool_durability_data(output))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name in COPPER_CRAFT_OUTPUTS:
        output = COPPER_CRAFT_OUTPUTS[name]
        data = dict(COPPER_VESSEL_DATA.get(output, tool_durability_data(output)))
        add_items(player.carried, output, COPPER_CRAFT_QUANTITIES.get(name, 1), data=data)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        if name in {"make copper needles", "craft copper bottle", "craft copper jar"}:
            player.needs["morale"] = clamp(player.needs["morale"] + 10)
        elif name in {"craft copper axe", "craft copper shovel", "craft copper spear"}:
            player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "collect salt water":
        add_items(player.carried, "salt water", 1)
    elif name == "boil salt water":
        require_fire(loc)
        world.processes.append(WorldProcess("boiling", player.location, 45, item="salt water", output="salt"))
    elif name == "build salt bed":
        loc.placed.append(PlacedObject("salt bed", active=True, data={"liquid": 0, "salt": 0, "evap_minutes": 0}))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.skills["crafting"] = player.skills.get("crafting", 0) + 1
    elif name == "fill salt bed":
        bed = salt_bed_at(loc)
        if bed:
            bed.data["liquid"] = min(SALT_BED_LIQUID_CAPACITY, int(bed.data.get("liquid", 0)) + SALT_BED_FILL_LIQUID)
            bed.data.setdefault("salt", 0)
            bed.data.setdefault("evap_minutes", 0)
    elif name == "scrape salt":
        bed = salt_bed_with_salt(loc)
        if bed:
            stored_salt = int(bed.data.get("salt", 0))
            qty, cost = (3, 144) if stored_salt >= 144 else (2, 96) if stored_salt >= 96 else (1, 48)
            bed.data["salt"] = stored_salt - cost
            add_items(player.carried, "salt", qty)
    elif name == "salt fish":
        world.processes.append(WorldProcess("curing", player.location, 3 * 1440, item="raw fish", output="salted fish"))
    elif name == "salt meat":
        world.processes.append(WorldProcess("curing", player.location, 3 * 1440, item="raw meat", output="salted meat"))
    elif name == "treat wound":
        player.conditions["treated_wound"] = 1
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 15)
        player.conditions["blood_loss"] = clamp(player.conditions.get("blood_loss", 0) - 8)
        player.stats["immunity"] = clamp(player.stats.get("immunity", 85) + 2)
    apply_tool_wear(world, player, name)
    log_event(world, f"{player.name} completed {name}.")


def gather_items_for_location(location: Location) -> list[str]:
    outputs = [
        item
        for item, resource in location.resources.items()
        if resource.get("action") == "gather"
    ]
    return outputs or ["sticks"]


def apply_tool_wear(world: World, player: Player, action_name: str) -> None:
    for item, wear in TOOL_WEAR.get(action_name, {}).items():
        for stack in carried_tool_stacks(player, item):
            if stack.item not in TOOL_DURABILITY:
                break
            if stack.qty > 1:
                stack.qty -= 1
                stack = ItemStack(stack.item, 1, stack.age_minutes, stack.exposed, dict(stack.data))
                player.carried.append(stack)
            max_durability = int(stack.data.get("max_durability", TOOL_DURABILITY[stack.item]))
            durability = int(stack.data.get("durability", max_durability))
            stack.data["max_durability"] = max_durability
            stack.data["durability"] = clamp(durability - wear, 0, max_durability)
            if stack.data["durability"] == 0:
                player.carried.remove(stack)
                log_event(world, f"{player.name}'s {stack.item} wore out.")
            else:
                mark_carried_recent(player, stack)
            break


def carried_tool_stacks(player: Player, item: str) -> list[ItemStack]:
    options = tool_options(item)
    return [stack for option in options for stack in list(player.carried) if stack.item == option]


def tool_durability_data(item: str) -> dict[str, int]:
    if item not in TOOL_DURABILITY:
        return {}
    durability = TOOL_DURABILITY[item]
    return {"durability": durability, "max_durability": durability}


def forage_outputs_for_location(location: Location) -> list[str]:
    outputs = [
        item
        for item, resource in location.resources.items()
        if resource.get("action", "forage") == "forage" and (resource.get("infinite") or int(resource.get("qty", 0)) > 0)
    ]
    return outputs or DEFAULT_FORAGE_OUTPUTS


def discovered_neighbor_names(world: World, location_name: str) -> list[str]:
    return [
        name
        for name in AREA_NEIGHBORS.get(location_name, [])
        if name in world.locations and world.locations[name].discovered
    ]


def discover_next(world: World, player: Player) -> None:
    discovered = discover_area_or_card(world, player)
    found_item = find_explore_item(world, player)
    if discovered or found_item:
        return
    add_items(player.carried, "stones", 1)
    log_event(world, f"{player.name} found stones while exploring {player.location}.")


def discover_area_or_card(world: World, player: Player) -> bool:
    current_location = world.locations[player.location]
    for name in AREA_EXPLORE_AREAS.get(player.location, []):
        loc = world.locations[name]
        if not loc.discovered:
            loc.discovered = True
            log_event(world, f"{player.name} discovered {name}.")
            return True
    for card in AREA_EXPLORE_CARDS.get(player.location, []):
        if card not in current_location.location_cards:
            current_location.location_cards.append(card)
            log_event(world, f"{player.name} found {card} at {player.location}.")
            return True
    for name in DISCOVERY_ORDER:
        loc = world.locations[name]
        if not loc.discovered:
            loc.discovered = True
            log_event(world, f"{player.name} discovered {name}.")
            return True
    return False


def find_explore_item(world: World, player: Player) -> bool:
    loc = world.locations[player.location]
    rewards = AREA_EXPLORE_ITEMS.get(player.location, [])
    available_rewards = [reward_parts(reward) for reward in rewards]
    available_rewards = [
        reward
        for reward in available_rewards
        if reward["limit"] is None or loc.explore_counts.get(str(reward["key"]), 0) < int(reward["limit"])
    ]
    if not available_rewards:
        return False
    total_weight = sum(int(reward["weight"]) for reward in available_rewards)
    if total_weight <= 0:
        return False
    rng = random.Random(f"{world.seed}:{world.tick}:{world.day}:{world.minute}:{player.name}:{player.location}")
    roll = rng.randrange(total_weight)
    upto = 0
    for reward in available_rewards:
        upto += int(reward["weight"])
        if roll < upto:
            item = str(reward["item"])
            min_qty = int(reward["min_qty"])
            max_qty = int(reward["max_qty"])
            qty = min_qty if min_qty == max_qty else rng.randint(min_qty, max_qty)
            if reward["limit"] is not None:
                key = str(reward["key"])
                loc.explore_counts[key] = loc.explore_counts.get(key, 0) + 1
            add_items(player.carried, item, qty)
            log_event(world, f"{player.name} found {qty} {item} while exploring {player.location}.")
            return True
    return False


def reward_parts(reward) -> dict[str, Any]:
    if len(reward) == 4:
        weight, item, min_qty, max_qty = reward
        return {
            "key": str(item).replace(" ", "_"),
            "weight": weight,
            "item": item,
            "min_qty": min_qty,
            "max_qty": max_qty,
            "limit": None,
        }
    key, weight, item, min_qty, max_qty, limit = reward
    return {
        "key": key,
        "weight": weight,
        "item": item,
        "min_qty": min_qty,
        "max_qty": max_qty,
        "limit": limit,
    }


def consume_drink(player: Player) -> None:
    for item in ["ginger tea", "spider lily tea", "jasmine tea", "coffee", "clean water", "coconut water", "coconut"]:
        if count_item(player.carried, item):
            remove_items(player.carried, item, 1)
            player.needs["thirst"] = clamp(player.needs["thirst"] - DRINK_VALUES[item])
            player.conditions["headache"] = clamp(player.conditions.get("headache", 0) - 4)
            saturation_stat = FOOD_SATURATION_STATS.get(item)
            if saturation_stat:
                player.stats[saturation_stat] = clamp(player.stats.get(saturation_stat, 100) - 8)
            if item == "coconut":
                player.needs["hunger"] = clamp(player.needs["hunger"] - 8)
            if item == "ginger tea":
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) - 18)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) - 12)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) - 6)
                player.stats["appetite"] = clamp(player.stats.get("appetite", 80) + 10)
                player.stats["immunity"] = clamp(player.stats.get("immunity", 85) + 5)
            if item == "spider lily tea":
                player.conditions["fever"] = clamp(player.conditions.get("fever", 0) - 15)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) - 8)
                player.conditions["wounds"] = clamp(player.conditions.get("wounds", 0) - 1)
                player.stats["immunity"] = clamp(player.stats.get("immunity", 85) + 10)
            if item == "jasmine tea":
                player.needs["stress"] = clamp(player.needs["stress"] - 12)
                player.needs["morale"] = clamp(player.needs["morale"] + 8)
                player.conditions["headache"] = clamp(player.conditions.get("headache", 0) - 6)
            if item == "coffee":
                player.needs["fatigue"] = clamp(player.needs["fatigue"] - 20)
                player.needs["stress"] = clamp(player.needs["stress"] + 3)
                player.conditions["caffeine"] = clamp(player.conditions.get("caffeine", 0) + 18)
            return


def consume_food(player: Player) -> None:
    for item in [
        "coconut fish",
        "yam curry",
        "sago cake",
        "fried puffballs",
        "cooked meat",
        "cooked fish",
        "dried fish",
        "salted meat",
        "salted fish",
        "cooked yam",
        "banana",
        "nipa seeds",
        "puffballs",
        "sago flatbread",
        "coconut meat",
        "crab",
        "prawns",
        "urchin",
        "seaweed",
        "lemongrass",
        "ginger",
        "chillies",
        "magic mushrooms",
        "assorted mushrooms",
        "bugs",
        "sago flour",
        "sago pulp",
        "soaked sago",
        "yam",
        "raw meat",
        "raw fish",
        "coconut",
    ]:
        if count_item(player.carried, item):
            remove_items(player.carried, item, 1)
            player.needs["hunger"] = clamp(player.needs["hunger"] - FOOD_VALUES[item])
            saturation_stat = FOOD_SATURATION_STATS.get(item)
            if saturation_stat:
                player.stats[saturation_stat] = clamp(
                    player.stats.get(saturation_stat, 100) - FOOD_SATURATION_VALUES.get(item, 18)
                )
            if item == "coconut":
                player.needs["thirst"] = clamp(player.needs["thirst"] - 10)
            if item == "soaked sago":
                player.needs["thirst"] = clamp(player.needs["thirst"] - 40)
                player.needs["morale"] = clamp(player.needs["morale"] - 10)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) + 24)
                player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + 2)
            if item == "sago pulp":
                player.needs["thirst"] = clamp(player.needs["thirst"] - 5)
                player.needs["morale"] = clamp(player.needs["morale"] - 3)
                player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + 2)
            if item == "sago flour":
                player.needs["thirst"] = clamp(player.needs["thirst"] + 5)
                player.needs["morale"] = clamp(player.needs["morale"] - 5)
                player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + 2)
            if item == "sago flatbread":
                player.needs["thirst"] = clamp(player.needs["thirst"] + 1)
                player.needs["stress"] = clamp(player.needs["stress"] - 10)
                player.needs["morale"] = clamp(player.needs["morale"] + 1)
                player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + 3)
            if item == "coconut fish":
                player.needs["thirst"] = clamp(player.needs["thirst"] - 22)
                player.needs["stress"] = clamp(player.needs["stress"] - 10)
                player.needs["morale"] = clamp(player.needs["morale"] + 15)
                player.stats["mental_structure"] = clamp(player.stats.get("mental_structure", 100) + 15)
                player.stats["coconut_appetite"] = clamp(player.stats.get("coconut_appetite", 100) - 30)
                player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + 5)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 10)
            if item == "yam curry":
                player.needs["thirst"] = clamp(player.needs["thirst"] - 6)
                player.needs["stress"] = clamp(player.needs["stress"] - 8)
                player.needs["morale"] = clamp(player.needs["morale"] + 10)
                player.conditions["capsaicin"] = clamp(player.conditions.get("capsaicin", 0) + 8)
            if item == "sago cake":
                player.needs["stress"] = clamp(player.needs["stress"] - 6)
                player.needs["morale"] = clamp(player.needs["morale"] + 8)
                player.stats["coconut_appetite"] = clamp(player.stats.get("coconut_appetite", 100) - 12)
            if item == "fried puffballs":
                player.needs["stress"] = clamp(player.needs["stress"] - 4)
                player.needs["morale"] = clamp(player.needs["morale"] + 6)
            if item in {"salted fish", "salted meat"}:
                player.needs["thirst"] = clamp(player.needs["thirst"] + 8)
                player.needs["morale"] = clamp(player.needs["morale"] - 4)
                player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + 5)
                player.conditions["sodium_imbalance"] = clamp(player.conditions.get("sodium_imbalance", 0) + 5)
            if item == "banana":
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) - 4)
                player.needs["morale"] = clamp(player.needs["morale"] + 2)
            if item == "lemongrass":
                player.needs["thirst"] = clamp(player.needs["thirst"] - 5)
                player.conditions["bug_repellent"] = clamp(player.conditions.get("bug_repellent", 0) + 12)
            if item == "ginger":
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) - 10)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) - 6)
                player.stats["appetite"] = clamp(player.stats.get("appetite", 80) + 6)
                player.stats["immunity"] = clamp(player.stats.get("immunity", 85) + 3)
            if item == "chillies":
                player.conditions["capsaicin"] = clamp(player.conditions.get("capsaicin", 0) + 20)
                player.needs["stress"] = clamp(player.needs["stress"] + 2)
            if item == "magic mushrooms":
                player.conditions["psilocybin"] = clamp(player.conditions.get("psilocybin", 0) + 35)
                player.conditions["altered_mind_state"] = clamp(player.conditions.get("altered_mind_state", 0) + 20)
                player.conditions["derealization"] = clamp(player.conditions.get("derealization", 0) + 10)
                player.needs["morale"] = clamp(player.needs["morale"] + 4)
            if item in {"raw meat", "raw fish", "assorted mushrooms", "bugs", "yam"}:
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + 8)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 5)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) + 10)
            else:
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) - 2)
                player.stats["appetite"] = clamp(player.stats.get("appetite", 80) + 2)
            return


def require_fire(loc: Location) -> None:
    if not active_fire(loc):
        raise ValueError("active fire required")


def update_world_processes(world: World, dt: int) -> None:
    for loc in world.locations.values():
        for obj in loc.placed:
            if obj.kind in {"fire", "campfire"} and obj.active and obj.fuel > 0:
                obj.data["burn_minutes"] = obj.data.get("burn_minutes", 0) + dt
                burn_minutes = 300 if obj.kind == "campfire" else 180
                while obj.data["burn_minutes"] >= burn_minutes and obj.fuel > 0:
                    obj.data["burn_minutes"] -= burn_minutes
                    obj.fuel -= 1
                    add_items(loc.ground, "ash", 1)
                    add_items(loc.ground, "charcoal", 1)
                if obj.fuel <= 0:
                    obj.active = False
                    if obj.kind == "fire":
                        obj.kind = "fire remnants"
                    log_event(world, f"A {obj.kind} at {loc.name} burned out.")
            if obj.kind in HEAT_STRUCTURE_KINDS:
                obj.data.setdefault("fuel", 0)
                obj.data.setdefault("max_fuel", KILN_MAX_FUEL)
                obj.data.setdefault("temperature", 0)
                obj.data.setdefault("max_temperature", HEAT_STRUCTURE_MAX_TEMPERATURES.get(obj.kind, KILN_MAX_TEMPERATURE))
                obj.data.setdefault("heat_gain", HEAT_STRUCTURE_HEAT_GAINS.get(obj.kind, 8))
                obj.data.setdefault("burn_minutes", 0)
                if obj.active and int(obj.data.get("fuel", 0)) > 0:
                    obj.data["burn_minutes"] = int(obj.data.get("burn_minutes", 0)) + dt
                    while obj.data["burn_minutes"] >= KILN_TP_MINUTES and int(obj.data.get("fuel", 0)) > 0:
                        obj.data["burn_minutes"] -= KILN_TP_MINUTES
                        obj.data["fuel"] = max(0, int(obj.data.get("fuel", 0)) - 1)
                        max_temperature = int(obj.data.get("max_temperature", KILN_MAX_TEMPERATURE))
                        heat_gain = int(obj.data.get("heat_gain", 8))
                        obj.data["temperature"] = min(max_temperature, int(obj.data.get("temperature", 0)) + heat_gain)
                    if int(obj.data.get("fuel", 0)) <= 0:
                        obj.active = False
                        add_items(loc.ground, "ash", 1)
                        if (world.day + world.tick + len(loc.name)) % 2 == 0:
                            add_items(loc.ground, "charcoal", 1)
                        log_event(world, f"A {obj.kind} at {loc.name} burned out.")
                elif not obj.active and int(obj.data.get("temperature", 0)) > 0:
                    obj.data["burn_minutes"] = int(obj.data.get("burn_minutes", 0)) + dt
                    while obj.data["burn_minutes"] >= KILN_TP_MINUTES and int(obj.data.get("temperature", 0)) > 0:
                        obj.data["burn_minutes"] -= KILN_TP_MINUTES
                        obj.data["temperature"] = max(0, int(obj.data.get("temperature", 0)) - 8)
            if obj.kind == "fish trap" and obj.active and not obj.data.get("ready"):
                obj.data["soak_minutes"] = int(obj.data.get("soak_minutes", 0)) + dt
                target_minutes = int(
                    obj.data.setdefault("target_minutes", trap_soak_target(world, loc.name, "fish trap"))
                )
                if obj.data["soak_minutes"] >= target_minutes:
                    obj.data["ready"] = 1
                    obj.data["catch"] = FISH_TRAP_OUTPUTS[
                        (world.day + world.tick + len(loc.name)) % len(FISH_TRAP_OUTPUTS)
                    ]
            if obj.kind == "snare trap" and obj.active and obj.data.get("baited") and not obj.data.get("ready"):
                obj.data["soak_minutes"] = int(obj.data.get("soak_minutes", 0)) + dt
                target_minutes = int(
                    obj.data.setdefault("target_minutes", trap_soak_target(world, loc.name, "snare trap"))
                )
                if obj.data["soak_minutes"] >= target_minutes:
                    obj.data["ready"] = 1
                    output_index = (world.day + world.tick + len(loc.name)) % len(SNARE_TRAP_OUTPUTS)
                    obj.data["catch"] = SNARE_TRAP_OUTPUTS[output_index]
            if obj.kind == "raincatcher" and obj.active:
                if world.weather in {"rain", "storm"}:
                    obj.data["rain_minutes"] = obj.data.get("rain_minutes", 0) + dt
                    while obj.data["rain_minutes"] >= 60:
                        obj.data["rain_minutes"] -= 60
                        add_items(loc.ground, "clean water", 1)
                elif world.weather == "clear":
                    obj.data["rain_minutes"] = max(0, obj.data.get("rain_minutes", 0) - dt)
            if obj.kind == "water reservoir" and obj.active:
                obj.data.setdefault("capacity", WATER_RESERVOIR_CAPACITY)
                obj.data.setdefault("liquid", 0)
                obj.data.setdefault("rain_minutes", 0)
                obj.data.setdefault("mosquito_protection", 0)
                if world.weather in {"rain", "storm"}:
                    obj.data["rain_minutes"] = int(obj.data.get("rain_minutes", 0)) + dt
                    while obj.data["rain_minutes"] >= WATER_RESERVOIR_TP_MINUTES:
                        obj.data["rain_minutes"] -= WATER_RESERVOIR_TP_MINUTES
                        obj.data["liquid"] = min(
                            int(obj.data.get("capacity", WATER_RESERVOIR_CAPACITY)),
                            int(obj.data.get("liquid", 0)) + WATER_RESERVOIR_RAIN_FILL,
                        )
                        obj.data["mosquito_protection"] = max(0, int(obj.data.get("mosquito_protection", 0)) - 4)
                elif world.weather == "clear":
                    obj.data["rain_minutes"] = max(0, int(obj.data.get("rain_minutes", 0)) - dt)
            if obj.kind == "well" and obj.active:
                obj.data.setdefault("capacity", WELL_CAPACITY)
                obj.data.setdefault("liquid", 0)
                obj.data.setdefault("fill_minutes", 0)
                obj.data["fill_minutes"] = int(obj.data.get("fill_minutes", 0)) + dt
                while obj.data["fill_minutes"] >= WELL_TP_MINUTES:
                    obj.data["fill_minutes"] -= WELL_TP_MINUTES
                    fill = WELL_BASE_FILL + (WELL_RAIN_FILL if world.weather in {"rain", "storm"} else 0)
                    obj.data["liquid"] = min(
                        int(obj.data.get("capacity", WELL_CAPACITY)),
                        int(obj.data.get("liquid", 0)) + fill,
                    )
            if obj.kind == "cistern" and obj.active:
                obj.data.setdefault("capacity", CISTERN_CAPACITY)
                obj.data.setdefault("liquid", 0)
                obj.data.setdefault("rain_minutes", 0)
                if world.weather in {"rain", "storm"}:
                    obj.data["rain_minutes"] = int(obj.data.get("rain_minutes", 0)) + dt
                    while obj.data["rain_minutes"] >= CISTERN_TP_MINUTES:
                        obj.data["rain_minutes"] -= CISTERN_TP_MINUTES
                        obj.data["liquid"] = min(
                            int(obj.data.get("capacity", CISTERN_CAPACITY)),
                            int(obj.data.get("liquid", 0)) + CISTERN_RAIN_FILL,
                        )
                elif world.weather == "clear":
                    obj.data["rain_minutes"] = max(0, int(obj.data.get("rain_minutes", 0)) - dt)
            if obj.kind == "solar still" and obj.active:
                hour = world.minute // 60
                if world.weather == "clear" and 7 <= hour < 17:
                    obj.data["sun_minutes"] = obj.data.get("sun_minutes", 0) + dt
                    while obj.data["sun_minutes"] >= 180:
                        obj.data["sun_minutes"] -= 180
                        add_items(loc.ground, "clean water", 1)
            if obj.kind == "salt bed" and obj.active and int(obj.data.get("liquid", 0)) > 0:
                obj.data["evap_minutes"] = int(obj.data.get("evap_minutes", 0)) + dt
                while obj.data["evap_minutes"] >= SALT_BED_TP_MINUTES and int(obj.data.get("liquid", 0)) > 0:
                    obj.data["evap_minutes"] -= SALT_BED_TP_MINUTES
                    obj.data["liquid"] = max(0, int(obj.data.get("liquid", 0)) - 50)
                    obj.data["salt"] = min(SALT_BED_SALT_CAPACITY, int(obj.data.get("salt", 0)) + 2)
    for process in list(world.processes):
        if process.kind in {"cooking", "boiling"} and not active_fire(world.locations[process.location]):
            continue
        if process.kind == "firing" and not firing_heat_available(world.locations[process.location], process):
            continue
        if process.kind == "calcining" and not hot_kiln_at(world.locations[process.location], int(process.data.get("temperature", 600))):
            continue
        if process.kind == "smelting" and not hot_kiln_at(world.locations[process.location], int(process.data.get("temperature", COPPER_SMELT_TEMPERATURE))):
            continue
        process.remaining_minutes -= dt
        if process.remaining_minutes <= 0:
            loc = world.locations[process.location]
            if process.output:
                add_items(
                    loc.ground,
                    process.output,
                    int(process.data.get("qty", 1)),
                    data=process.data.get("item_data"),
                )
            world.processes.remove(process)
            log_event(world, f"{process.kind} at {process.location} produced {process.output}.")


def firing_heat_available(location: Location, process: WorldProcess) -> bool:
    temperature = int(process.data.get("temperature", 0))
    if process.data.get("heat") == "fire_or_kiln" and active_fire(location):
        return True
    return hot_kiln_at(location, temperature) is not None


def update_location_resources(world: World, dt: int) -> None:
    for loc in world.locations.values():
        for item, resource in loc.resources.items():
            if resource.get("infinite"):
                continue
            capacity = int(resource.get("capacity", resource.get("qty", 0)))
            if int(resource.get("qty", 0)) >= capacity:
                resource["regen_progress"] = 0
                continue
            resource["regen_progress"] = int(resource.get("regen_progress", 0)) + dt
            regen_minutes = int(resource.get("regen_minutes", 0))
            while regen_minutes and resource["regen_progress"] >= regen_minutes and int(resource.get("qty", 0)) < capacity:
                resource["regen_progress"] -= regen_minutes
                resource["qty"] = int(resource.get("qty", 0)) + 1
                log_event(world, f"{item} regrew at {loc.name}.")


def update_items(world: World, dt: int) -> None:
    for loc in world.locations.values():
        dry = world.weather == "clear"
        update_item_stacks(world, loc.ground, dt, dry=dry, place=loc.name)
        update_storage_contents_in_stacks(world, loc.ground, dt, place=loc.name)
        for obj in placed_storage_objects(loc):
            contents = storage_contents(obj.data)
            storage_dt = max(1, dt // 2) if obj.data.get("cool_storage") else dt
            update_item_stacks(world, contents, storage_dt, dry=False, place=f"{obj.kind} at {loc.name}")
            set_storage_contents(obj.data, contents)
    for player in world.players.values():
        if player.connected:
            update_item_stacks(world, player.carried, dt, dry=False, place=f"{player.name}'s pack")
            update_storage_contents_in_stacks(world, player.carried, dt, place=f"{player.name}'s pack")


def update_storage_contents_in_stacks(world: World, stacks: list[ItemStack], dt: int, *, place: str) -> None:
    for stack in stacks:
        if stack_is_storage(stack):
            contents = storage_contents(stack.data)
            update_item_stacks(world, contents, dt, dry=False, place=f"{place} {stack.item}")
            set_storage_contents(stack.data, contents)


def update_item_stacks(world: World, stacks, dt: int, *, dry: bool, place: str) -> None:
    for stack in list(stacks):
        stack.age_minutes += dt
        if stack.item in SPOIL_MINUTES and stack.age_minutes >= SPOIL_MINUTES[stack.item]:
            stacks.remove(stack)
            if stack.item == "mud pile":
                add_items(stacks, "dirt pile", stack.qty)
            log_event(world, f"{stack.item.capitalize()} spoiled at {place}.")
        elif stack.item in {"clean water", "unsafe water", "salt water"} and stack.exposed and dry and stack.age_minutes >= 360:
            stacks.remove(stack)
            log_event(world, f"Exposed {stack.item} evaporated at {place}.")
