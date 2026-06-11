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
    DISCOVERY_ORDER,
    DRINK_VALUES,
    DIVE_ENTERTAINMENT_GAIN,
    DIVE_FATIGUE_COST,
    DIVE_FILTH_REMOVAL,
    DIVE_LOCATIONS,
    DIVE_MAX_FATIGUE,
    DIVE_MORALE_GAIN,
    DIVE_NOTHING_WEIGHT,
    DIVE_OUTPUT_WEIGHTS,
    DIVE_STRESS_RELIEF,
    DIVE_SWIMMING_NOTHING_REDUCTION,
    DIVE_WETNESS,
    FISH_TRAP_OUTPUTS,
    FISH_TRAP_SOAK_RANGE,
    FOOD_SATURATION_VALUES,
    FOOD_SATURATION_STATS,
    FOOD_VALUES,
    FIRE_SOURCE_ITEMS,
    DEFAULT_ITEM_WEIGHT,
    ITEM_WEIGHTS,
    KILN_FIRING,
    KILN_FUEL_VALUES,
    LINE_FISH_LOCATIONS,
    LINE_FISH_STRESS_RELIEF,
    LINE_FISH_WEIGHTS,
    MATERIAL_ALTERNATIVES,
    PREREQUISITE_ACTIONS,
    RAFT_BUILD_STAGES,
    RAFT_EVENT_PASSING_SHIP,
    RAFT_PASSING_SHIP_DISTANCE_TRIGGERS,
    RAFT_PASSING_SHIP_WINDOW_MINUTES,
    RAFT_RESCUE_DISTANCE,
    RAFT_SIGNAL_PROGRESS_RANGES,
    RESOURCE_HARVESTS,
    SKILL_BY_ACTION,
    SPEAR_FISH_BASE_WEIGHTS,
    SPEAR_FISH_LOCATIONS,
    SPEAR_FISH_WETNESS,
    SNARE_TRAP_OUTPUTS,
    SNARE_TRAP_SOAK_RANGE,
    SPOIL_MINUTES,
    TIDE_POOL_OUTPUTS,
    TINDER_LIGHTING_ACTIONS,
    TINDER_ITEMS,
    TORCH_FUEL_MINUTES,
    TORCH_MAX_FUEL,
    TOOL_DURABILITY,
    TOOL_REQUIREMENTS,
    TOOL_WEAR,
    WALK_FATIGUE_COST,
    WALK_FOOT_DAMAGE,
    WALK_LOCATIONS,
    WALK_STRESS_RELIEF,
    WATER_LOCATIONS,
    HIGH_TIDE_WINDOWS,
    RAIN_COUNTER_MAX,
    RAIN_COUNTER_MIN,
    RAIN_COUNTER_SEASON_DELTAS,
    RAIN_COUNTER_START,
    RAIN_COUNTER_STEP_MINUTES,
    RAIN_COUNTER_WEATHER_DELTAS,
    RAIN_COUNTER_WEIGHT_BONUSES,
    STORM_DAMAGE_INTERVAL_MINUTES,
    STORM_DAMAGE_OBJECTS,
    STORM_DAMAGE_RANGE,
    STORM_EVENT_BRUISING,
    STORM_EVENT_WETNESS,
    STORM_EXPOSED_LOCATIONS,
    WEATHER_ALIASES,
    WEATHER_DEFS,
    WEATHER_TRANSITION_WEIGHTS,
    build_locations,
    scale_wiki_delta,
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
    world.rain_counter = RAIN_COUNTER_START
    world.weather_remaining_minutes = weather_duration_minutes(world.weather)
    world.locations = build_locations()
    for location_name, data in AREA_DEFS.items():
        for item, qty in data.get("ground", {}).items():
            add_items(world.locations[location_name].ground, item, int(qty))
    update_tides(world)
    log_event(world, "Day 1 dawns on the beach.")
    log_event(world, "Tip: pick up a coconut and drink it for quick water; gather unsafe water and boil it for safer water.")
    return world


def world_snapshot(world: World, player_name: str) -> dict[str, Any]:
    player = world.players[player_name]
    current_location = world.locations[player.location]
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
    blocked_actions = blocked_action_hints(world, player, actions)
    players = {player_name: player_data}
    for other in world.players.values():
        if other.name == player_name or not other.connected or other.location != player.location:
            continue
        players[other.name] = public_player_data(other)
    current_location_data = current_location.to_dict()
    current_location_data["neighbors"] = allowed_move_destinations(world, player)
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
        "weather": canonical_weather(world.weather),
        "season": world.season,
        "rain_counter": world.rain_counter,
        "rain_value": weather_rain_value(world.weather),
        "sun_strength": weather_sun_strength(world.weather),
        "tide": tide_state(world),
        "locations": locations,
        "players": players,
        "event_log": world.event_log[-MAX_EVENT_LOG:],
        "light": light_state_for_player(world, player, current_location),
        "paused": world.paused,
        "outcome": outcome_data(world),
        "raft": raft_data(world),
        "sleep": sleep_data(world),
        "blocked_actions": blocked_actions,
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
    if player.conditions.get("malaria", 0) >= 70 or player.conditions.get("parasites", 0) >= 85:
        return "disease"
    if player.conditions.get("bacterial_infection", 0) >= 60 or player.conditions.get("fever", 0) >= 60:
        return "infection"
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
    "cook conch meat",
    "cook fish",
    "cook meat",
    "cook sago cake",
    "cook sago flatbread",
    "cook yam curry",
    "fry puffballs",
    "prepare yam",
    "roast coffee beans",
}
LIGHT_REQUIRED_ACTIONS = {
    "break conch",
    "collect bone splinters",
    "collect feathers",
    "craft bone hook",
    "craft fish bait",
    "craft fishing line",
    "craft fishing rod",
    "flesh skin",
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
    "hammer": ("heavy stone", "axe head", "shovel head", "spear head", "copper axe", "copper shovel"),
    "cooking pot": ("cooking pot", "copper jar"),
    "fishing line": ("fishing line", "fishing rod"),
    "needle": ("copper needle",),
    "spear": ("copper spear",),
}
SHELTER_KINDS = {"shelter", "shed", "mud hut", "stone hut", "cellar"}
STORAGE_DATA = {
    "basket": {"storage_capacity": 1000, "slots": 4, "weight_reduction": 1000},
    "woven backpack": {
        "storage_capacity": 1000,
        "slots": 4,
        "weight_reduction": 1000,
        "equipped_weight_reduction": 250,
        "equipped_slot": "back",
    },
    "storage chest": {"storage_capacity": 4000, "slots": 1, "weight_reduction": 4000},
    "supply chest": {"storage_capacity": 3000, "weight_reduction": 3000, "durability": 480, "max_durability": 480},
}
BASE_CARRY_CAPACITY = 2500
MAX_EFFECTIVE_CARRY = 4000
BASE_LOOSE_CARRY_SLOTS = 4
BACK_SLOT_CAPACITY = 1
LOAD_BLOCKED_ACTIONS = {
    "build raft",
    "explore",
    "fish",
    "fish with bait",
    "forage tide pool",
    "gather",
    "go for a walk",
    "harvest coconuts",
    "collect sand",
    "dive",
    "dig up sand",
    "move",
    "sail raft",
    "spear fish",
    "swim",
    *RESOURCE_HARVESTS,
}
DARK_ALLOWED_ACTIONS = {
    "drop",
    "drink",
    "drink from vessel",
    "eat",
    "empty vessel",
    "extinguish torch",
    "leisure",
    "light torch",
    "move",
    "pack",
    "pick up",
    "place basket",
    "retrieve",
    "rest",
    "start fire",
    "store",
    "take off backpack",
    "unpack",
    *TINDER_LIGHTING_ACTIONS,
}
HAND_CARRIED_STORAGE_KINDS = {"basket"}
PICKABLE_STORAGE_KINDS = {"basket"}
SHELTER_STORAGE_CAPACITY = {"shed": 15000, "mud hut": 60000, "cellar": 30000}
SHELTER_PROTECTION = {
    "shed": {"rain_protection": 5, "heat_insulation": 3, "sun_protection": 6},
    "mud hut": {"rain_protection": 5, "heat_insulation": 3, "perceived_temperature": -1, "sun_protection": 6},
    "cellar": {"rain_protection": 5, "heat_insulation": 6, "perceived_temperature": -4, "sun_protection": 6, "cool_storage": 1},
}
RAFT_BUILD_LOCATIONS = {"beach"}
BLOCKED_ACTION_HINTS = (
    "build raft",
    "start fire",
    "boil water",
    "craft sharp stone",
    "craft stone axe",
    "build shelter",
    "craft leaf bed",
    "build drying rack",
    "build fish trap",
    "build snare trap",
    "build water filter",
    "build kiln",
    "build forge",
    "make copper needles",
)
MAX_BLOCKED_ACTION_HINTS = 5


def canonical_weather(weather: str) -> str:
    return WEATHER_ALIASES.get(weather, weather)


def weather_data(weather: str) -> dict[str, Any]:
    return WEATHER_DEFS.get(canonical_weather(weather), WEATHER_DEFS["clear"])


def weather_duration_minutes(weather: str) -> int:
    return int(weather_data(weather)["duration_minutes"])


def weather_rain_value(weather: str) -> int:
    return int(weather_data(weather)["rain_value"])


def is_raining(weather: str) -> bool:
    return weather_rain_value(weather) > 0


def is_storm(weather: str) -> bool:
    return canonical_weather(weather) == "storm"


def weather_sun_strength(weather: str) -> int:
    return int(weather_data(weather)["sun_strength"])


def weather_is_dry(weather: str) -> bool:
    return weather_rain_value(weather) == 0 and weather_sun_strength(weather) >= 4


def season_for_day(day: int) -> str:
    return "wet" if ((day - 1) // 7) % 2 else "dry"


def rain_counter_bonus(weather: str, rain_counter: int) -> int:
    low, high = RAIN_COUNTER_WEIGHT_BONUSES[weather]
    rain_counter = clamp(rain_counter, RAIN_COUNTER_MIN, RAIN_COUNTER_MAX)
    return round(low + (high - low) * rain_counter / RAIN_COUNTER_MAX)


def weather_transition_weights(world: World) -> tuple[tuple[str, int], ...]:
    weights = []
    for weather, base_weight in WEATHER_TRANSITION_WEIGHTS[world.season]:
        weight = max(1, base_weight + rain_counter_bonus(weather, world.rain_counter))
        weights.append((weather, weight))
    return tuple(weights)


def tide_is_high(world: World) -> bool:
    return any(start <= world.minute < end for start, end in HIGH_TIDE_WINDOWS)


def tide_state(world: World) -> str:
    return "high" if tide_is_high(world) else "low"


def normalize_tide_pool_card(location: Location, high_tide: bool) -> None:
    if "tide pool" not in location.location_cards and "flooded tide pool" not in location.location_cards:
        return
    target = "flooded tide pool" if high_tide else "tide pool"
    location.location_cards = [card for card in location.location_cards if card not in {"tide pool", "flooded tide pool"}]
    location.location_cards.append(target)


def location_is_dark(location: Location) -> bool:
    return "darkness" in location.features


def active_fire(location: Location) -> PlacedObject | None:
    return next((p for p in location.placed if p.kind in {"fire", "campfire"} and p.active and p.fuel > 0), None)


def torch_duration_minutes(stack: ItemStack) -> int:
    max_fuel = int(stack.data.get("max_fuel", TORCH_MAX_FUEL))
    return max(1, max_fuel) * TORCH_FUEL_MINUTES


def torch_remaining_minutes(stack: ItemStack) -> int:
    return max(0, torch_duration_minutes(stack) - int(stack.age_minutes))


def torch_has_fuel(stack: ItemStack) -> bool:
    return stack.item in {"torch", "lit torch"} and torch_remaining_minutes(stack) > 0


def player_has_lit_torch(player: Player) -> bool:
    return any(stack.item == "lit torch" and torch_has_fuel(stack) for stack in player.carried)


def player_has_fire_source(player: Player) -> bool:
    for stack in player.carried:
        if stack.item == "lit torch" and torch_has_fuel(stack):
            return True
        if stack.item in FIRE_SOURCE_ITEMS and stack.item != "lit torch":
            return True
    return False


def light_state_for_player(world: World, player: Player, location: Location) -> str:
    if not location_is_dark(location) and 6 <= world.minute // 60 < 18:
        return "daylight"
    if active_fire(location):
        return "firelit"
    if player_has_lit_torch(player):
        return "torchlit"
    return "dark"


def player_has_light_at(world: World, player: Player, location: Location) -> bool:
    return light_state_for_player(world, player, location) != "dark"


def move_destination_allowed(world: World, player: Player, destination: str) -> bool:
    if destination not in discovered_neighbor_names(world, player.location):
        return False
    current_location = world.locations[player.location]
    destination_location = world.locations[destination]
    if not location_is_dark(destination_location):
        return True
    if location_is_dark(current_location) and not player_has_light_at(world, player, current_location):
        return True
    return player_has_lit_torch(player) or active_fire(destination_location) is not None


def allowed_move_destinations(world: World, player: Player) -> list[str]:
    return [name for name in discovered_neighbor_names(world, player.location) if move_destination_allowed(world, player, name)]


def torch_lighting_source_available(location: Location, player: Player) -> bool:
    return active_fire(location) is not None or player_has_fire_source(player)


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
            "parasite_control": 100 - conditions.get("parasites", 0),
            "malaria_resistance": 100 - conditions.get("malaria", 0),
            "infection_control": 100 - conditions.get("bacterial_infection", 0),
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
    stats["antibiotic_coverage"] = min(stats.get("antibiotic_coverage", 100), stats["immunity"], stats["infection_control"])
    stats["jasmine_restfulness"] = min(stats.get("jasmine_restfulness", 100), stats["calm"], stats["wakefulness"])
    if strong_sunlight(world, player.location, loc) and 10 <= world.minute // 60 < 17 and not sheltered:
        stats["sun_protection"] = min(stats.get("sun_protection", 100), 45 + stats.get("tanning", 75) // 4)
        stats["heat_protection"] = min(stats.get("heat_protection", 100), 70)
    if is_raining(world.weather) and not sheltered:
        stats["rain_protection"] = min(stats.get("rain_protection", 100), 35)
    if mosquito_pressure_at(world, player, loc):
        repellent_floor = clamp(55 + conditions.get("bug_repellent", 0) // 2, 0, 100)
        stats["bug_protection"] = min(stats.get("bug_protection", 100), repellent_floor)
    stats["foot_protection"] = min(stats.get("foot_protection", 100), 100 - conditions.get("foot_damage", 0) // 2)
    return {key: clamp(int(stats.get(key, 100)), 0, 100) for key in PLAYER_STAT_KEYS}


def sun_exposed(location_name: str, location: Location) -> bool:
    return location_name in {"atoll", "bay", "beach", "bird rock", "desolate beach", "rocks"} or any(
        feature in location.features for feature in {"open sun", "sand", "hot ground", "cliffs"}
    )


def strong_sunlight(world: World, location_name: str, location: Location) -> bool:
    hour = world.minute // 60
    return weather_sun_strength(world.weather) >= 4 and 7 <= hour < 17 and sun_exposed(location_name, location)


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


def mosquito_pressure_at(world: World, player: Player, location: Location) -> bool:
    return (
        player.location in {"jungle", "deep jungle", "mangrove forest", "wetlands"}
        or (canonical_weather(world.weather) == "clear" and water_reservoir_mosquito_pressure(location))
    ) and not active_fire(location)


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
        (container for container in carried_storage_stacks(player) if storage_can_accept_stack(container.data, stack)),
        None,
    )


def carried_storage_with_item(player: Player, item: str) -> ItemStack | None:
    return next(
        (
            container
            for container in carried_storage_stacks(player)
            if any(stack.item == item for stack in storage_contents(container.data))
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


def raft_frame_at(location: Location) -> PlacedObject | None:
    return next((obj for obj in location.placed if obj.kind == "raft frame" and obj.active), None)


def raft_build_stage_index(location: Location) -> int:
    frame = raft_frame_at(location)
    if frame is None:
        return 0
    return max(0, min(len(RAFT_BUILD_STAGES), int(frame.data.get("stage", 0))))


def count_nearby_material(player: Player, location: Location, item: str) -> int:
    return (
        count_material(player.carried, item)
        + count_material(location.ground, item)
        + sum(count_material(storage_contents(obj.data), item) for obj in placed_storage_objects(location))
    )


def raft_stage_requirements_met(world: World, player: Player) -> bool:
    if player.location not in RAFT_BUILD_LOCATIONS or world.locations["raft"].discovered:
        return False
    if any(p.current_action and p.current_action.name == "build raft" for p in world.players.values()):
        return False
    loc = world.locations[player.location]
    if not player_has_light_at(world, player, loc):
        return False
    stage_index = raft_build_stage_index(loc)
    if stage_index >= len(RAFT_BUILD_STAGES):
        return False
    stage = RAFT_BUILD_STAGES[stage_index]
    if not all(count_nearby_material(player, loc, item) >= qty for item, qty in stage["materials"].items()):
        return False
    return all(count_tool(player.carried, item) >= 1 for item in stage["tool_wear"])


def reserve_raft_stage_materials(player: Player, location: Location, stage_index: int, args: dict[str, Any]) -> list[ItemStack]:
    reserved = []
    sources = []
    for item, qty in RAFT_BUILD_STAGES[stage_index]["materials"].items():
        remaining = qty
        for source, stacks in (("carried", player.carried), ("ground", location.ground)):
            if remaining <= 0:
                break
            removed = remove_material(stacks, item, min(remaining, count_material(stacks, item)))
            reserved.extend(removed)
            sources.extend({"source": source} for _ in removed)
            remaining -= sum(stack.qty for stack in removed)
        for placed_index, obj in enumerate(location.placed):
            if remaining <= 0:
                break
            if not obj.active or not isinstance(obj.data, dict) or "storage_capacity" not in obj.data:
                continue
            contents = storage_contents(obj.data)
            removed = remove_material(contents, item, min(remaining, count_material(contents, item)))
            if removed:
                set_storage_contents(obj.data, contents)
                reserved.extend(removed)
                sources.extend({"source": "storage", "placed_index": placed_index} for _ in removed)
                remaining -= sum(stack.qty for stack in removed)
        if remaining:
            raise ValueError(f"missing {item} for raft stage")
    args["reserved_sources"] = sources
    return reserved


def packable_carried_stacks(player: Player) -> list[ItemStack]:
    return [stack for stack in player.carried if not stack_is_storage(stack)]


def stack_matches_carried_stack(existing: ItemStack, incoming: ItemStack) -> bool:
    return (
        existing.item == incoming.item
        and existing.age_minutes == incoming.age_minutes
        and existing.exposed == incoming.exposed
        and existing.data == incoming.data
    )


def stack_equipped_slot(stack: ItemStack) -> str | None:
    if not stack_is_storage(stack):
        return None
    if stack.data.get("equipped_slot"):
        return str(stack.data["equipped_slot"])
    if stack.item == "woven backpack" or stack.data.get("equipped_weight_reduction"):
        return "back"
    return None


def wearable_backpack_stacks(player: Player) -> list[ItemStack]:
    return [stack for stack in player.carried if stack_equipped_slot(stack) == "back"]


def worn_backpack_stack(player: Player) -> ItemStack | None:
    backpacks = wearable_backpack_stacks(player)
    if not backpacks:
        return None
    return max(
        backpacks,
        key=lambda stack: (
            int(stack.data.get("equipped_weight_reduction", 0)),
            int(stack.data.get("storage_capacity", 0)),
        ),
    )


def stack_would_be_worn_on_back(player: Player, stack: ItemStack) -> bool:
    return stack_equipped_slot(stack) == "back" and worn_backpack_stack(player) is None


def stack_can_be_carried_in_hand(stack: ItemStack) -> bool:
    return not stack_is_storage(stack) or stack.item in HAND_CARRIED_STORAGE_KINDS


def carried_storage_stacks(player: Player) -> list[ItemStack]:
    worn = worn_backpack_stack(player)
    return [
        stack
        for stack in player.carried
        if stack_is_storage(stack) and (stack is worn or stack.item in HAND_CARRIED_STORAGE_KINDS)
    ]


def carry_error_for_stack(player: Player, stack: ItemStack) -> str:
    if (
        stack_is_storage(stack)
        and not stack_would_be_worn_on_back(player, stack)
        and not stack_can_be_carried_in_hand(stack)
    ):
        return f"cannot carry {stack.item} in hand"
    return f"no free carry slot for {stack.item}"


def loose_carry_slots_used(player: Player) -> int:
    worn = worn_backpack_stack(player)
    return sum(1 for stack in player.carried if stack is not worn)


def stack_needs_loose_slot(player: Player, stack: ItemStack) -> bool:
    if stack_would_be_worn_on_back(player, stack):
        return False
    if stack_is_storage(stack):
        return True
    return not any(
        not stack_is_storage(existing) and stack_matches_carried_stack(existing, stack)
        for existing in player.carried
    )


def carrying_load(player: Player) -> dict[str, int | str | bool]:
    loose_weight = 0
    container_weight = 0
    packed_weight = 0
    relief = 0
    worn_backpack = worn_backpack_stack(player)
    for stack in player.carried:
        if stack_is_storage(stack):
            own_weight = item_unit_weight(stack.item) * stack.qty
            container_weight += own_weight
            content_weight = storage_content_weight(stack.data)
            packed_weight += content_weight
            relief += min(content_weight, int(stack.data.get("weight_reduction", 0)))
            if stack is worn_backpack:
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
        "loose_slots": loose_carry_slots_used(player),
        "loose_slot_capacity": BASE_LOOSE_CARRY_SLOTS,
        "back_slots": 1 if worn_backpack else 0,
        "back_slot_capacity": BACK_SLOT_CAPACITY,
        "burden": burden,
        "status": status,
        "overburdened": effective_weight > MAX_EFFECTIVE_CARRY,
    }


def effective_weight_for_carried_stack(stack: ItemStack, *, worn_on_back: bool = False) -> int:
    if not stack_is_storage(stack):
        return stack_weight(stack)
    own_weight = item_unit_weight(stack.item) * stack.qty
    content_weight = storage_content_weight(stack.data)
    relief = min(content_weight, int(stack.data.get("weight_reduction", 0)))
    if worn_on_back:
        relief += min(own_weight, int(stack.data.get("equipped_weight_reduction", 0)))
    return max(0, own_weight + content_weight - relief)


def can_carry_loose_stack(player: Player, stack: ItemStack) -> bool:
    worn_on_back = stack_would_be_worn_on_back(player, stack)
    if stack_is_storage(stack) and not worn_on_back and not stack_can_be_carried_in_hand(stack):
        return False
    if (
        int(carrying_load(player)["effective_weight"])
        + effective_weight_for_carried_stack(stack, worn_on_back=worn_on_back)
        > MAX_EFFECTIVE_CARRY
    ):
        return False
    return not stack_needs_loose_slot(player, stack) or loose_carry_slots_used(player) < BASE_LOOSE_CARRY_SLOTS


def add_items_to_carried_or_ground(
    world: World,
    player: Player,
    item: str,
    qty: int = 1,
    *,
    age_minutes: int = 0,
    exposed: bool = True,
    data: dict[str, Any] | None = None,
) -> None:
    candidate = ItemStack(item, qty, age_minutes, exposed, deepcopy(data or {}))
    if can_carry_loose_stack(player, candidate):
        add_items(player.carried, item, qty, age_minutes=age_minutes, exposed=exposed, data=data)
        return
    loc = world.locations[player.location]
    add_items(loc.ground, item, qty, age_minutes=age_minutes, exposed=exposed, data=data)
    log_event(world, f"{player.name} had no free carry slot, so {qty} {item} was left at {player.location}.")


def one_item_stack(stack: ItemStack) -> ItemStack:
    return ItemStack(stack.item, 1, stack.age_minutes, stack.exposed, deepcopy(stack.data))


def pickup_candidates(location: Location) -> list[ItemStack]:
    return [one_item_stack(stack) for stack in location.ground] + [
        ItemStack(obj.kind, 1, data=deepcopy(obj.data)) for obj in pickable_storage_objects(location)
    ]


def unpack_candidates(player: Player) -> list[ItemStack]:
    return [
        one_item_stack(content)
        for container in carried_storage_stacks(player)
        for content in storage_contents(container.data)
    ]


def retrieve_candidates(location: Location) -> list[ItemStack]:
    return [
        one_item_stack(content)
        for obj in placed_storage_objects(location)
        for content in storage_contents(obj.data)
    ]


def placed_basket_at(location: Location) -> PlacedObject | None:
    return next((obj for obj in location.placed if obj.kind == "basket" and obj.active), None)


def vessel_fill_source(world: World, player: Player) -> tuple[str, int | None, str] | None:
    loc = world.locations[player.location]
    if cistern_with_water(loc):
        return "clean water", None, "cistern"
    if water_reservoir_with_water(loc):
        return "clean water", None, "water reservoir"
    if is_raining(world.weather):
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
    actions = ["explore"]
    if player.location in WALK_LOCATIONS and player_has_light_at(world, player, loc):
        actions.append("go for a walk")
    if any(can_carry_loose_stack(player, ItemStack(item)) for item in gather_items_for_location(loc)):
        actions.append("gather")
    actions.extend(["rest", "leisure"])
    if any(not stack_is_storage(stack) for stack in player.carried):
        actions.append("drop")
    if worn_backpack_stack(player):
        actions.append("take off backpack")
    actions.extend(["pick up"] if any(can_carry_loose_stack(player, stack) for stack in pickup_candidates(loc)) else [])
    if any(carried_storage_for_stack(player, stack) for stack in packable_carried_stacks(player)):
        actions.append("pack")
    if any(can_carry_loose_stack(player, stack) for stack in unpack_candidates(player)):
        actions.append("unpack")
    if placed_storage_objects(loc) and any(placed_storage_for_stack(loc, stack) for stack in packable_carried_stacks(player)):
        actions.append("store")
    if any(can_carry_loose_stack(player, stack) for stack in retrieve_candidates(loc)):
        actions.append("retrieve")
    water_here = player.location in WATER_LOCATIONS or has_location_card(
        loc, "sea", "seawater", "tide pool", "flooded tide pool"
    )
    actions.extend(["wash", "swim"] if water_here else [])
    actions.extend(["move"] if allowed_move_destinations(world, player) else [])
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
    if resource_available(loc, "coconut palm"):
        actions.append("harvest coconuts")
    for action, data in RESOURCE_HARVESTS.items():
        if resource_available(loc, str(data["resource"])) and action_prerequisites_met(world, player, action):
            actions.append(action)
    if has_location_card(loc, "tide pool") and player_has_light_at(world, player, loc):
        actions.append("forage tide pool")
    if dive_here(loc, player.location) and player_has_light_at(world, player, loc) and player.needs["fatigue"] <= DIVE_MAX_FATIGUE:
        actions.append("dive")
    if ready_fish_trap(loc):
        actions.append("check fish trap")
    if ready_snare_trap(loc):
        actions.append("check snare trap")
    for action in PREREQUISITE_ACTIONS:
        if action_prerequisites_met(world, player, action):
            actions.append(action)
    fish_here = line_fish_here(loc, player.location)
    if fish_here and player_has_tool_inputs(player, "fish"):
        actions.append("fish")
        if player_has_action_inputs(player, "fish with bait"):
            actions.append("fish with bait")
    if spear_fish_here(loc, player.location) and player_has_tool_inputs(player, "spear fish") and player_has_light_at(
        world, player, loc
    ):
        actions.append("spear fish")
    if active_fire(loc):
        if count_item(player.carried, "sticks"):
            actions.append("tend fire")
    if active_fire(loc) or player_has_lit_torch(player):
        if any(count_item(player.carried, item) for item in TINDER_ITEMS):
            actions.append("light tinder from fire")
    if any(stack.item == "torch" and torch_has_fuel(stack) for stack in player.carried) and torch_lighting_source_available(
        loc, player
    ):
        actions.append("light torch")
    if count_tool(player.carried, "hand drill") and any(
        count_item(player.carried, item) for item in TINDER_ITEMS
    ):
        actions.append("light tinder with hand drill")
    if count_tool(player.carried, "bow drill") and any(
        count_item(player.carried, item) for item in TINDER_ITEMS
    ):
        actions.append("light tinder with bow drill")
    if (
        count_tool(player.carried, "signaling mirror")
        and strong_sunlight(world, player.location, loc)
        and any(count_item(player.carried, item) for item in TINDER_ITEMS)
    ):
        actions.append("light tinder with mirror")
    if location_is_dark(loc) and not player_has_light_at(world, player, loc):
        actions = [action for action in actions if action in DARK_ALLOWED_ACTIONS]
    if carrying_load(player)["overburdened"]:
        actions = [action for action in actions if action not in LOAD_BLOCKED_ACTIONS]
    return order_actions_by_recent(actions, player.action_history)


def order_actions_by_recent(actions: list[str], action_history: list[str]) -> list[str]:
    available = list(dict.fromkeys(actions))
    available_set = set(available)
    recent = [action for action in dict.fromkeys(action_history) if action in available_set]
    return recent + [action for action in available if action not in recent]


def sleep_data(world: World) -> dict[str, Any]:
    players = sorted(player.name for player in world.players.values() if player.connected and player.status == "alive")
    resting = [
        name
        for name in players
        if world.players[name].current_action and world.players[name].current_action.name == "rest"
    ]
    waiting_for = [name for name in players if name not in resting]
    return {
        "all_resting": bool(players) and not waiting_for,
        "resting": resting,
        "waiting_for": waiting_for,
    }


def blocked_action_hints(world: World, player: Player, current_actions: list[str]) -> list[dict[str, Any]]:
    if world.outcome is not None or player.status != "alive":
        return []
    current = set(current_actions)
    hints = []
    for action_name in BLOCKED_ACTION_HINTS:
        if (
            action_name in current
            or action_name not in ACTION_DURATIONS
            or not blocked_action_relevant(world, player, action_name)
        ):
            continue
        blockers = action_blockers(world, player, action_name)
        if blockers:
            hints.append({"action": action_name, "missing": blockers[:5]})
        if len(hints) >= MAX_BLOCKED_ACTION_HINTS:
            break
    return hints


def blocked_action_relevant(world: World, player: Player, action_name: str) -> bool:
    loc = world.locations[player.location]
    if action_name == "build raft":
        return not world.locations["raft"].discovered
    if action_name == "start fire":
        return active_fire(loc) is None
    if action_name == "boil water":
        return active_fire(loc) is not None or count_material(player.carried, "unsafe water") > 0
    if action_name in {"build drying rack", "build water filter", "build kiln", "build forge"}:
        return not has_object(loc, action_name.removeprefix("build "))
    if action_name == "build fish trap":
        return fish_trap_can_be_built(player.location, loc) or any(
            count_material(player.carried, item) for item in ACTION_INPUTS[action_name]
        )
    if action_name == "build snare trap":
        return snare_trap_can_be_built(loc) or any(
            count_material(player.carried, item) for item in ACTION_INPUTS[action_name]
        )
    if action_name == "make copper needles":
        return count_material(player.carried, "copper sheet") > 0 or count_tool(player.carried, "copper knife") > 0
    return True


def action_blockers(world: World, player: Player, action_name: str) -> list[dict[str, Any]]:
    loc = world.locations[player.location]
    blockers: list[dict[str, Any]] = []
    if action_name == "build raft":
        if player.location not in RAFT_BUILD_LOCATIONS:
            add_blocker(blockers, {"kind": "location", "name": "beach"})
        if world.locations["raft"].discovered:
            add_blocker(blockers, {"kind": "complete", "name": "raft"})
        if any(p.current_action and p.current_action.name == "build raft" for p in world.players.values()):
            add_blocker(blockers, {"kind": "busy", "action": "build raft"})
        if not player_has_light_at(world, player, loc):
            add_blocker(blockers, {"kind": "light"})
        stage_index = raft_build_stage_index(loc)
        if stage_index < len(RAFT_BUILD_STAGES):
            stage = RAFT_BUILD_STAGES[stage_index]
            for item, qty in stage["materials"].items():
                have = count_nearby_material(player, loc, item)
                if have < qty:
                    add_blocker(
                        blockers,
                        {"kind": "item", "item": item, "qty": qty - have, "have": have, "nearby": True},
                    )
            for item, qty in stage["tool_wear"].items():
                have = count_tool(player.carried, item)
                if have < qty:
                    add_blocker(blockers, {"kind": "tool", "item": item, "qty": qty - have, "have": have})
        else:
            add_blocker(blockers, {"kind": "complete", "name": "raft frame"})
        add_global_action_blockers(world, player, action_name, blockers)
        return blockers

    add_missing_inputs(player, action_name, blockers)
    add_missing_tools(player, action_name, blockers)
    if action_name in FIRE_REQUIRED_ACTIONS and active_fire(loc) is None:
        add_blocker(blockers, {"kind": "fire"})
    if action_name in LIGHT_REQUIRED_ACTIONS and not player_has_light_at(world, player, loc):
        add_blocker(blockers, {"kind": "light"})
    if action_name == "collect salt water" and not salt_water_here(loc):
        add_blocker(blockers, {"kind": "resource", "name": "salt water"})
    if action_name in {"collect sand", "dig up sand", "build sand castle"} and not sand_here(loc):
        add_blocker(blockers, {"kind": "resource", "name": "sand"})
    if action_name == "make quicklime" and hot_kiln_at(loc, 600) is None:
        add_blocker(blockers, {"kind": "object", "name": "hot kiln"})
    if action_name == "mine copper ore" and not copper_vein_can_be_mined(loc):
        add_blocker(blockers, {"kind": "resource", "name": "copper vein"})
    if action_name == "smelt copper" and hot_kiln_at(loc, COPPER_SMELT_TEMPERATURE) is None:
        add_blocker(blockers, {"kind": "object", "name": "hot advanced kiln or forge"})
    if action_name in COPPER_CASTING_OUTPUTS and hot_kiln_at(loc, COPPER_SMELT_TEMPERATURE) is None:
        add_blocker(blockers, {"kind": "object", "name": "hot advanced kiln or forge"})
    if action_name == "build advanced kiln" and not advanced_kiln_can_be_built(loc):
        add_blocker(blockers, {"kind": "complete", "name": "advanced kiln"})
    if action_name == "build forge" and not forge_can_be_built(loc):
        add_blocker(blockers, {"kind": "complete", "name": "forge"})
    if action_name == "build shed" and not placed_structure_can_be_built(loc, "shed"):
        add_blocker(blockers, {"kind": "complete", "name": "shed"})
    if action_name == "build mud hut" and not placed_structure_can_be_built(loc, "mud hut"):
        add_blocker(blockers, {"kind": "complete", "name": "mud hut"})
    if action_name == "build stone hut" and not stone_hut_can_be_built(loc):
        add_blocker(blockers, {"kind": "complete", "name": "stone hut"})
    if action_name == "build cellar" and not placed_structure_can_be_built(loc, "cellar"):
        add_blocker(blockers, {"kind": "complete", "name": "cellar"})
    if action_name == "build well" and not well_can_be_built(player.location, loc):
        add_blocker(blockers, {"kind": "location", "name": "wetlands"})
    if action_name == "build cistern" and not cistern_can_be_built(loc):
        add_blocker(blockers, {"kind": "complete", "name": "cistern"})
    if action_name == "fill vessel":
        source = vessel_fill_source(world, player)
        if source is None:
            add_blocker(blockers, {"kind": "resource", "name": "water source"})
        elif carried_vessel_for_fill(player, source[0]) is None:
            add_blocker(blockers, {"kind": "item", "item": "empty vessel", "qty": 1, "have": 0})
    if action_name in {"drink from vessel", "empty vessel"} and carried_vessel_with_liquid(player) is None:
        add_blocker(blockers, {"kind": "item", "item": "filled vessel", "qty": 1, "have": 0})
    if action_name in {"dry fish", "dry cinchona bark"} and not has_object(loc, "drying rack"):
        add_blocker(blockers, {"kind": "object", "name": "drying rack"})
    if action_name == "filter water" and not has_object(loc, "water filter"):
        add_blocker(blockers, {"kind": "object", "name": "water filter"})
    if action_name == "build fish trap" and not fish_trap_can_be_built(player.location, loc):
        add_blocker(blockers, {"kind": "resource", "name": "shore water"})
    if action_name == "build snare trap" and not snare_trap_can_be_built(loc):
        add_blocker(blockers, {"kind": "resource", "name": "tree cover"})
    if action_name == "bait snare trap" and baitable_snare_trap(loc) is None:
        add_blocker(blockers, {"kind": "object", "name": "empty snare trap"})
    if action_name == "fuel kiln" and fuelable_kiln_at(loc) is None:
        add_blocker(blockers, {"kind": "object", "name": "kiln or forge"})
    if action_name == "fuel kiln" and not player_has_kiln_fuel(player):
        add_blocker(blockers, {"kind": "item", "item": "fuel", "qty": 1, "have": 0})
    if action_name == "light kiln" and lightable_kiln_at(loc) is None:
        add_blocker(blockers, {"kind": "object", "name": "fueled kiln or forge"})
    if action_name == "light kiln" and active_fire(loc) is None:
        add_blocker(blockers, {"kind": "fire"})
    if action_name in KILN_FIRING:
        firing = KILN_FIRING[action_name]
        if firing["heat"] == "kiln" and hot_kiln_at(loc, int(firing["temperature"])) is None:
            add_blocker(blockers, {"kind": "object", "name": "hot kiln"})
        if (
            firing["heat"] != "kiln"
            and active_fire(loc) is None
            and hot_kiln_at(loc, int(firing["temperature"])) is None
        ):
            add_blocker(blockers, {"kind": "object", "name": "fire or hot kiln"})
    add_global_action_blockers(world, player, action_name, blockers)
    return blockers


def add_missing_inputs(player: Player, action_name: str, blockers: list[dict[str, Any]]) -> None:
    for item, qty in ACTION_INPUTS.get(action_name, {}).items():
        have = count_material(player.carried, item)
        if have < qty:
            add_blocker(blockers, {"kind": "item", "item": item, "qty": qty - have, "have": have})


def add_missing_tools(player: Player, action_name: str, blockers: list[dict[str, Any]]) -> None:
    for item, qty in TOOL_REQUIREMENTS.get(action_name, {}).items():
        have = count_tool(player.carried, item)
        if have < qty:
            add_blocker(blockers, {"kind": "tool", "item": item, "qty": qty - have, "have": have})


def add_global_action_blockers(world: World, player: Player, action_name: str, blockers: list[dict[str, Any]]) -> None:
    loc = world.locations[player.location]
    if (
        location_is_dark(loc)
        and action_name not in DARK_ALLOWED_ACTIONS
        and not player_has_light_at(world, player, loc)
    ):
        add_blocker(blockers, {"kind": "light"})
    if carrying_load(player)["overburdened"] and action_name in LOAD_BLOCKED_ACTIONS:
        add_blocker(blockers, {"kind": "load"})


def add_blocker(blockers: list[dict[str, Any]], blocker: dict[str, Any]) -> None:
    if blocker not in blockers:
        blockers.append(blocker)


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
    if action_name == "add rope to basket":
        return count_item(player.carried, "basket") > 0 or placed_basket_at(loc) is not None
    if action_name == "collect sand":
        return sand_here(loc)
    if action_name in {"dig up sand", "build sand castle"}:
        return sand_here(loc)
    if action_name in LIGHT_REQUIRED_ACTIONS:
        return player_has_light_at(world, player, loc)
    if action_name in {"fish", "fish with bait"}:
        return line_fish_here(loc, player.location)
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
    if action_name == "build raft":
        return raft_stage_requirements_met(world, player)
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
    if action_name in {"dry fish", "dry cinchona bark"}:
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
    return all(count_material(player.carried, item) >= qty for item, qty in ACTION_INPUTS.get(action_name, {}).items())


def player_has_tool_inputs(player: Player, action_name: str) -> bool:
    return all(count_tool(player.carried, item) >= qty for item, qty in TOOL_REQUIREMENTS.get(action_name, {}).items())


def tool_options(item: str) -> tuple[str, ...]:
    return TOOL_ALTERNATIVES.get(item, (item,))


def count_tool(stacks: list[ItemStack], item: str) -> int:
    options = set(tool_options(item))
    return sum(stack.qty for stack in stacks if stack.item in options)


def count_material(stacks: list[ItemStack], item: str) -> int:
    options = MATERIAL_ALTERNATIVES.get(item, (item,))
    return sum(count_item(stacks, option) for option in options)


def remove_material(stacks: list[ItemStack], item: str, qty: int) -> list[ItemStack]:
    removed = []
    remaining = qty
    for option in MATERIAL_ALTERNATIVES.get(item, (item,)):
        take = min(remaining, count_item(stacks, option))
        if take:
            removed.extend(remove_items(stacks, option, take))
            remaining -= take
        if remaining <= 0:
            break
    return removed


def remove_from_stack(stacks: list[ItemStack], stack: ItemStack, qty: int = 1) -> list[ItemStack]:
    index = next((index for index, existing in enumerate(stacks) if existing is stack), -1)
    if index < 0:
        raise ValueError(f"missing {stack.item}")
    if qty > stack.qty:
        raise ValueError(f"missing {qty} {stack.item}")
    stack.qty -= qty
    removed = [ItemStack(stack.item, qty, stack.age_minutes, stack.exposed, deepcopy(stack.data))]
    if stack.qty == 0:
        del stacks[index]
    return removed


def indexed_stack(stacks: list[ItemStack], args: dict[str, Any], key: str, *, item: str | None = None) -> ItemStack | None:
    if key not in args:
        return None
    index = int(args[key])
    if index < 0 or index >= len(stacks):
        raise ValueError("item index out of range")
    stack = stacks[index]
    if item is not None and stack.item != item:
        raise ValueError(f"item index points to {stack.item}, not {item}")
    return stack


def indexed_carried_stack(
    player: Player,
    args: dict[str, Any],
    *,
    item: str | None = None,
    storage: bool | None = None,
) -> ItemStack | None:
    stack = indexed_stack(player.carried, args, "carried_index", item=item)
    if stack is None:
        return None
    if storage is True and not stack_is_storage(stack):
        raise ValueError(f"{stack.item} is not storage")
    if storage is False and stack_is_storage(stack):
        raise ValueError("use the storage-specific action for containers")
    return stack


def indexed_storage_content(data: dict[str, Any], args: dict[str, Any], *, item: str | None = None) -> ItemStack | None:
    return indexed_stack(storage_contents(data), args, "content_index", item=item)


def indexed_ground_stack(location: Location, args: dict[str, Any], *, item: str | None = None) -> ItemStack | None:
    return indexed_stack(location.ground, args, "ground_index", item=item)


def remove_indexed_storage_content(data: dict[str, Any], index: int, qty: int) -> list[ItemStack]:
    contents = storage_contents(data)
    removed = remove_from_stack(contents, contents[index], qty)
    set_storage_contents(data, contents)
    return removed


def indexed_placed_storage(location: Location, args: dict[str, Any]) -> PlacedObject | None:
    if "placed_index" not in args:
        return None
    index = int(args["placed_index"])
    if index < 0 or index >= len(location.placed):
        raise ValueError("placed index out of range")
    obj = location.placed[index]
    if not obj.active or not isinstance(obj.data, dict) or "storage_capacity" not in obj.data:
        raise ValueError(f"{obj.kind} is not placed storage")
    return obj


def indexed_pickable_placed_storage(location: Location, args: dict[str, Any], *, item: str | None = None) -> PlacedObject | None:
    obj = indexed_placed_storage(location, args)
    if obj is None:
        return None
    if obj.kind not in PICKABLE_STORAGE_KINDS:
        raise ValueError(f"{obj.kind} cannot be picked up")
    if item is not None and obj.kind != item:
        raise ValueError(f"placed index points to {obj.kind}, not {item}")
    return obj


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
        candidate = ItemStack(str(args["item"]))
        if not can_carry_loose_stack(player, candidate):
            raise ValueError(carry_error_for_stack(player, candidate))
    if action_name == "harvest coconuts":
        resource = loc.resources.get("coconut palm")
        if not resource or (not resource.get("infinite") and int(resource.get("qty", 0)) <= 0):
            raise ValueError(f"coconut palms are depleted at {player.location}")
        if not resource.get("infinite"):
            resource["qty"] = int(resource.get("qty", 0)) - 1
            args["reserved_resource"] = "coconut palm"
    if action_name in RESOURCE_HARVESTS:
        resource_name = str(RESOURCE_HARVESTS[action_name]["resource"])
        resource = loc.resources.get(resource_name)
        if not resource or (not resource.get("infinite") and int(resource.get("qty", 0)) <= 0):
            raise ValueError(f"{resource_name} is depleted at {player.location}")
        if not resource.get("infinite"):
            resource["qty"] = int(resource.get("qty", 0)) - 1
            args["reserved_resource"] = resource_name
    if action_name == "move":
        destinations = allowed_move_destinations(world, player)
        destination = str(args["location"]) if "location" in args else destinations[0]
        if destination not in discovered_neighbor_names(world, player.location):
            raise ValueError("destination is not a discovered neighbor")
        if destination not in destinations:
            raise ValueError("it is too dark to enter without a carried light")
        args["location"] = destination
    if action_name == "fuel kiln":
        requested = args.get("item")
        fuel_items = [item for item in KILN_FUEL_VALUES if count_item(player.carried, item)]
        if requested is not None and requested not in fuel_items:
            raise ValueError(f"cannot fuel kiln with {requested}")
        args["item"] = str(requested or fuel_items[0])
    if action_name in TINDER_LIGHTING_ACTIONS:
        tinder_items = [item for item in TINDER_ITEMS if count_item(player.carried, item)]
        requested = args.get("item")
        if requested is not None and requested not in tinder_items:
            raise ValueError(f"cannot light {requested}")
        args["item"] = str(requested or tinder_items[0])
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
        source = indexed_carried_stack(player, args, storage=False)
        item = source.item if source else args.get("item") or next((stack.item for stack in packable_carried_stacks(player)), None)
        qty = int(args.get("qty", 1))
        if source is None:
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
        source_container = indexed_carried_stack(player, args, storage=True)
        selected_content = indexed_storage_content(source_container.data, args) if source_container else None
        item = selected_content.item if selected_content else args.get("item") or next(
            (content.item for content in unpack_candidates(player)),
            None,
        )
        if source_container is None:
            source_container = carried_storage_with_item(player, str(item)) if item is not None else None
        if item is None or source_container is None:
            raise ValueError(f"no carried container has {item}")
        stack = selected_content or next(content for content in storage_contents(source_container.data) if content.item == item)
        candidate = ItemStack(stack.item, min(int(args.get("qty", 1)), stack.qty), stack.age_minutes, stack.exposed, deepcopy(stack.data))
        if not can_carry_loose_stack(player, candidate):
            raise ValueError(carry_error_for_stack(player, candidate))
        args["item"] = str(item)
        args["qty"] = candidate.qty
    if action_name == "retrieve":
        source_storage = indexed_placed_storage(loc, args)
        selected_content = indexed_storage_content(source_storage.data, args) if source_storage else None
        item = selected_content.item if selected_content else args.get("item") or next(
            (content.item for obj in placed_storage_objects(loc) for content in storage_contents(obj.data)),
            None,
        )
        if source_storage is None:
            source_storage = placed_storage_with_item(loc, str(item)) if item is not None else None
        if source_storage is None:
            raise ValueError(f"no placed storage has {item}")
        stack = selected_content or next(content for content in storage_contents(source_storage.data) if content.item == item)
        candidate = ItemStack(stack.item, min(int(args.get("qty", 1)), stack.qty), stack.age_minutes, stack.exposed, deepcopy(stack.data))
        if not can_carry_loose_stack(player, candidate):
            raise ValueError(carry_error_for_stack(player, candidate))
        args["item"] = str(item)
        args["qty"] = candidate.qty
    reserved = []
    if action_name == "build raft":
        stage_index = raft_build_stage_index(loc)
        args["raft_stage"] = stage_index
        args["raft_stages"] = len(RAFT_BUILD_STAGES)
        reserved.extend(reserve_raft_stage_materials(player, loc, stage_index, args))
    elif action_name == "add rope to basket":
        carried_basket = indexed_carried_stack(player, args, item="basket", storage=True)
        if carried_basket is None:
            carried_basket = next((stack for stack in player.carried if stack.item == "basket"), None)
        if carried_basket:
            removed = remove_from_stack(player.carried, carried_basket, 1)
            args["basket_data"] = deepcopy(removed[0].data)
            args["basket_source"] = "carried"
        else:
            basket = placed_basket_at(loc)
            if basket is None:
                raise ValueError("no basket here")
            args["basket_data"] = deepcopy(basket.data)
            args["basket_source"] = "placed"
            loc.placed.remove(basket)
        reserved.extend(remove_material(player.carried, "rope", 1))
    elif action_name == "take off backpack":
        backpack = worn_backpack_stack(player)
        if backpack is None:
            raise ValueError("no worn backpack")
        player.carried.remove(backpack)
        reserved.append(backpack)
    elif action_name == "place basket":
        basket = indexed_carried_stack(player, args, item="basket", storage=True)
        if basket is None:
            basket = next((stack for stack in player.carried if stack.item == "basket"), None)
        if basket is None:
            raise ValueError("missing basket")
        reserved.extend(remove_from_stack(player.carried, basket, 1))
    elif action_name in ACTION_INPUTS:
        for item, qty in ACTION_INPUTS[action_name].items():
            reserved.extend(remove_material(player.carried, item, qty))
    if action_name == "pick up":
        requested_item = str(args["item"]) if "item" in args else None
        source = indexed_ground_stack(loc, args, item=requested_item)
        item = source.item if source is not None else requested_item
        if item is None:
            item = loc.ground[0].item if loc.ground else pickable_storage_objects(loc)[0].kind if pickable_storage_objects(loc) else None
        if source is None and "ground_index" not in args:
            source = next((stack for stack in loc.ground if stack.item == item), None)
        if source is not None:
            candidate = ItemStack(source.item, min(int(args.get("qty", 1)), source.qty), source.age_minutes, source.exposed, deepcopy(source.data))
            if not can_carry_loose_stack(player, candidate):
                raise ValueError(carry_error_for_stack(player, candidate))
            args["item"] = source.item
            args["qty"] = candidate.qty
            reserved.extend(remove_from_stack(loc.ground, source, candidate.qty))
        else:
            obj = indexed_pickable_placed_storage(loc, args, item=item) if "placed_index" in args else None
            if obj is None:
                obj = next((placed for placed in pickable_storage_objects(loc) if placed.kind == item), None)
            if obj is None:
                raise ValueError(f"missing {item}")
            candidate = ItemStack(obj.kind, 1, data=deepcopy(obj.data))
            if not can_carry_loose_stack(player, candidate):
                raise ValueError(carry_error_for_stack(player, candidate))
            del loc.placed[next(index for index, placed in enumerate(loc.placed) if placed is obj)]
            args["item"] = obj.kind
            args["placed_storage"] = True
            reserved.append(candidate)
    if action_name == "drop":
        source = indexed_carried_stack(player, args, storage=False)
        item = source.item if source else args.get("item") or next((stack.item for stack in player.carried if not stack_is_storage(stack)), None)
        if source is None:
            source = next((stack for stack in player.carried if stack.item == item), None)
        if source is not None and stack_is_storage(source):
            raise ValueError("use place basket or take off backpack for storage")
        if source is None:
            raise ValueError(f"missing {item}")
        reserved.extend(remove_from_stack(player.carried, source, int(args.get("qty", 1))))
    if action_name in {"pack", "store"}:
        source = indexed_carried_stack(player, args, storage=False)
        if source is None:
            reserved.extend(remove_items(player.carried, str(args["item"]), int(args.get("qty", 1))))
        else:
            reserved.extend(remove_from_stack(player.carried, source, int(args.get("qty", 1))))
    if action_name == "fuel kiln":
        reserved.extend(remove_items(player.carried, str(args["item"]), 1))
    if action_name in TINDER_LIGHTING_ACTIONS:
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
    if action.name == "build raft":
        for source, stack in zip(action.args.get("reserved_sources", []), action.reserved, strict=False):
            source_name = source.get("source") if isinstance(source, dict) else str(source)
            if source_name == "ground":
                add_items(loc.ground, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
            elif source_name == "storage":
                placed_index = int(source.get("placed_index", -1)) if isinstance(source, dict) else -1
                storage = loc.placed[placed_index] if 0 <= placed_index < len(loc.placed) else None
                if storage and storage_can_accept_stack(storage.data, stack):
                    add_stack_to_storage(storage.data, stack)
                else:
                    add_items(loc.ground, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
            else:
                add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
        player.current_action = None
        log_event(world, f"{player.name} cancelled {action.name}.")
        return
    if action.name == "add rope to basket":
        basket_data = deepcopy(action.args.get("basket_data", STORAGE_DATA["basket"]))
        if action.args.get("basket_source") == "placed":
            loc.placed.append(PlacedObject("basket", active=True, data=basket_data))
        else:
            add_items(player.carried, "basket", 1, data=basket_data)
        for stack in action.reserved:
            add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
        player.current_action = None
        log_event(world, f"{player.name} cancelled {action.name}.")
        return
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
    update_weather(world, dt)
    update_tides(world)
    update_weather_events(world, dt)
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


def tick_world_with_sleep_skip(world: World) -> bool:
    day_changed = tick_world(world)
    while not world.paused and world.outcome is None and all_connected_alive_players_sleeping(world):
        day_changed = tick_world(world) or day_changed
    return day_changed


def all_connected_alive_players_sleeping(world: World) -> bool:
    players = [player for player in world.players.values() if player.connected and player.status == "alive"]
    return bool(players) and all(player.current_action and player.current_action.name == "rest" for player in players)


def update_weather(world: World, dt: int) -> None:
    world.season = season_for_day(world.day)
    update_rain_counter(world, dt)
    world.weather_remaining_minutes -= dt
    if world.weather_remaining_minutes > 0:
        return
    world.weather_remaining_minutes = weather_duration_minutes(world.weather)
    current_time = world.day * 1440 + world.minute
    rng = random.Random(f"{world.seed}:weather:{current_time // RAIN_COUNTER_STEP_MINUTES}:{world.season}:{world.rain_counter}")
    old_weather = canonical_weather(world.weather)
    weights = weather_transition_weights(world)
    total = sum(weight for _, weight in weights)
    roll = rng.randrange(total)
    upto = 0
    for weather, weight in weights:
        upto += weight
        if roll < upto:
            world.weather = weather
            break
    if canonical_weather(world.weather) != old_weather:
        log_weather_change(world, canonical_weather(world.weather))
    world.weather_remaining_minutes = weather_duration_minutes(world.weather)


def update_rain_counter(world: World, dt: int) -> None:
    current_time = world.day * 1440 + world.minute
    previous_time = current_time - dt
    first_step = previous_time // RAIN_COUNTER_STEP_MINUTES + 1
    last_step = current_time // RAIN_COUNTER_STEP_MINUTES
    for step in range(first_step, last_step + 1):
        delta = RAIN_COUNTER_SEASON_DELTAS[world.season]
        weather_delta = RAIN_COUNTER_WEATHER_DELTAS.get(canonical_weather(world.weather))
        if weather_delta:
            rng = random.Random(f"{world.seed}:rain-counter:{step}:{canonical_weather(world.weather)}")
            delta += rng.randint(*weather_delta)
        world.rain_counter = clamp(world.rain_counter + delta, RAIN_COUNTER_MIN, RAIN_COUNTER_MAX)


def log_weather_change(world: World, weather: str) -> None:
    if weather == "heavy rain":
        log_event(world, "Heavy rain starts over the island.")
    elif weather == "storm":
        log_event(world, "A storm lashes the island.")
    elif weather == "clear":
        log_event(world, "The sky clears.")


def update_tides(world: World) -> None:
    high_tide = tide_is_high(world)
    for loc in world.locations.values():
        normalize_tide_pool_card(loc, high_tide)


def update_weather_events(world: World, dt: int) -> None:
    current_time = world.day * 1440 + world.minute
    previous_time = current_time - dt
    if current_time // STORM_DAMAGE_INTERVAL_MINUTES == previous_time // STORM_DAMAGE_INTERVAL_MINUTES:
        return
    if is_storm(world.weather):
        apply_storm_event(world)


def apply_storm_event(world: World) -> None:
    for player in world.players.values():
        if not player.connected or player.status != "alive" or player.location not in STORM_EXPOSED_LOCATIONS:
            continue
        loc = world.locations[player.location]
        if sheltered_at(loc):
            continue
        player.conditions["wetness"] = clamp(player.conditions.get("wetness", 0) + STORM_EVENT_WETNESS)
        player.conditions["bruising"] = clamp(player.conditions.get("bruising", 0) + STORM_EVENT_BRUISING)
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) + 2)
        player.needs["stress"] = clamp(player.needs.get("stress", 0) + scale_wiki_delta(12, "stress"))
        player.needs["fatigue"] = clamp(player.needs.get("fatigue", 0) + 3)
        log_event(world, f"Storm winds battered {player.name} at {player.location}.")
    for location_name in STORM_EXPOSED_LOCATIONS:
        loc = world.locations.get(location_name)
        if loc:
            damage_storm_exposed_objects(world, loc)


def damage_storm_exposed_objects(world: World, loc: Location) -> None:
    for obj in list(loc.placed):
        if not obj.active or obj.kind not in STORM_DAMAGE_OBJECTS:
            continue
        rng = random.Random(f"{world.seed}:storm-damage:{loc.name}:{world.day}:{world.minute}:{obj.kind}")
        obj.data["storm_damage"] = clamp(
            int(obj.data.get("storm_damage", 0)) + rng.randint(*STORM_DAMAGE_RANGE)
        )
        if obj.data["storm_damage"] >= 100:
            loc.placed.remove(obj)
            log_event(world, f"A {obj.kind} at {loc.name} was wrecked by the storm.")
        else:
            log_event(world, f"Storm damaged {obj.kind} at {loc.name}.")


def update_player_needs(world: World, player: Player, dt: int) -> None:
    if player.needs.get("health", 100) <= 0:
        finish_world(world, player, "loss", "dead", death_reason(player))
        return
    current_time = world.day * 1440 + world.minute
    previous_time = current_time - dt
    player.needs["thirst"] = clamp(player.needs["thirst"] + current_time // 3 - previous_time // 3, 0, 100)
    player.needs["hunger"] = clamp(player.needs["hunger"] + current_time // 6 - previous_time // 6, 0, 100)
    player.needs["fatigue"] = clamp(player.needs["fatigue"] + current_time // 12 - previous_time // 12, 0, 100)
    health_loss = 0
    if player.needs["thirst"] >= 90:
        health_loss += current_time // 60 - previous_time // 60
    if player.needs["hunger"] >= 95:
        health_loss += current_time // 180 - previous_time // 180
    if health_loss:
        player.needs["health"] = clamp(player.needs["health"] - health_loss)
    if player.needs["health"] <= 0:
        finish_world(world, player, "loss", "dead", death_reason(player))
        return
    loc = world.locations[player.location]
    sheltered = sheltered_at(loc)
    storm_exposed = is_storm(world.weather) and not sheltered
    rain_value = weather_rain_value(world.weather)
    if rain_value and not sheltered:
        wetness_gain = 3 if is_storm(world.weather) else max(1, rain_value // 2)
        player.conditions["wetness"] = clamp(player.conditions["wetness"] + wetness_gain)
    if world.minute % 60 == 0:
        dry = 10 if sheltered or active_fire(loc) else 4
        player.conditions["wetness"] = clamp(player.conditions["wetness"] - dry)
        player.conditions["filth"] = clamp(player.conditions.get("filth", 0) + (0 if sheltered else 1))
        if strong_sunlight(world, player.location, loc) and 10 <= world.minute // 60 < 17 and not sheltered:
            player.needs["thirst"] = clamp(player.needs["thirst"] + max(1, scale_wiki_delta(4, "hydration")))
            player.conditions["sunburn"] = clamp(player.conditions.get("sunburn", 0) + 2)
            player.conditions["hyperthermia"] = clamp(player.conditions.get("hyperthermia", 0) + 1)
            player.conditions["headache"] = clamp(player.conditions.get("headache", 0) + 1)
            player.stats["tanning"] = clamp(player.stats.get("tanning", 75) + 1)
            if player.conditions.get("hyperthermia", 0) >= 40:
                player.needs["fatigue"] = clamp(player.needs["fatigue"] + 1)
        else:
            player.conditions["sunburn"] = clamp(player.conditions.get("sunburn", 0) - 1)
            player.conditions["hyperthermia"] = clamp(player.conditions.get("hyperthermia", 0) - 2)
        if rain_value and player.conditions.get("wetness", 0) >= 60:
            cold_gain = 2 if storm_exposed else 1
            if active_fire(loc):
                cold_gain = max(1, cold_gain - 1)
            player.conditions["hypothermia"] = clamp(player.conditions.get("hypothermia", 0) + cold_gain)
        else:
            player.conditions["hypothermia"] = clamp(
                player.conditions.get("hypothermia", 0) - (2 if active_fire(loc) else 1)
            )
        if storm_exposed:
            player.needs["stress"] = clamp(player.needs["stress"] + scale_wiki_delta(5, "stress"))
            player.needs["fatigue"] = clamp(player.needs["fatigue"] + 1)
        if player.conditions.get("hyperthermia", 0) >= 70:
            player.needs["health"] = clamp(
                player.needs["health"] - (2 if player.conditions.get("hyperthermia", 0) >= 90 else 1)
            )
        if player.conditions.get("hypothermia", 0) >= 70:
            player.needs["health"] = clamp(
                player.needs["health"] - (2 if player.conditions.get("hypothermia", 0) >= 90 else 1)
            )
        if mosquito_pressure_at(world, player, loc):
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
        if player.conditions.get("headache", 0) and not strong_sunlight(world, player.location, loc):
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
        update_parasitic_disease(world, player, loc)
        update_bacterial_infection(player)
        if player.needs["health"] <= 0:
            finish_world(world, player, "loss", "dead", death_reason(player))
            return
    if world.minute == 6 * 60 and player.conditions.get("treated_wound", 0):
        player.conditions["wounds"] = clamp(player.conditions.get("wounds", 0) - 1)
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 10)
        player.conditions["blood_loss"] = clamp(player.conditions.get("blood_loss", 0) - 15)
        player.conditions["treated_wound"] = 0


def update_bacterial_infection(player: Player) -> None:
    infection = int(player.conditions.get("bacterial_infection", 0))
    wounds = int(player.conditions.get("wounds", 0))
    immunity = int(player.stats.get("immunity", 85))
    if wounds:
        if player.conditions.get("treated_wound", 0):
            infection = clamp(infection - 3)
        else:
            gain = wounds * 2
            if player.conditions.get("filth", 0) >= 50:
                gain += 2
            if player.conditions.get("wetness", 0) >= 60:
                gain += 1
            if immunity < 60:
                gain += 1
            infection = clamp(infection + gain)
    elif infection:
        infection = clamp(infection - max(2, immunity // 30))
    player.conditions["bacterial_infection"] = infection
    if infection >= 20:
        player.conditions["fever"] = clamp(player.conditions.get("fever", 0) + 1 + infection // 40)
    elif player.conditions.get("fever", 0):
        player.conditions["fever"] = clamp(player.conditions.get("fever", 0) - 1)
    if infection >= 70 and player.conditions.get("fever", 0) >= 50:
        player.needs["health"] = clamp(player.needs["health"] - (2 if infection >= 90 else 1))


def update_parasitic_disease(world: World, player: Player, loc: Location) -> None:
    parasites = int(player.conditions.get("parasites", 0))
    malaria = int(player.conditions.get("malaria", 0))
    quinine = int(player.conditions.get("quinine", 0))
    immunity = int(player.stats.get("immunity", 85))
    if parasites:
        pressure = 1 if parasites >= 20 else 0
        if parasites >= 50:
            pressure += 1
        if player.conditions.get("filth", 0) >= 60:
            pressure += 1
        if immunity < 60:
            pressure += 1
        treatment = (1 if immunity >= 80 else 0) + quinine // 16
        parasites = clamp(parasites + pressure - treatment)
        if parasites >= 35:
            player.needs["hunger"] = clamp(player.needs["hunger"] + 1)
            player.stats["healthy_weight"] = clamp(player.stats.get("healthy_weight", 75) - 1)
            player.stats["immunity"] = clamp(player.stats.get("immunity", 85) - 1)
        if parasites >= 70:
            player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 1)
    if mosquito_pressure_at(world, player, loc) and player.conditions.get("bug_repellent", 0) < 20:
        bites = int(player.conditions.get("bug_bites", 0))
        if bites >= 20:
            malaria = clamp(malaria + 1 + bites // 35)
    if malaria:
        treatment = quinine // 12
        recovery = 1 if not mosquito_pressure_at(world, player, loc) and immunity >= 80 else 0
        malaria = clamp(malaria - treatment - recovery)
        if malaria >= 20:
            player.conditions["fever"] = clamp(player.conditions.get("fever", 0) + 1 + malaria // 35)
            player.conditions["headache"] = clamp(player.conditions.get("headache", 0) + 1)
            player.needs["fatigue"] = clamp(player.needs["fatigue"] + 1)
        if malaria >= 70 and player.conditions.get("fever", 0) >= 50:
            player.needs["health"] = clamp(player.needs["health"] - 1)
    if quinine >= 16:
        side_effect = 1 + quinine // 34
        player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + side_effect)
        player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + side_effect)
        player.needs["stress"] = clamp(player.needs["stress"] + side_effect)
    player.conditions["parasites"] = parasites
    player.conditions["malaria"] = malaria


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
        elif name in {"drop", "take off backpack"}:
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
        container = indexed_carried_stack(player, action.args, storage=True) or carried_storage_with_item(player, str(action.args["item"]))
        if container:
            if "content_index" in action.args:
                removed = remove_indexed_storage_content(container.data, int(action.args["content_index"]), int(action.args.get("qty", 1)))
            else:
                removed = remove_stack_from_storage(container.data, str(action.args["item"]), int(action.args.get("qty", 1)))
            for stack in removed:
                add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
            mark_carried_recent(player, container)
    elif name == "retrieve":
        storage = indexed_placed_storage(loc, action.args) or placed_storage_with_item(loc, str(action.args["item"]))
        if storage:
            if "content_index" in action.args:
                removed = remove_indexed_storage_content(storage.data, int(action.args["content_index"]), int(action.args.get("qty", 1)))
            else:
                removed = remove_stack_from_storage(storage.data, str(action.args["item"]), int(action.args.get("qty", 1)))
            for stack in removed:
                add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed, data=stack.data)
    player.needs["fatigue"] = clamp(
        player.needs["fatigue"]
        + {
            "gather": 4,
            "go for a walk": WALK_FATIGUE_COST,
            "explore": 8,
            "move": 4,
            "dive": DIVE_FATIGUE_COST,
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
            "harvest cinchona bark": 4,
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
            "craft hand drill": 3,
            "craft bow drill": 5,
            "craft torch": 1,
            "make wood shavings": 2,
            "light tinder with hand drill": 4,
            "light tinder with bow drill": 2,
            "light tinder from fire": 1,
            "light tinder with mirror": 1,
            "light torch": 1,
            "extinguish torch": 1,
            "make aloe gel": 2,
            "brew ginger tea": 1,
            "brew spider lily tea": 1,
            "brew jasmine tea": 1,
            "make bug repellent": 2,
            "prepare yam": 3,
            "extract nipa seeds": 2,
            "extract coffee beans": 1,
            "roast coffee beans": 1,
            "dry cinchona bark": 1,
            "grind cinchona powder": 3,
            "brew coffee": 1,
            "split sago log": 25,
            "scrape sago pith": 9,
            "soak sago sawdust": 1,
            "grind soaked sago": 2,
            "dry sago pulp": 1,
            "cook sago flatbread": 1,
            "collect sand": 1,
            "dig up sand": 2,
            "build sand castle": 1,
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
            "build raft": 9,
            "break conch": 1,
            "cook conch meat": 1,
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
            "gather": 3,
            "go for a walk": 1,
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
            "dig up sand": 2,
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
            "harvest cinchona bark": 3,
            "flesh skin": 3,
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
            "build raft": 2,
            "break conch": 1,
        }.get(name, 0)
    )
    player.conditions["foot_damage"] = clamp(
        player.conditions.get("foot_damage", 0)
        + {
            "explore": 2,
            "go for a walk": WALK_FOOT_DAMAGE,
            "move": 1,
            "harvest coconuts": 3,
            "cut sago palm": 2,
            "dig wild yam": 2,
            "dig up mud": 1,
            "dig up dirt": 1,
            "dig up sand": 1,
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
            "harvest cinchona bark": 3,
            "dig wild yam": 25,
            "collect bananas": 1,
            "cut nipa fruit": 1,
            "cut sago palm": 8,
            "dig up mud": 2,
            "dig up dirt": 2,
            "build sand castle": 1,
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
            "flesh skin": 2,
            "weave cord": 1,
            "weave palm fronds": 1,
            "craft woven basket": 1,
            "craft woven backpack": 1,
            "add rope to basket": 1,
            "detach rope from woven backpack": 1,
            "craft stone axe": 2,
            "craft hand drill": 1,
            "craft bow drill": 1,
            "craft torch": 1,
            "break conch": 1,
            "make wood shavings": 1,
            "light tinder with hand drill": 1,
            "light tinder with bow drill": 1,
            "light torch": 1,
            "extinguish torch": 1,
            "split sago log": 8,
            "grind soaked sago": 1,
            "grind cinchona powder": 1,
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
            "build raft": 2,
        }.get(name, 0)
    )
    if name in {"dig up mud", "make mud"}:
        player.conditions["wetness"] = clamp(player.conditions.get("wetness", 0) + 20)
    if name in {"explore", "go for a walk", "move", "forage tide pool", "harvest coconuts"}:
        player.stats["foot_callouses"] = clamp(player.stats.get("foot_callouses", 70) + 1)
    if name in {
        "gather",
            "craft sharp stone",
            "flesh skin",
            "weave cord",
            "weave rope",
            "weave palm fronds",
            "craft woven basket",
            "craft woven backpack",
            "add rope to basket",
            "detach rope from woven backpack",
            "place basket",
            "craft digging stick",
            "craft hand drill",
            "craft bow drill",
            "craft torch",
            "make wood shavings",
            "light tinder with hand drill",
            "light tinder with bow drill",
            "light tinder from fire",
            "light tinder with mirror",
            "light torch",
            "extinguish torch",
            "collect sand",
            "dig up sand",
            "build sand castle",
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
    if name == "forage tide pool":
        item = TIDE_POOL_OUTPUTS[(world.tick + len(player.name)) % len(TIDE_POOL_OUTPUTS)]
        add_items_to_carried_or_ground(world, player, item, 1)
    elif name == "dive":
        player.conditions["wetness"] = clamp(player.conditions.get("wetness", 0) + DIVE_WETNESS)
        player.conditions["filth"] = clamp(player.conditions.get("filth", 0) - DIVE_FILTH_REMOVAL)
        player.needs["morale"] = clamp(player.needs["morale"] + DIVE_MORALE_GAIN)
        player.needs["stress"] = clamp(player.needs["stress"] - DIVE_STRESS_RELIEF)
        player.stats["entertainment"] = clamp(player.stats.get("entertainment", 50) + DIVE_ENTERTAINMENT_GAIN)
        item = dive_find(world, player)
        if item:
            add_items_to_carried_or_ground(world, player, item, 1)
        else:
            log_event(world, f"{player.name} found nothing while diving {player.location}.")
    elif name == "gather":
        item = action.args.get("item") or gather_items_for_location(loc)[0]
        add_items_to_carried_or_ground(world, player, item, 1)
    elif name == "go for a walk":
        player.needs["stress"] = clamp(player.needs["stress"] - WALK_STRESS_RELIEF)
        if not find_explore_item(world, player, "walking"):
            log_event(world, f"{player.name} found nothing while walking {player.location}.")
    elif name == "harvest coconuts":
        add_items_to_carried_or_ground(world, player, "coconut", 1)
    elif name in RESOURCE_HARVESTS:
        rng = random.Random(f"{world.seed}:{world.tick}:{world.day}:{player.name}:{name}")
        for item, min_qty, max_qty in RESOURCE_HARVESTS[name]["outputs"]:
            qty = min_qty if min_qty == max_qty else rng.randint(min_qty, max_qty)
            add_items_to_carried_or_ground(world, player, item, qty)
    elif name == "explore":
        discover_next(world, player)
    elif name == "move":
        player.location = str(action.args["location"])
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
                player.needs["thirst"] = clamp(
                    player.needs["thirst"] - max(1, DRINK_VALUES["clean water"] * amount // VESSEL_DRINK_AMOUNT)
                )
                player.conditions["headache"] = clamp(player.conditions.get("headache", 0) - 3)
            elif liquid_type == "unsafe water":
                player.needs["thirst"] = clamp(player.needs["thirst"] - max(1, 18 * amount // VESSEL_DRINK_AMOUNT))
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + 6)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 4)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) + 5)
                player.conditions["parasites"] = clamp(player.conditions.get("parasites", 0) + 6)
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
        add_items_to_carried_or_ground(world, player, "sharp stone", 1, data={"durability": durability, "max_durability": durability})
    elif name == "crack coconut":
        add_items_to_carried_or_ground(world, player, "coconut water", 1, exposed=False)
        add_items_to_carried_or_ground(world, player, "coconut meat", 1)
        add_items_to_carried_or_ground(world, player, "coconut shell", 1)
    elif name == "weave cord":
        add_items_to_carried_or_ground(world, player, "fiber cord", 1)
    elif name == "weave rope":
        add_items_to_carried_or_ground(world, player, "rope", 1)
    elif name == "weave palm fronds":
        add_items_to_carried_or_ground(world, player, "palm weave", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
    elif name == "craft woven basket":
        add_items_to_carried_or_ground(world, player, "basket", 1, data=STORAGE_DATA["basket"])
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "craft woven backpack":
        add_items_to_carried_or_ground(world, player, "woven backpack", 1, data=STORAGE_DATA["woven backpack"])
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "add rope to basket":
        data = {**STORAGE_DATA["woven backpack"], **deepcopy(action.args.get("basket_data", {}))}
        data["equipped_weight_reduction"] = STORAGE_DATA["woven backpack"]["equipped_weight_reduction"]
        data["equipped_slot"] = STORAGE_DATA["woven backpack"]["equipped_slot"]
        add_items_to_carried_or_ground(world, player, "woven backpack", 1, data=data)
    elif name == "detach rope from woven backpack":
        backpack = next((stack for stack in action.reserved if stack.item == "woven backpack"), None)
        data = {**STORAGE_DATA["basket"], **deepcopy(backpack.data if backpack else {})}
        data.pop("equipped_weight_reduction", None)
        data.pop("equipped_slot", None)
        add_items_to_carried_or_ground(world, player, "basket", 1, data=data)
        add_items_to_carried_or_ground(world, player, "rope", 1)
    elif name == "place basket":
        data = deepcopy(action.reserved[0].data) if action.reserved else dict(STORAGE_DATA["basket"])
        loc.placed.append(PlacedObject("basket", active=True, data=data))
    elif name == "craft stone axe":
        durability = TOOL_DURABILITY["stone axe"]
        add_items_to_carried_or_ground(world, player, "stone axe", 1, data={"durability": durability, "max_durability": durability})
    elif name == "craft digging stick":
        durability = TOOL_DURABILITY["digging stick"]
        add_items_to_carried_or_ground(world, player, "digging stick", 1, data={"durability": durability, "max_durability": durability})
    elif name == "craft hand drill":
        durability = TOOL_DURABILITY["hand drill"]
        add_items_to_carried_or_ground(world, player, "hand drill", 1, data={"durability": durability, "max_durability": durability})
    elif name == "craft bow drill":
        durability = TOOL_DURABILITY["bow drill"]
        add_items_to_carried_or_ground(world, player, "bow drill", 1, data={"durability": durability, "max_durability": durability})
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
    elif name == "make wood shavings":
        add_items_to_carried_or_ground(world, player, "wood shavings", 3)
    elif name in TINDER_LIGHTING_ACTIONS:
        add_items_to_carried_or_ground(world, player, "lit tinder", 1, data={"fuel": 6, "max_fuel": 6})
        player.needs["morale"] = clamp(player.needs["morale"] + 1)
        if name in {"light tinder with hand drill", "light tinder with bow drill"}:
            hand_damage = 10 if name == "light tinder with bow drill" else 40
            player.conditions["hand_damage"] = clamp(player.conditions.get("hand_damage", 0) + hand_damage)
    elif name == "craft torch":
        add_items_to_carried_or_ground(world, player, "torch", 1, data={"fuel": TORCH_MAX_FUEL, "max_fuel": TORCH_MAX_FUEL})
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "light torch":
        torch = next((stack for stack in action.reserved if stack.item == "torch"), None)
        age = min(int(torch.age_minutes if torch else 0), TORCH_MAX_FUEL * TORCH_FUEL_MINUTES)
        max_fuel = int((torch.data if torch else {}).get("max_fuel", TORCH_MAX_FUEL))
        add_items_to_carried_or_ground(world, player, "lit torch", 1, age_minutes=age, data={"max_fuel": max_fuel})
    elif name == "extinguish torch":
        torch = next((stack for stack in action.reserved if stack.item == "lit torch"), None)
        max_fuel = int((torch.data if torch else {}).get("max_fuel", TORCH_MAX_FUEL))
        max_minutes = max_fuel * TORCH_FUEL_MINUTES
        age = min(int(torch.age_minutes if torch else 0) + TORCH_FUEL_MINUTES, max_minutes)
        remaining_fuel = max(0, (max_minutes - age + TORCH_FUEL_MINUTES - 1) // TORCH_FUEL_MINUTES)
        if remaining_fuel:
            add_items(
                player.carried,
                "torch",
                1,
                age_minutes=age,
                data={"fuel": remaining_fuel, "max_fuel": max_fuel},
            )
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
    elif name == "craft bone hook":
        add_items_to_carried_or_ground(world, player, "bone hook", 1)
    elif name == "craft fishing line":
        add_items_to_carried_or_ground(world, player, "fishing line", 1, data=tool_durability_data("fishing line"))
        player.needs["stress"] = clamp(player.needs["stress"] - 4)
    elif name == "craft fishing rod":
        add_items_to_carried_or_ground(world, player, "fishing rod", 1, data=tool_durability_data("fishing rod"))
        player.needs["stress"] = clamp(player.needs["stress"] - 4)
    elif name == "craft fish bait":
        add_items_to_carried_or_ground(world, player, "fish bait", 8)
        player.needs["stress"] = clamp(player.needs["stress"] - 4)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
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
            add_items_to_carried_or_ground(world, player, item, 1)
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
            add_items_to_carried_or_ground(world, player, item, 1)
            add_items_to_carried_or_ground(world, player, "fresh skin", 1)
            trap.data = {"baited": 0, "soak_minutes": 0}
    elif name == "build water filter":
        loc.placed.append(PlacedObject("water filter", active=True))
    elif name == "build solar still":
        loc.placed.append(PlacedObject("solar still", active=True, data={"sun_minutes": 0}))
    elif name in {"fish", "fish with bait"}:
        player.needs["morale"] = clamp(player.needs["morale"] + 1)
        player.needs["stress"] = clamp(player.needs["stress"] - LINE_FISH_STRESS_RELIEF)
        if line_fish_catch(world, player, name):
            add_items_to_carried_or_ground(world, player, "raw fish", 1)
        else:
            log_event(world, f"{player.name} caught nothing while fishing {player.location}.")
    elif name == "spear fish":
        player.conditions["wetness"] = clamp(player.conditions.get("wetness", 0) + SPEAR_FISH_WETNESS)
        player.needs["morale"] = clamp(player.needs["morale"] + 1)
        if spear_fish_catch(world, player):
            add_items_to_carried_or_ground(world, player, "raw fish", 1)
        else:
            log_event(world, f"{player.name} caught nothing while spear fishing {player.location}.")
    elif name == "break conch":
        add_items_to_carried_or_ground(world, player, "conch meat", 1)
        add_items_to_carried_or_ground(world, player, "crushed conch", 1)
    elif name == "cook fish":
        require_fire(loc)
        world.processes.append(WorldProcess("cooking", player.location, 45, item="raw fish", output="cooked fish"))
    elif name == "cook conch meat":
        require_fire(loc)
        world.processes.append(WorldProcess("cooking", player.location, 45, item="conch meat", output="cooked conch meat"))
    elif name == "cook meat":
        require_fire(loc)
        world.processes.append(WorldProcess("cooking", player.location, 60, item="raw meat", output="cooked meat"))
    elif name == "boil water":
        require_fire(loc)
        world.processes.append(WorldProcess("boiling", player.location, 45, item="unsafe water", output="clean water"))
    elif name == "dry fish":
        world.processes.append(WorldProcess("drying", player.location, 12 * 60, item="raw fish", output="dried fish"))
    elif name == "dry cinchona bark":
        world.processes.append(WorldProcess("drying", player.location, 2 * 1440, item="cinchona bark", output="dried cinchona bark"))
    elif name == "filter water":
        world.processes.append(WorldProcess("filtering", player.location, 30, item="unsafe water", output="clean water"))
    elif name == "flesh skin":
        add_items_to_carried_or_ground(world, player, "fleshed skin", 1)
    elif name == "make aloe gel":
        add_items_to_carried_or_ground(world, player, "aloe gel", 3)
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
        add_items_to_carried_or_ground(world, player, "ginger tea", 1)
    elif name == "brew spider lily tea":
        add_items_to_carried_or_ground(world, player, "spider lily tea", 1)
    elif name == "brew jasmine tea":
        add_items_to_carried_or_ground(world, player, "jasmine tea", 1)
    elif name == "make bug repellent":
        add_items_to_carried_or_ground(world, player, "bug repellent", 2)
    elif name == "apply bug repellent":
        player.conditions["bug_repellent"] = clamp(player.conditions.get("bug_repellent", 0) + 96)
        player.conditions["bug_bites"] = clamp(player.conditions.get("bug_bites", 0) - 8)
    elif name == "prepare yam":
        add_items_to_carried_or_ground(world, player, "cooked yam", 1)
    elif name == "extract nipa seeds":
        add_items_to_carried_or_ground(world, player, "nipa seeds", 4)
    elif name == "extract coffee beans":
        add_items_to_carried_or_ground(world, player, "coffee beans", 2)
    elif name == "roast coffee beans":
        require_fire(loc)
        add_items_to_carried_or_ground(world, player, "roasted coffee beans", 1)
    elif name == "grind cinchona powder":
        add_items_to_carried_or_ground(world, player, "quinine powder", 3)
    elif name == "brew coffee":
        require_fire(loc)
        add_items_to_carried_or_ground(world, player, "coffee", 1)
    elif name == "split sago log":
        add_items_to_carried_or_ground(world, player, "sago pith section", 16)
    elif name == "scrape sago pith":
        add_items_to_carried_or_ground(world, player, "sago sawdust", 1)
    elif name == "soak sago sawdust":
        add_items_to_carried_or_ground(world, player, "soaked sago", 1)
    elif name == "grind soaked sago":
        add_items_to_carried_or_ground(world, player, "sago pulp", 1)
    elif name == "dry sago pulp":
        world.processes.append(WorldProcess("drying", player.location, 24 * 60, item="sago pulp", output="sago flour", data={"qty": 2}))
    elif name == "cook sago flatbread":
        require_fire(loc)
        add_items_to_carried_or_ground(world, player, "sago flatbread", 1)
    elif name in COOKING_POT_MEALS:
        require_fire(loc)
        meal = COOKING_POT_MEALS[name]
        world.processes.append(
            WorldProcess("cooking", player.location, int(meal["minutes"]), output=str(meal["output"]))
        )
    elif name == "collect sand":
        add_items_to_carried_or_ground(world, player, "sand", 4)
    elif name == "dig up sand":
        add_items_to_carried_or_ground(world, player, "sand", 8)
    elif name == "build sand castle":
        loc.placed.append(PlacedObject("sand castle", active=True))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
        player.stats["entertainment"] = clamp(player.stats.get("entertainment", 50) + 15)
    elif name == "make quicklime":
        world.processes.append(
            WorldProcess("calcining", player.location, 4 * 60, item="pretty seashells", output="quicklime", data={"qty": 2, "temperature": 600})
        )
    elif name == "mix mortar":
        add_items_to_carried_or_ground(world, player, "mortar", 4)
    elif name == "make clay":
        add_items_to_carried_or_ground(world, player, "clay", 1)
    elif name == "make mud brick":
        add_items_to_carried_or_ground(world, player, "mud brick", 1)
    elif name == "make mud":
        add_items_to_carried_or_ground(world, player, "mud pile", 1)
    elif name == "crush dirt":
        add_items_to_carried_or_ground(world, player, "fine dirt", 1)
    elif name == "mix clay":
        add_items_to_carried_or_ground(world, player, "clay", 1)
    elif name == "shape clay bowl":
        add_items_to_carried_or_ground(world, player, "unfired clay bowl", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "shape clay jar":
        add_items_to_carried_or_ground(world, player, "unfired clay jar", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "shape cooking pot":
        add_items_to_carried_or_ground(world, player, "unfired cooking pot", 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name == "shape clay vase":
        add_items_to_carried_or_ground(world, player, "unfired clay vase", 1)
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
        add_items_to_carried_or_ground(world, player, "copper ore", 1)
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
        add_items_to_carried_or_ground(world, player, COPPER_MOLD_OUTPUTS[name], 1)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 2)
    elif name in COPPER_CASTING_OUTPUTS:
        output = COPPER_CASTING_OUTPUTS[name]
        add_items_to_carried_or_ground(world, player, output, 1, data=tool_durability_data(output))
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name in COPPER_CRAFT_OUTPUTS:
        output = COPPER_CRAFT_OUTPUTS[name]
        data = dict(COPPER_VESSEL_DATA.get(output, tool_durability_data(output)))
        add_items_to_carried_or_ground(world, player, output, COPPER_CRAFT_QUANTITIES.get(name, 1), data=data)
        player.needs["stress"] = clamp(player.needs["stress"] - 10)
        if name in {"make copper needles", "craft copper bottle", "craft copper jar"}:
            player.needs["morale"] = clamp(player.needs["morale"] + 10)
        elif name in {"craft copper axe", "craft copper shovel", "craft copper spear"}:
            player.needs["morale"] = clamp(player.needs["morale"] + 5)
    elif name == "collect salt water":
        add_items_to_carried_or_ground(world, player, "salt water", 1)
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
            add_items_to_carried_or_ground(world, player, "salt", qty)
    elif name == "salt fish":
        world.processes.append(WorldProcess("curing", player.location, 3 * 1440, item="raw fish", output="salted fish"))
    elif name == "salt meat":
        world.processes.append(WorldProcess("curing", player.location, 3 * 1440, item="raw meat", output="salted meat"))
    elif name == "treat wound":
        player.conditions["treated_wound"] = 1
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 15)
        player.conditions["blood_loss"] = clamp(player.conditions.get("blood_loss", 0) - 8)
        player.conditions["bacterial_infection"] = clamp(player.conditions.get("bacterial_infection", 0) - 8)
        player.stats["immunity"] = clamp(player.stats.get("immunity", 85) + 2)
    elif name == "build raft":
        stage_index = int(action.args.get("raft_stage", raft_build_stage_index(loc)))
        stage_count = len(RAFT_BUILD_STAGES)
        apply_tool_wear_values(world, player, RAFT_BUILD_STAGES[stage_index]["tool_wear"])
        completed_stage = stage_index + 1
        if completed_stage >= stage_count:
            frame = raft_frame_at(loc)
            if frame:
                loc.placed.remove(frame)
            world.locations["raft"].discovered = True
            player.needs["morale"] = clamp(player.needs.get("morale", 50) + scale_wiki_delta(100, "morale"))
            player.needs["stress"] = clamp(player.needs.get("stress", 0) - scale_wiki_delta(10, "stress"))
            log_event(world, f"{player.name} launched a raft at the beach.")
        else:
            frame = raft_frame_at(loc)
            if frame is None:
                frame = PlacedObject("raft frame", active=True)
                loc.placed.append(frame)
            frame.data = {"stage": completed_stage, "stages": stage_count}
            log_event(world, f"{player.name} advanced the raft frame to stage {completed_stage}/{stage_count}.")
        player.skills["crafting"] = player.skills.get("crafting", 0) + 1
    apply_tool_wear(world, player, name)
    log_event(world, f"{player.name} completed {name}.")


def gather_items_for_location(location: Location) -> list[str]:
    outputs = [
        item
        for item, resource in location.resources.items()
        if resource.get("action") == "gather"
    ]
    return outputs


def dive_here(location: Location, location_name: str) -> bool:
    return (
        location_name in DIVE_LOCATIONS
        or "sea" in location.features
        or has_location_card(location, "sea", "seawater")
    )


def dive_find(world: World, player: Player) -> str | None:
    weights = dict(DIVE_OUTPUT_WEIGHTS.get(player.location, DIVE_OUTPUT_WEIGHTS["default"]))
    skill = max(0, min(150, player.skills.get("swimming", 0)))
    nothing_weight = max(0, DIVE_NOTHING_WEIGHT - DIVE_SWIMMING_NOTHING_REDUCTION * skill // 150)
    total = nothing_weight + sum(weights.values())
    rng = random.Random(f"{world.seed}:dive:{player.location}:{world.tick}:{player.name}")
    roll = rng.randrange(total)
    if roll < nothing_weight:
        return None
    roll -= nothing_weight
    for item, weight in weights.items():
        if roll < weight:
            return item
        roll -= weight
    return None


def line_fish_here(location: Location, location_name: str) -> bool:
    return (
        location_name in LINE_FISH_LOCATIONS
        or "sea" in location.features
        or has_location_card(location, "sea", "seawater")
    )


def line_fish_catch(world: World, player: Player, action_name: str) -> bool:
    weights = LINE_FISH_WEIGHTS[action_name]
    skill = max(0, min(150, player.skills.get("fishing", 0)))
    nothing_weight = int(weights["nothing"]) - int(weights["skill_reduction"]) * skill // 150
    tool_used = next((stack.item for stack in carried_tool_stacks(player, "fishing line")), "")
    if tool_used == "fishing rod":
        nothing_weight -= int(weights["rod_reduction"])
    nothing_weight = max(0, nothing_weight)
    fish_weight = int(weights["fish"])
    rng = random.Random(f"{world.seed}:{action_name}:{player.location}:{world.tick}:{player.name}")
    return rng.randrange(nothing_weight + fish_weight) >= nothing_weight


def spear_fish_here(location: Location, location_name: str) -> bool:
    return (
        location_name in SPEAR_FISH_LOCATIONS
        or "sea" in location.features
        or has_location_card(location, "sea", "seawater", "flooded tide pool")
    )


def spear_fish_catch(world: World, player: Player) -> bool:
    base_nothing, base_fish = SPEAR_FISH_BASE_WEIGHTS.get(
        player.location,
        SPEAR_FISH_BASE_WEIGHTS["default"],
    )
    skill_bonus = max(0, player.skills.get("spear_fishing", 0)) // 5
    nothing_weight = max(0, base_nothing - skill_bonus)
    fish_weight = base_fish + skill_bonus
    rng = random.Random(f"{world.seed}:spear fish:{player.location}:{world.tick}:{player.name}")
    return rng.randrange(nothing_weight + fish_weight) >= nothing_weight


def apply_tool_wear(world: World, player: Player, action_name: str) -> None:
    apply_tool_wear_values(world, player, TOOL_WEAR.get(action_name, {}))


def apply_tool_wear_values(world: World, player: Player, wear_by_tool: dict[str, int]) -> None:
    for item, wear in wear_by_tool.items():
        stacks = carried_tool_stacks(player, item)
        stacks.sort(
            key=lambda stack: (
                stack.item in TOOL_DURABILITY,
                int(stack.data.get("durability", TOOL_DURABILITY.get(stack.item, 9999))),
            )
        )
        for stack in stacks:
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
                if stack.item in {"fishing line", "fishing rod"}:
                    add_items_to_carried_or_ground(world, player, "fiber cord", 2)
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


def discovered_neighbor_names(world: World, location_name: str) -> list[str]:
    candidates = list(AREA_NEIGHBORS.get(location_name, []))
    candidates.extend(name for name, neighbors in AREA_NEIGHBORS.items() if location_name in neighbors)
    return [
        name
        for name in dict.fromkeys(candidates)
        if name in world.locations and world.locations[name].discovered
    ]


def discover_next(world: World, player: Player) -> None:
    discovered = discover_area_or_card(world, player)
    found_item = find_explore_item(world, player)
    if discovered or found_item:
        return
    add_items_to_carried_or_ground(world, player, "stones", 1)
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
            if card in {"tide pool", "flooded tide pool"}:
                normalize_tide_pool_card(current_location, tide_is_high(world))
            log_event(world, f"{player.name} found {card} at {player.location}.")
            return True
    for name in DISCOVERY_ORDER:
        loc = world.locations[name]
        if not loc.discovered:
            loc.discovered = True
            log_event(world, f"{player.name} discovered {name}.")
            return True
    return False


def find_explore_item(world: World, player: Player, activity: str = "exploring") -> bool:
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
            add_items_to_carried_or_ground(world, player, item, qty)
            log_event(world, f"{player.name} found {qty} {item} while {activity} {player.location}.")
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
                player.conditions["bacterial_infection"] = clamp(player.conditions.get("bacterial_infection", 0) - 25)
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
        "quinine powder",
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
            if item == "quinine powder":
                player.conditions["quinine"] = clamp(player.conditions.get("quinine", 0) + 17)
                player.conditions["parasites"] = clamp(player.conditions.get("parasites", 0) - 15)
                player.conditions["malaria"] = clamp(player.conditions.get("malaria", 0) - 25)
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + 4)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 4)
                player.needs["stress"] = clamp(player.needs["stress"] + 2)
                player.needs["morale"] = clamp(player.needs["morale"] - 3)
            if item == "magic mushrooms":
                player.conditions["psilocybin"] = clamp(player.conditions.get("psilocybin", 0) + 35)
                player.conditions["altered_mind_state"] = clamp(player.conditions.get("altered_mind_state", 0) + 20)
                player.conditions["derealization"] = clamp(player.conditions.get("derealization", 0) + 10)
                player.needs["morale"] = clamp(player.needs["morale"] + 4)
            if item in {"raw meat", "raw fish", "conch meat", "assorted mushrooms", "bugs", "yam"}:
                player.conditions["nausea"] = clamp(player.conditions.get("nausea", 0) + 8)
                player.conditions["diarrhea"] = clamp(player.conditions.get("diarrhea", 0) + 5)
                player.conditions["food_poisoning"] = clamp(player.conditions.get("food_poisoning", 0) + 10)
                player.conditions["parasites"] = clamp(player.conditions.get("parasites", 0) + (10 if item in {"raw meat", "raw fish"} else 5))
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
                if is_raining(world.weather):
                    obj.data["rain_minutes"] = obj.data.get("rain_minutes", 0) + dt
                    while obj.data["rain_minutes"] >= 60:
                        obj.data["rain_minutes"] -= 60
                        add_items(loc.ground, "clean water", 1)
                elif weather_is_dry(world.weather):
                    obj.data["rain_minutes"] = max(0, obj.data.get("rain_minutes", 0) - dt)
            if obj.kind == "water reservoir" and obj.active:
                obj.data.setdefault("capacity", WATER_RESERVOIR_CAPACITY)
                obj.data.setdefault("liquid", 0)
                obj.data.setdefault("rain_minutes", 0)
                obj.data.setdefault("mosquito_protection", 0)
                if is_raining(world.weather):
                    obj.data["rain_minutes"] = int(obj.data.get("rain_minutes", 0)) + dt
                    while obj.data["rain_minutes"] >= WATER_RESERVOIR_TP_MINUTES:
                        obj.data["rain_minutes"] -= WATER_RESERVOIR_TP_MINUTES
                        obj.data["liquid"] = min(
                            int(obj.data.get("capacity", WATER_RESERVOIR_CAPACITY)),
                            int(obj.data.get("liquid", 0)) + WATER_RESERVOIR_RAIN_FILL,
                        )
                        obj.data["mosquito_protection"] = max(0, int(obj.data.get("mosquito_protection", 0)) - 4)
                elif weather_is_dry(world.weather):
                    obj.data["rain_minutes"] = max(0, int(obj.data.get("rain_minutes", 0)) - dt)
            if obj.kind == "well" and obj.active:
                obj.data.setdefault("capacity", WELL_CAPACITY)
                obj.data.setdefault("liquid", 0)
                obj.data.setdefault("fill_minutes", 0)
                obj.data["fill_minutes"] = int(obj.data.get("fill_minutes", 0)) + dt
                while obj.data["fill_minutes"] >= WELL_TP_MINUTES:
                    obj.data["fill_minutes"] -= WELL_TP_MINUTES
                    fill = WELL_BASE_FILL + (WELL_RAIN_FILL if is_raining(world.weather) else 0)
                    obj.data["liquid"] = min(
                        int(obj.data.get("capacity", WELL_CAPACITY)),
                        int(obj.data.get("liquid", 0)) + fill,
                    )
            if obj.kind == "cistern" and obj.active:
                obj.data.setdefault("capacity", CISTERN_CAPACITY)
                obj.data.setdefault("liquid", 0)
                obj.data.setdefault("rain_minutes", 0)
                if is_raining(world.weather):
                    obj.data["rain_minutes"] = int(obj.data.get("rain_minutes", 0)) + dt
                    while obj.data["rain_minutes"] >= CISTERN_TP_MINUTES:
                        obj.data["rain_minutes"] -= CISTERN_TP_MINUTES
                        obj.data["liquid"] = min(
                            int(obj.data.get("capacity", CISTERN_CAPACITY)),
                            int(obj.data.get("liquid", 0)) + CISTERN_RAIN_FILL,
                        )
                elif weather_is_dry(world.weather):
                    obj.data["rain_minutes"] = max(0, int(obj.data.get("rain_minutes", 0)) - dt)
            if obj.kind == "solar still" and obj.active:
                hour = world.minute // 60
                if weather_sun_strength(world.weather) >= 4 and 7 <= hour < 17:
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
        dry = weather_is_dry(world.weather)
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
                message = f"{stack.item.capitalize()} spoiled at {place}."
            elif stack.item == "leaves":
                add_items(stacks, "dry leaves", stack.qty)
                message = f"Leaves dried at {place}."
            elif stack.item == "fleshed skin":
                add_items(stacks, "leather", stack.qty)
                message = f"Fleshed skin cured at {place}."
            elif stack.item == "lit tinder":
                message = f"{stack.item.capitalize()} burned out at {place}."
            elif stack.item == "lit torch":
                message = f"{stack.item.capitalize()} burned out at {place}."
            else:
                message = f"{stack.item.capitalize()} spoiled at {place}."
            log_event(world, message)
        elif stack.item in {"clean water", "unsafe water", "salt water"} and stack.exposed and dry and stack.age_minutes >= 360:
            stacks.remove(stack)
            log_event(world, f"Exposed {stack.item} evaporated at {place}.")
