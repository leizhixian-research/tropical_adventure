import json
from pathlib import Path

from tropical_adventure.game import (
    available_actions,
    cancel_action,
    join_player,
    new_world,
    start_action,
    tick_world,
    world_snapshot,
)
from tropical_adventure.content import (
    AREA_DEFS,
    AREA_EXPLORE_CARDS,
    AREA_EXPLORE_ITEMS,
    AREA_LOCATION_CARDS,
    AREA_NEIGHBORS,
    DISCOVERY_ORDER,
    LOCATION_CARD_DEFS,
)
from tropical_adventure.models import ItemStack, PlacedObject, add_items, count_item
from tropical_adventure.persistence import load_world, save_world


def run_minutes(world, minutes):
    for _ in range(minutes // world.minutes_per_tick):
        tick_world(world)


def test_tick_progression_changes_time_and_connected_needs_only():
    world = new_world(seed=2)
    alice = join_player(world, "Alice")
    bob = join_player(world, "Bob")
    bob.connected = False
    alice_thirst = alice.needs["thirst"]
    bob_thirst = bob.needs["thirst"]

    tick_world(world)

    assert world.tick == 1
    assert world.minute == 363
    assert alice.needs["thirst"] > alice_thirst
    assert bob.needs["thirst"] == bob_thirst


def test_time_does_not_pass_without_connected_players():
    world = new_world(seed=2)
    alice = join_player(world, "Alice")
    alice.connected = False
    old_tick = world.tick
    old_minute = world.minute
    old_weather = world.weather

    day_changed = tick_world(world)

    assert day_changed is False
    assert world.tick == old_tick
    assert world.minute == old_minute
    assert world.weather == old_weather


def test_actions_consume_inputs_produce_outputs_and_advance_skill():
    world = new_world()
    player = join_player(world, "Alice")
    add_items(player.carried, "stones", 1)

    start_action(world, "Alice", "craft sharp stone")
    run_minutes(world, 24)

    assert count_item(player.carried, "stones") == 0
    assert count_item(player.carried, "sharp stone") == 1
    assert player.skills["knapping"] == 1


def test_available_actions_are_ordered_by_player_recent_use():
    world = new_world()
    player = join_player(world, "Alice")

    assert available_actions(world, "Alice")[:5] == ["explore", "forage", "gather", "rest", "leisure"]

    start_action(world, "Alice", "forage")
    run_minutes(world, 12)
    assert player.action_history == ["forage"]
    assert available_actions(world, "Alice")[0] == "forage"

    start_action(world, "Alice", "rest")
    run_minutes(world, 18)
    assert player.action_history[:2] == ["rest", "forage"]
    assert available_actions(world, "Alice")[:2] == ["rest", "forage"]


def test_per_player_blueprint_unlocks_are_individual_and_round_trip(tmp_path: Path):
    world = new_world()
    alice = join_player(world, "Alice")
    bob = join_player(world, "Bob")

    start_action(world, "Alice", "explore")
    run_minutes(world, 18)

    assert "fire" in alice.known_blueprints
    assert "fire" not in bob.known_blueprints
    path = tmp_path / "island.json"
    saved_path = save_world(world, path)
    loaded = load_world(saved_path)
    assert "fire" in loaded.players["Alice"].known_blueprints
    assert "fire" not in loaded.players["Bob"].known_blueprints
    assert loaded.players["Alice"].action_history == ["explore"]
    assert loaded.players["Bob"].action_history == []
    assert loaded.players["Alice"].connected is False
    assert loaded.paused is False


def test_explore_move_wash_swim_leisure_treat_wound_effects():
    world = new_world()
    player = join_player(world, "Alice")
    add_items(player.carried, "bandage leaves", 1)
    player.conditions["wounds"] = 2
    player.conditions["pain"] = 20

    start_action(world, "Alice", "treat wound")
    run_minutes(world, 18)
    assert player.conditions["treated_wound"] == 1
    assert player.conditions["pain"] < 20

    start_action(world, "Alice", "leisure")
    run_minutes(world, 12)
    assert player.needs["morale"] > 50

    start_action(world, "Alice", "wash")
    run_minutes(world, 12)
    assert player.conditions["wetness"] > 0
    assert player.needs["stress"] < 10

    start_action(world, "Alice", "explore")
    run_minutes(world, 18)
    assert world.locations["jungle outskirts"].discovered
    start_action(world, "Alice", "move", {"location": "jungle outskirts"})
    run_minutes(world, 12)
    assert player.location == "jungle outskirts"


def test_explore_finds_area_items_as_well_as_discoveries():
    world = new_world()
    player = join_player(world, "Alice")

    start_action(world, "Alice", "explore")
    run_minutes(world, 18)

    assert world.locations["jungle outskirts"].discovered is True
    found_items = {stack.item for stack in player.carried}
    beach_items = {reward[2] if len(reward) == 6 else reward[1] for reward in AREA_EXPLORE_ITEMS["beach"]}
    assert found_items & beach_items
    assert any("found" in event and "while exploring beach" in event for event in world.event_log)


def test_explore_limited_rewards_are_counted_and_saved(tmp_path: Path):
    world = new_world(seed=2)
    player = join_player(world, "Alice")

    start_action(world, "Alice", "explore")
    run_minutes(world, 18)

    assert world.locations["beach"].explore_counts["heavy_stone_1_limit"] == 1
    saved_path = save_world(world, tmp_path / "island.json")
    loaded = load_world(saved_path)
    assert loaded.locations["beach"].explore_counts["heavy_stone_1_limit"] == 1

    loaded.players["Alice"].connected = True
    loaded.players["Alice"].current_action = None
    for _ in range(12):
        start_action(loaded, "Alice", "explore")
        run_minutes(loaded, 18)

    for reward in AREA_EXPLORE_ITEMS["beach"]:
        if len(reward) == 6:
            key, _weight, _item, _min_qty, _max_qty, limit = reward
            assert loaded.locations["beach"].explore_counts.get(key, 0) <= limit


def test_action_cancellation_returns_reserved_resources():
    world = new_world()
    player = join_player(world, "Alice")
    add_items(player.carried, "stones", 1)

    start_action(world, "Alice", "craft sharp stone")
    assert count_item(player.carried, "stones") == 0
    cancel_action(world, "Alice")
    assert count_item(player.carried, "stones") == 1
    assert player.current_action is None


def test_pick_up_drop_and_disconnected_carried_items_freeze_while_ground_spoils():
    world = new_world()
    player = join_player(world, "Alice")
    join_player(world, "Bob")
    loc = world.locations[player.location]
    add_items(loc.ground, "raw fish", 1)

    start_action(world, "Alice", "pick up", {"item": "raw fish"})
    run_minutes(world, 3)
    assert count_item(player.carried, "raw fish") == 1

    player.connected = False
    add_items(loc.ground, "raw fish", 1)
    run_minutes(world, 720)

    assert count_item(player.carried, "raw fish") == 1
    assert count_item(loc.ground, "raw fish") == 0

    player.connected = True
    run_minutes(world, 720)
    assert count_item(player.carried, "raw fish") == 0
    add_items(player.carried, "raw fish", 1)
    start_action(world, "Alice", "drop", {"item": "raw fish"})
    run_minutes(world, 3)
    assert count_item(player.carried, "raw fish") == 0
    assert count_item(loc.ground, "raw fish") == 1


def test_placed_objects_are_shared_and_processes_complete():
    world = new_world(seed=3)
    alice = join_player(world, "Alice")
    bob = join_player(world, "Bob")
    for p in (alice, bob):
        p.known_blueprints.update({"fire", "shelter", "raincatcher", "cook fish", "boil water"})
    add_items(alice.carried, "sticks", 4)
    add_items(alice.carried, "leaves", 6)
    add_items(alice.carried, "vine", 2)
    start_action(world, "Alice", "build shelter")
    run_minutes(world, 90)
    assert any(o.kind == "shelter" for o in world.locations["beach"].placed)
    assert "rest" in available_actions(world, "Bob")

    add_items(alice.carried, "sticks", 2)
    add_items(alice.carried, "leaves", 1)
    start_action(world, "Alice", "start fire")
    run_minutes(world, 36)
    add_items(bob.carried, "raw fish", 1)
    start_action(world, "Bob", "cook fish")
    run_minutes(world, 6)
    assert world.processes and world.processes[0].kind == "cooking"
    # Heated processes only advance while a fire is active.
    for obj in world.locations["beach"].placed:
        if obj.kind == "fire":
            obj.active = False
            obj.fuel = 0
    run_minutes(world, 45)
    assert count_item(world.locations["beach"].ground, "cooked fish") == 0
    world.locations["beach"].placed.append(__import__("tropical_adventure.models", fromlist=["PlacedObject"]).PlacedObject("fire", fuel=1, active=True))
    run_minutes(world, 45)
    assert count_item(world.locations["beach"].ground, "cooked fish") == 1


def test_fire_burndown_raincatcher_evaporation_and_wound_processes():
    world = new_world(seed=1)
    player = join_player(world, "Alice")
    player.known_blueprints.update({"fire", "raincatcher"})
    loc = world.locations["beach"]
    add_items(player.carried, "sticks", 2)
    add_items(player.carried, "leaves", 1)
    start_action(world, "Alice", "start fire")
    run_minutes(world, 36)
    run_minutes(world, 180)
    assert any(o.kind == "fire remnants" for o in loc.placed)
    assert count_item(loc.ground, "ash") >= 1
    assert count_item(loc.ground, "charcoal") >= 1

    add_items(loc.ground, "clean water", 1)
    for stack in loc.ground:
        if stack.item == "clean water":
            stack.age_minutes = 357
    world.weather = "clear"
    tick_world(world)
    assert count_item(loc.ground, "clean water") == 0

    player.conditions["wounds"] = 1
    player.conditions["pain"] = 0
    # align to hourly boundary for wound pain tick
    world.minute = 57
    tick_world(world)
    assert player.conditions["pain"] > 0


def test_json_save_load_round_trips_world_processes_and_day_save(tmp_path: Path):
    world = new_world()
    join_player(world, "Alice")
    world.processes.append(__import__("tropical_adventure.models", fromlist=["WorldProcess"]).WorldProcess("boiling", "beach", 45, output="clean water"))
    path = tmp_path / "island.json"
    saved_path = save_world(world, path)
    loaded = load_world(saved_path)
    expected = world.to_dict()
    expected["players"]["Alice"]["connected"] = False
    assert loaded.to_dict() == expected


def test_save_world_uses_island_day_time_name_in_requested_directory(tmp_path: Path):
    world = new_world()
    join_player(world, "Alice")
    load_path = tmp_path / "custom-load-file.json"

    first = save_world(world, load_path)
    world.minute = 9 * 60 + 15
    world.tick = 105
    second = save_world(world, load_path)

    assert first == tmp_path / "island_1_360.json"
    assert second == tmp_path / "island_1_555.json"
    assert sorted(p.name for p in tmp_path.glob("island*.json")) == ["island_1_360.json", "island_1_555.json"]
    assert load_world(second).minute == 9 * 60 + 15


def test_save_world_overwrites_existing_file_even_when_day_and_time_match(tmp_path: Path):
    world = new_world()
    player = join_player(world, "Alice")
    load_path = tmp_path / "custom-load-file.json"

    first = save_world(world, load_path)
    player.conditions["hunger"] = 12
    world.tick = 99
    second = save_world(world, load_path)

    assert first == second == tmp_path / "island_1_360.json"
    assert sorted(p.name for p in tmp_path.glob("island*.json")) == ["island_1_360.json"]
    assert load_world(second).players["Alice"].conditions["hunger"] == 12


def test_load_world_uses_requested_save_file_directly(tmp_path: Path):
    path = tmp_path / "island.json"
    world = new_world()
    world.day = 2
    world.minute = 9 * 60
    path.write_text(json.dumps(world.to_dict()), encoding="utf-8")

    loaded = load_world(path)

    assert loaded.day == 2
    assert loaded.minute == 9 * 60


def test_load_world_starts_new_world_when_requested_save_file_is_missing_even_if_legacy_snapshots_exist(tmp_path: Path):
    path = tmp_path / "island.json"
    legacy_world = new_world()
    legacy_world.day = 2
    legacy_world.minute = 9 * 60
    (tmp_path / "island-day002-0900.json").write_text("{}", encoding="utf-8")

    loaded = load_world(path)

    assert loaded.day == 1
    assert loaded.minute == 6 * 60


def test_world_event_log_stores_only_last_5_events():
    world = new_world()
    world.event_log = [f"event {i}" for i in range(12)]

    saved = world.to_dict()
    loaded = type(world).from_dict(saved)

    assert saved["event_log"] == [f"event {i}" for i in range(7, 12)]
    assert loaded.event_log == [f"event {i}" for i in range(7, 12)]


def test_add_items_moves_interacted_stack_to_most_recent_position():
    stacks = [ItemStack("sticks", 1), ItemStack("coconut", 1)]

    add_items(stacks, "sticks", 2)

    assert [(stack.item, stack.qty) for stack in stacks] == [("coconut", 1), ("sticks", 3)]


def test_gather_rejects_arbitrary_client_requested_items():
    world = new_world()
    join_player(world, "Alice")
    try:
        start_action(world, "Alice", "gather", {"item": "cooked fish"})
    except ValueError as exc:
        assert "cannot gather cooked fish" in str(exc)
    else:
        raise AssertionError("arbitrary gather item was accepted")


def test_forage_rejects_arbitrary_client_requested_items():
    world = new_world()
    join_player(world, "Alice")
    try:
        start_action(world, "Alice", "forage", {"item": "cooked fish"})
    except ValueError as exc:
        assert "cannot forage cooked fish" in str(exc)
    else:
        raise AssertionError("arbitrary forage item was accepted")


def test_forage_rejects_items_that_need_a_different_action():
    world = new_world()
    player = join_player(world, "Alice")
    for location in world.locations.values():
        location.discovered = True
    player.location = "rocks"

    try:
        start_action(world, "Alice", "forage", {"item": "raw fish"})
    except ValueError as exc:
        assert "cannot forage raw fish" in str(exc)
    else:
        raise AssertionError("fish resource was accepted as a forage action")


def test_card_survival_content_locations_are_loaded_and_discoverable():
    world = new_world()
    player = join_player(world, "Alice")

    wiki_areas = {
        "acid lake",
        "atoll",
        "beach",
        "bay",
        "bird rock",
        "deep jungle",
        "desolate beach",
        "eastern grasslands",
        "eastern highlands",
        "enclosure",
        "highland hole",
        "jungle",
        "jungle highlands",
        "jungle outskirts",
        "mangrove forest",
        "raft",
        "rocks",
        "secret cove",
        "secret valley",
        "volcano",
        "western grasslands",
        "western highlands",
        "wetlands",
        "bat cave",
        "cellar",
        "dark cave",
        "grasslands cave",
        "macaque den",
        "mud hut",
        "plane crash",
        "sea cave",
        "shed",
        "stone hut",
        "tidal cave",
        "crystal chamber",
        "damp chamber",
        "darkness",
        "flooded chamber",
        "high chamber",
        "medium chamber",
        "low chamber",
        "narrow tunnel",
        "tunnel",
    }
    wiki_location_cards = {
        "bat colony",
        "brimstone vent",
        "collapsed tunnel entrance",
        "copper vein",
        "debris",
        "dry acid lake",
        "dry cave pond",
        "dry puddle",
        "flooded tide pool",
        "hole",
        "narrow passage",
        "sand",
        "seawater",
        "shaft",
        "shipwreck",
        "skeleton",
        "tide pool",
        "wall scratchings",
    }

    assert wiki_areas <= set(world.locations)
    assert wiki_location_cards <= set(LOCATION_CARD_DEFS)
    assert not ((wiki_location_cards - wiki_areas) & set(world.locations))
    assert set(name for name, _blueprints in DISCOVERY_ORDER) <= set(AREA_DEFS)
    assert {"bay", "jungle outskirts", "rocks"} <= set(AREA_NEIGHBORS["beach"])
    assert AREA_NEIGHBORS["acid lake"] == ["volcano"]
    assert "dry acid lake" in world.locations["acid lake"].location_cards
    assert AREA_EXPLORE_CARDS["acid lake"] == ["brimstone vent"]
    assert "brimstone vent" not in world.locations["acid lake"].location_cards
    assert {"sea", "copper vein"} <= set(world.locations["rocks"].location_cards)
    assert "tide pool" not in world.locations["rocks"].location_cards
    assert {"copper vein", "skeleton"} <= set(AREA_LOCATION_CARDS["highland hole"])
    assert "wall scratchings" in AREA_LOCATION_CARDS["sea cave"]
    assert "tide pool" in AREA_LOCATION_CARDS["tidal cave"]
    assert "exit" in AREA_LOCATION_CARDS["plane crash"]
    assert world.locations["beach"].discovered is True
    assert world.locations["bay"].resources["raw fish"]["action"] == "fish"

    for expected in ["jungle outskirts", "rocks"]:
        start_action(world, "Alice", "explore")
        run_minutes(world, 18)
        assert world.locations[expected].discovered is True
    player.location = "rocks"
    start_action(world, "Alice", "explore")
    run_minutes(world, 18)
    assert "tide pool" in world.locations["rocks"].location_cards
    player.location = "acid lake"
    start_action(world, "Alice", "explore")
    run_minutes(world, 18)
    assert "brimstone vent" in world.locations["acid lake"].location_cards
    assert "fire" in player.known_blueprints
    assert "shelter" in player.known_blueprints


def test_coconuts_are_finite_location_resources_that_regrow_over_time():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    assert beach.resources["coconut"]["qty"] == 2
    start_action(world, "Alice", "forage", {"item": "coconut"})
    run_minutes(world, 12)
    assert count_item(player.carried, "coconut") == 1
    assert beach.resources["coconut"]["qty"] == 1

    start_action(world, "Alice", "forage", {"item": "coconut"})
    run_minutes(world, 12)
    assert count_item(player.carried, "coconut") == 2
    assert beach.resources["coconut"]["qty"] == 0

    try:
        start_action(world, "Alice", "forage", {"item": "coconut"})
    except ValueError as exc:
        assert "coconut is depleted" in str(exc)
    else:
        raise AssertionError("depleted coconuts could still be foraged")

    run_minutes(world, 3 * 1440)
    assert beach.resources["coconut"]["qty"] == 1


def test_infinite_water_source_can_be_gathered_without_depletion():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    assert beach.resources["unsafe water"]["infinite"] is True
    for _ in range(3):
        start_action(world, "Alice", "gather", {"item": "unsafe water"})
        run_minutes(world, 12)

    assert count_item(player.carried, "unsafe water") == 3
    assert beach.resources["unsafe water"]["infinite"] is True


def test_gather_accepts_any_location_resource_marked_for_gather():
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["secret cove"].discovered = True
    player.location = "secret cove"

    start_action(world, "Alice", "gather", {"item": "stones"})
    run_minutes(world, 12)

    assert count_item(player.carried, "stones") == 1


def test_fish_and_tend_fire_are_available_when_prerequisites_are_met():
    world = new_world()
    player = join_player(world, "Alice")
    for location in world.locations.values():
        location.discovered = True
    player.location = "rocks"
    add_items(player.carried, "sharp stone", 1)
    start_action(world, "Alice", "explore")
    run_minutes(world, 18)

    assert "fish" in available_actions(world, "Alice")
    start_action(world, "Alice", "fish")
    run_minutes(world, 36)
    assert count_item(player.carried, "raw fish") == 1

    player.location = "beach"
    player.known_blueprints.add("fire")
    add_items(player.carried, "sticks", 3)
    add_items(player.carried, "leaves", 1)
    start_action(world, "Alice", "start fire")
    run_minutes(world, 36)

    assert "tend fire" in available_actions(world, "Alice")
    fire = next(obj for obj in world.locations["beach"].placed if obj.kind == "fire")
    assert fire.fuel == 1
    start_action(world, "Alice", "tend fire")
    run_minutes(world, 6)
    assert fire.fuel == 2


def test_move_rejects_invalid_destination_before_action_starts():
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["jungle outskirts"].discovered = True

    for destination in ("nope", ""):
        try:
            start_action(world, "Alice", "move", {"location": destination})
        except ValueError as exc:
            assert "destination is not a discovered neighbor" in str(exc)
        else:
            raise AssertionError("invalid move destination was accepted")
    assert player.current_action is None


def test_world_snapshot_is_player_dependent_and_uses_local_firelight():
    world = new_world()
    player = join_player(world, "Alice")
    world.minute = 23 * 60
    snapshot = world_snapshot(world, "Alice")
    assert set(snapshot["locations"]) == {"beach"}
    assert snapshot["light"] == "dark"
    assert "lights" not in snapshot

    world.locations["jungle outskirts"].discovered = True
    world.locations["jungle outskirts"].placed.append(PlacedObject("fire", fuel=1, active=True))
    snapshot = world_snapshot(world, "Alice")
    assert snapshot["light"] == "dark"
    assert set(snapshot["locations"]) == {"beach", "jungle outskirts"}
    assert snapshot["locations"]["jungle outskirts"]["placed"] == []

    player.location = "jungle outskirts"
    snapshot = world_snapshot(world, "Alice")
    assert snapshot["light"] == "firelit"
    assert snapshot["locations"]["jungle outskirts"]["placed"] == [
        {"kind": "fire", "fuel": 1, "active": True, "data": {}}
    ]


def test_player_snapshot_includes_only_current_player_state():
    world = new_world()
    alice = join_player(world, "Alice")
    bob = join_player(world, "Bob")
    bob.carried.append(ItemStack("coconut", 1))
    bob.needs["thirst"] = 99

    snapshot = world_snapshot(world, "Alice")

    assert set(snapshot["players"]) == {"Alice"}
    assert snapshot["players"]["Alice"]["needs"] == alice.needs
    assert "available_actions" in snapshot["players"]["Alice"]
    assert "available_actions" in snapshot
    assert "Bob" not in snapshot["players"]
    assert "known_blueprints" not in snapshot["players"]["Alice"]
    assert "skills" not in snapshot["players"]["Alice"]
    assert "processes" not in snapshot
