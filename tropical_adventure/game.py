from __future__ import annotations

import random
from typing import Any

from .content import (
    ACTION_BLUEPRINTS,
    ACTION_DURATIONS,
    AREA_DEFS,
    AREA_EXPLORE_AREAS,
    AREA_EXPLORE_CARDS,
    AREA_EXPLORE_ITEMS,
    AREA_NEIGHBORS,
    DEFAULT_FORAGE_OUTPUTS,
    DISCOVERY_ORDER,
    FISH_LOCATIONS,
    RECIPES,
    SKILL_BY_ACTION,
    WATER_LOCATIONS,
    build_locations,
)
from .models import (
    Action,
    BLUEPRINTS,
    Location,
    MAX_EVENT_LOG,
    PlacedObject,
    Player,
    STARTING_BLUEPRINTS,
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
        "needs": dict(player.needs),
        "carried": [item.to_dict() for item in player.carried],
        "current_action": player.current_action.to_dict() if player.current_action else None,
    }
    actions = available_actions(world, player_name)
    player_data["available_actions"] = actions
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
        "players": {player_name: player_data},
        "event_log": world.event_log[-MAX_EVENT_LOG:],
        "light": "daylight" if daylight else "firelit" if active_fire(current_location) else "dark",
        "paused": world.paused,
        "available_actions": actions,
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
    player.known_blueprints = set(STARTING_BLUEPRINTS)
    world.players[name] = player
    log_event(world, f"{name} joined the island.")
    return player


def disconnect_player(world: World, name: str) -> None:
    if name in world.players:
        world.players[name].connected = False
        log_event(world, f"{name} disconnected; their personal state is frozen.")


def active_fire(location: Location) -> PlacedObject | None:
    return next((p for p in location.placed if p.kind == "fire" and p.active and p.fuel > 0), None)


def has_object(location: Location, kind: str) -> bool:
    return any(p.kind == kind and p.active for p in location.placed)


def has_location_card(location: Location, *cards: str) -> bool:
    return any(card in location.location_cards for card in cards)


def available_actions(world: World, player_name: str) -> list[str]:
    player = world.players[player_name]
    loc = world.locations[player.location]
    actions = ["explore", "forage", "gather", "rest", "leisure"]
    actions.extend(["drop"] if player.carried else [])
    actions.extend(["pick up"] if loc.ground else [])
    water_here = player.location in WATER_LOCATIONS or has_location_card(
        loc, "sea", "seawater", "tide pool", "flooded tide pool"
    )
    actions.extend(["wash", "swim"] if water_here else [])
    actions.extend(
        ["move"] if discovered_neighbor_names(world, player.location) else []
    )
    if count_item(player.carried, "clean water") or count_item(player.carried, "coconut"):
        actions.append("drink")
    if count_item(player.carried, "coconut") or count_item(player.carried, "cooked fish"):
        actions.append("eat")
    if player.conditions.get("wounds", 0) and count_item(player.carried, "bandage leaves"):
        actions.append("treat wound")
    for action, blueprint in ACTION_BLUEPRINTS.items():
        if blueprint in player.known_blueprints:
            actions.append(action)
    fish_here = player.location in FISH_LOCATIONS or has_location_card(loc, "tide pool", "flooded tide pool")
    if fish_here and count_item(player.carried, "sharp stone"):
        actions.append("fish")
    if active_fire(loc):
        if count_item(player.carried, "sticks"):
            actions.append("tend fire")
    else:
        actions = [action for action in actions if action not in {"cook fish", "boil water"}]
    return order_actions_by_recent(actions, player.action_history)


def order_actions_by_recent(actions: list[str], action_history: list[str]) -> list[str]:
    available = list(dict.fromkeys(actions))
    available_set = set(available)
    recent = [action for action in dict.fromkeys(action_history) if action in available_set]
    return recent + [action for action in available if action not in recent]


def start_action(world: World, player_name: str, action_name: str, args: dict[str, Any] | None = None) -> None:
    args = args or {}
    if world.paused:
        raise ValueError("world is paused")
    player = world.players[player_name]
    if not player.connected:
        raise ValueError("player is disconnected")
    if player.current_action:
        raise ValueError("player already has an action")
    if action_name not in ACTION_DURATIONS:
        raise ValueError(f"unknown action: {action_name}")
    if action_name not in available_actions(world, player_name):
        raise ValueError(f"action unavailable: {action_name}")
    loc = world.locations[player.location]
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
    if action_name == "move" and "location" in args:
        destination = str(args["location"])
        if destination not in discovered_neighbor_names(world, player.location):
            raise ValueError("destination is not a discovered neighbor")
    reserved = []
    if action_name in RECIPES:
        for item, qty in RECIPES[action_name].items():
            if action_name == "fish":
                if count_item(player.carried, item) < qty:
                    raise ValueError(f"missing {item}")
                continue
            reserved.extend(remove_items(player.carried, item, qty))
    if action_name == "pick up":
        item = args.get("item") or (loc.ground[0].item if loc.ground else None)
        reserved.extend(remove_items(loc.ground, item, int(args.get("qty", 1))))
    if action_name == "drop":
        item = args.get("item") or (player.carried[0].item if player.carried else None)
        reserved.extend(remove_items(player.carried, item, int(args.get("qty", 1))))
    total = ACTION_DURATIONS[action_name]
    player.current_action = Action(action_name, total, total, args, reserved)
    player.action_history = [action_name, *[action for action in player.action_history if action != action_name]]
    log_event(world, f"{player.name} started {action_name}.")


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
        add_items(target, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed)
    player.current_action = None
    log_event(world, f"{player.name} cancelled {action.name}.")


def tick_world(world: World) -> bool:
    if world.paused or not any(player.connected for player in world.players.values()):
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
    for player in list(world.players.values()):
        if player.connected:
            update_player_needs(world, player, dt)
            advance_action(world, player, dt)
    update_world_processes(world, dt)
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
    player.needs["thirst"] = clamp(player.needs["thirst"] + dt // 3, 0, 100)
    player.needs["hunger"] = clamp(player.needs["hunger"] + dt // 6, 0, 100)
    player.needs["fatigue"] = clamp(player.needs["fatigue"] + dt // 12, 0, 100)
    if player.needs["thirst"] >= 90 or player.needs["hunger"] >= 95:
        player.needs["health"] = clamp(player.needs["health"] - 1)
    loc = world.locations[player.location]
    if world.weather in {"rain", "storm"} and not has_object(loc, "shelter"):
        player.conditions["wetness"] = clamp(player.conditions["wetness"] + 2)
    if world.minute % 60 == 0:
        dry = 10 if has_object(loc, "shelter") or active_fire(loc) else 4
        player.conditions["wetness"] = clamp(player.conditions["wetness"] - dry)
        if player.conditions.get("wounds", 0) and not player.conditions.get("treated_wound", 0):
            player.conditions["pain"] = clamp(player.conditions.get("pain", 0) + 3)
    if world.minute == 6 * 60 and player.conditions.get("treated_wound", 0):
        player.conditions["wounds"] = clamp(player.conditions.get("wounds", 0) - 1)
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 10)
        player.conditions["treated_wound"] = 0


def advance_action(world: World, player: Player, dt: int) -> None:
    action = player.current_action
    if not action:
        return
    action.remaining_minutes -= dt
    if action.remaining_minutes <= 0:
        complete_action(world, player, action)
        player.current_action = None


def complete_action(world: World, player: Player, action: Action) -> None:
    loc = world.locations[player.location]
    name = action.name
    for stack in action.reserved:
        if name == "pick up":
            add_items(player.carried, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed)
        elif name == "drop":
            add_items(loc.ground, stack.item, stack.qty, age_minutes=stack.age_minutes, exposed=stack.exposed)
    player.needs["fatigue"] = clamp(
        player.needs["fatigue"]
        + {
            "forage": 5,
            "gather": 4,
            "explore": 8,
            "move": 4,
            "wash": 2,
            "swim": 8,
            "rest": 0,
            "leisure": 1,
            "craft sharp stone": 3,
            "start fire": 6,
            "fish": 8,
            "build raincatcher": 10,
            "build shelter": 14,
        }.get(name, 0)
    )
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
        unlock_from_item(player, item)
        if world.weather == "storm":
            player.conditions["wounds"] = clamp(player.conditions.get("wounds", 0) + 1)
            player.conditions["pain"] = clamp(player.conditions.get("pain", 0) + 5)
    elif name == "gather":
        item = action.args.get("item") or gather_items_for_location(loc)[0]
        add_items(player.carried, item, 1)
        unlock_from_item(player, item)
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
    elif name == "drink":
        consume_drink(player)
    elif name == "eat":
        consume_food(player)
    elif name == "rest":
        shelter_bonus = 12 if has_object(loc, "shelter") else 0
        player.needs["fatigue"] = clamp(player.needs["fatigue"] - 35 - shelter_bonus)
        player.needs["health"] = clamp(player.needs["health"] + 2 + shelter_bonus // 6)
        player.needs["morale"] = clamp(player.needs["morale"] + shelter_bonus // 3)
    elif name == "leisure":
        player.needs["morale"] = clamp(player.needs["morale"] + 10)
        player.needs["stress"] = clamp(player.needs["stress"] - 6)
    elif name == "craft sharp stone":
        add_items(player.carried, "sharp stone", 1)
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
    elif name == "build raincatcher":
        loc.placed.append(PlacedObject("raincatcher", active=True, data={"rain_minutes": 0}))
    elif name == "fish":
        add_items(player.carried, "raw fish", 1)
        unlock_from_item(player, "raw fish")
    elif name == "cook fish":
        require_fire(loc)
        world.processes.append(WorldProcess("cooking", player.location, 45, item="raw fish", output="cooked fish"))
    elif name == "boil water":
        require_fire(loc)
        world.processes.append(WorldProcess("boiling", player.location, 45, item="unsafe water", output="clean water"))
    elif name == "treat wound":
        player.conditions["treated_wound"] = 1
        player.conditions["pain"] = clamp(player.conditions.get("pain", 0) - 15)
    unlock_from_skill(player)
    log_event(world, f"{player.name} completed {name}.")


def gather_items_for_location(location: Location) -> list[str]:
    outputs = [
        item
        for item, resource in location.resources.items()
        if resource.get("action") == "gather"
    ]
    return outputs or ["sticks"]


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
            player.known_blueprints.update(blueprints_for_area(name))
            log_event(world, f"{player.name} discovered {name}.")
            return True
    for card in AREA_EXPLORE_CARDS.get(player.location, []):
        if card not in current_location.location_cards:
            current_location.location_cards.append(card)
            log_event(world, f"{player.name} found {card} at {player.location}.")
            return True
    for name, blueprints in DISCOVERY_ORDER:
        loc = world.locations[name]
        if not loc.discovered:
            loc.discovered = True
            player.known_blueprints.update(blueprints)
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
            unlock_from_item(player, item)
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


def blueprints_for_area(name: str) -> set[str]:
    return next((blueprints for area, blueprints in DISCOVERY_ORDER if area == name), set())


def unlock_from_item(player: Player, item: str) -> None:
    if item in {"sticks", "leaves"}:
        player.known_blueprints.add("fire")
    if item in {"vine", "leaves"} and player.skills.get("woodworking", 0) >= 1:
        player.known_blueprints.update({"shelter", "raincatcher"})
    if item == "raw fish":
        player.known_blueprints.add("cook fish")
    if item == "unsafe water":
        player.known_blueprints.add("boil water")


def unlock_from_skill(player: Player) -> None:
    if player.skills.get("woodworking", 0) >= 1:
        player.known_blueprints.update({"shelter", "raincatcher"})
    if player.skills.get("cooking", 0) >= 1:
        player.known_blueprints.update({"cook fish", "boil water"})
    player.known_blueprints &= BLUEPRINTS


def consume_drink(player: Player) -> None:
    if count_item(player.carried, "clean water"):
        remove_items(player.carried, "clean water", 1)
        player.needs["thirst"] = clamp(player.needs["thirst"] - 35)
    else:
        remove_items(player.carried, "coconut", 1)
        player.needs["thirst"] = clamp(player.needs["thirst"] - 20)
        player.needs["hunger"] = clamp(player.needs["hunger"] - 8)


def consume_food(player: Player) -> None:
    if count_item(player.carried, "cooked fish"):
        remove_items(player.carried, "cooked fish", 1)
        player.needs["hunger"] = clamp(player.needs["hunger"] - 35)
    else:
        remove_items(player.carried, "coconut", 1)
        player.needs["hunger"] = clamp(player.needs["hunger"] - 15)
        player.needs["thirst"] = clamp(player.needs["thirst"] - 10)


def require_fire(loc: Location) -> None:
    if not active_fire(loc):
        raise ValueError("active fire required")


def update_world_processes(world: World, dt: int) -> None:
    for loc in world.locations.values():
        for obj in loc.placed:
            if obj.kind == "fire" and obj.active and obj.fuel > 0:
                obj.data["burn_minutes"] = obj.data.get("burn_minutes", 0) + dt
                while obj.data["burn_minutes"] >= 180 and obj.fuel > 0:
                    obj.data["burn_minutes"] -= 180
                    obj.fuel -= 1
                    add_items(loc.ground, "ash", 1)
                    add_items(loc.ground, "charcoal", 1)
                if obj.fuel <= 0:
                    obj.active = False
                    obj.kind = "fire remnants"
                    log_event(world, f"A fire at {loc.name} burned out.")
            if obj.kind == "raincatcher" and obj.active:
                if world.weather in {"rain", "storm"}:
                    obj.data["rain_minutes"] = obj.data.get("rain_minutes", 0) + dt
                    while obj.data["rain_minutes"] >= 60:
                        obj.data["rain_minutes"] -= 60
                        add_items(loc.ground, "clean water", 1)
                elif world.weather == "clear":
                    obj.data["rain_minutes"] = max(0, obj.data.get("rain_minutes", 0) - dt)
    for process in list(world.processes):
        if process.kind in {"cooking", "boiling"} and not active_fire(world.locations[process.location]):
            continue
        process.remaining_minutes -= dt
        if process.remaining_minutes <= 0:
            loc = world.locations[process.location]
            if process.output:
                add_items(loc.ground, process.output, 1)
            world.processes.remove(process)
            log_event(world, f"{process.kind} at {process.location} produced {process.output}.")


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
    for player in world.players.values():
        if player.connected:
            update_item_stacks(world, player.carried, dt, dry=False, place=f"{player.name}'s pack")


def update_item_stacks(world: World, stacks, dt: int, *, dry: bool, place: str) -> None:
    for stack in list(stacks):
        stack.age_minutes += dt
        if stack.item == "raw fish" and stack.age_minutes >= 720:
            stacks.remove(stack)
            log_event(world, f"Raw fish spoiled at {place}.")
        elif stack.item == "cooked fish" and stack.age_minutes >= 1440:
            stacks.remove(stack)
            log_event(world, f"Cooked fish spoiled at {place}.")
        elif stack.item in {"clean water", "unsafe water"} and stack.exposed and dry and stack.age_minutes >= 360:
            stacks.remove(stack)
            log_event(world, f"Exposed {stack.item} evaporated at {place}.")
