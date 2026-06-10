import json
from pathlib import Path

from tropical_adventure.game import (
    available_actions,
    cancel_action,
    join_player,
    new_world,
    start_action,
    tick_world,
    update_world_processes,
    world_snapshot,
)
from tropical_adventure.content import (
    ACTION_DEFS,
    ACTION_DESCRIPTIONS,
    ACTION_DURATIONS,
    AREA_DEFS,
    AREA_EXPLORE_CARDS,
    AREA_EXPLORE_ITEMS,
    AREA_LOCATION_CARDS,
    AREA_NEIGHBORS,
    CARD_SURVIVAL_STAT_RANGES,
    DISCOVERY_ORDER,
    DRINK_VALUES,
    FISH_TRAP_OUTPUTS,
    FISH_TRAP_SOAK_RANGE,
    FOOD_SATURATION_VALUES,
    FOOD_VALUES,
    LOCATION_CARD_DEFS,
    PREREQUISITE_ACTIONS,
    RAFT_EVENT_PASSING_SHIP,
    RAFT_RESCUE_DISTANCE,
    RESOURCE_HARVESTS,
    SNARE_TRAP_SOAK_RANGE,
    TIDE_POOL_OUTPUTS,
    TOOL_DURABILITY,
    scale_wiki_delta,
    scale_wiki_value,
)
from tropical_adventure.models import ItemStack, PlacedObject, SATURATION_STAT_KEYS, add_items, count_item
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
    alice_hunger = alice.needs["hunger"]
    alice_fatigue = alice.needs["fatigue"]
    bob_thirst = bob.needs["thirst"]
    bob_hunger = bob.needs["hunger"]
    bob_fatigue = bob.needs["fatigue"]

    tick_world(world)

    assert world.tick == 1
    assert world.minute == 363
    assert alice.needs["thirst"] > alice_thirst
    assert bob.needs["thirst"] == bob_thirst
    for _ in range(3):
        tick_world(world)
    assert alice.needs["hunger"] > alice_hunger
    assert alice.needs["fatigue"] > alice_fatigue
    assert bob.needs["hunger"] == bob_hunger
    assert bob.needs["fatigue"] == bob_fatigue


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


def test_card_survival_source_ranges_scale_to_normalized_player_stats():
    assert CARD_SURVIVAL_STAT_RANGES["hydration"] == (0, 180)
    assert CARD_SURVIVAL_STAT_RANGES["stamina"] == (0, 32)
    assert CARD_SURVIVAL_STAT_RANGES["stress"] == (0, 240)
    assert CARD_SURVIVAL_STAT_RANGES["morale"] == (-350, 350)

    assert scale_wiki_value(90, "hydration") == 50
    assert scale_wiki_delta(63, "hydration") == 35
    assert scale_wiki_value(16, "stamina") == 50
    assert scale_wiki_value(120, "stress") == 50
    assert scale_wiki_value(-350, "morale") == 0
    assert scale_wiki_value(0, "morale") == 50
    assert scale_wiki_value(350, "morale") == 100
    assert DRINK_VALUES["clean water"] == 35
    assert FOOD_VALUES["cooked fish"] == 35


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


def test_actions_are_gated_by_concrete_prerequisites_and_round_trip(tmp_path: Path):
    world = new_world()
    alice = join_player(world, "Alice")
    join_player(world, "Bob")

    add_items(alice.carried, "stones", 1)
    assert "craft sharp stone" in available_actions(world, "Alice")
    player_state_keys = {
        "name",
        "location",
        "connected",
        "status",
        "outcome_reason",
        "ended_day",
        "ended_minute",
        "needs",
        "conditions",
        "stats",
        "skills",
        "carried",
        "current_action",
        "action_history",
    }
    snapshot_player_keys = {
        "name",
        "location",
        "connected",
        "status",
        "outcome_reason",
        "ended_day",
        "ended_minute",
        "needs",
        "stats",
        "carrying",
        "carried",
        "current_action",
        "available_actions",
    }
    assert set(alice.to_dict()) == player_state_keys
    assert set(world.to_dict()["players"]["Alice"]) == player_state_keys
    assert set(world_snapshot(world, "Alice")["players"]["Alice"]) == snapshot_player_keys

    path = tmp_path / "island.json"
    saved_path = save_world(world, path)
    loaded = load_world(saved_path)
    assert loaded.players["Alice"].action_history == []
    assert loaded.players["Bob"].action_history == []
    assert loaded.players["Alice"].connected is False
    assert loaded.paused is False


def test_player_death_sets_loss_outcome_and_blocks_actions():
    world = new_world()
    player = join_player(world, "Alice")
    join_player(world, "Bob")
    world.minute = 6 * 60 - world.minutes_per_tick
    player.needs["health"] = 1
    player.needs["thirst"] = 100
    start_action(world, "Bob", "rest")
    start_action(world, "Alice", "rest")

    tick_world(world)

    assert world.outcome == "loss"
    assert world.outcome_player == "Alice"
    assert world.outcome_reason == "dehydration"
    assert player.status == "dead"
    assert player.current_action is None
    assert world.players["Bob"].current_action is None
    assert available_actions(world, "Alice") == []
    snapshot = world_snapshot(world, "Alice")
    assert snapshot["outcome"] == {
        "kind": "loss",
        "player": "Alice",
        "reason": "dehydration",
        "day": 1,
        "minute": 360,
    }
    assert snapshot["players"]["Alice"]["status"] == "dead"
    assert "Alice died from dehydration." in world.event_log
    try:
        start_action(world, "Alice", "rest")
    except ValueError as exc:
        assert "game is over" in str(exc)
    else:
        raise AssertionError("dead player acted after loss")


def test_raft_voyage_final_distance_sets_win_outcome_and_round_trips(tmp_path: Path):
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["raft"].discovered = True
    player.location = "raft"
    world.raft_distance = 2010

    assert "sail raft" in available_actions(world, "Alice")
    start_action(world, "Alice", "sail raft")
    run_minutes(world, 60)

    assert world.outcome == "win"
    assert world.outcome_player == "Alice"
    assert world.outcome_reason == "rescued after completing raft voyage"
    assert player.status == "escaped"
    assert player.current_action is None
    assert available_actions(world, "Alice") == []
    assert "Alice was rescued by a ship." in world.event_log
    snapshot = world_snapshot(world, "Alice")
    assert snapshot["outcome"]["kind"] == "win"
    assert snapshot["players"]["Alice"]["status"] == "escaped"
    assert snapshot["raft"]["distance"] == RAFT_RESCUE_DISTANCE

    saved_path = save_world(world, tmp_path / "island.json")
    loaded = load_world(saved_path)

    assert loaded.outcome == "win"
    assert loaded.outcome_player == "Alice"
    assert loaded.outcome_reason == "rescued after completing raft voyage"
    assert loaded.raft_distance == RAFT_RESCUE_DISTANCE
    assert loaded.players["Alice"].status == "escaped"
    assert loaded.players["Alice"].connected is False


def test_passing_ship_window_can_be_signaled_or_missed():
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["raft"].discovered = True
    player.location = "raft"
    world.raft_distance = 330

    start_action(world, "Alice", "sail raft")
    run_minutes(world, 60)

    assert world.raft_event == RAFT_EVENT_PASSING_SHIP
    assert world.raft_event_remaining_minutes == 90
    assert world.raft_signal_progress == 0
    assert "wave and shout" in available_actions(world, "Alice")
    assert "signal with mirror" not in available_actions(world, "Alice")

    world.raft_signal_progress = 99
    start_action(world, "Alice", "wave and shout")
    run_minutes(world, 15)

    assert world.outcome == "win"
    assert world.outcome_reason == "rescued by passing ship"
    assert player.status == "escaped"

    missed = new_world()
    missed_player = join_player(missed, "Alice")
    missed.locations["raft"].discovered = True
    missed_player.location = "raft"
    missed.raft_event = RAFT_EVENT_PASSING_SHIP
    missed.raft_event_remaining_minutes = 90

    run_minutes(missed, 90)

    assert missed.raft_event is None
    assert missed.raft_missed_ships == 1
    assert missed.outcome is None


def test_defined_actions_are_known_from_start_but_inputs_gate_execution():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    assert "cook coconut fish" in ACTION_DURATIONS
    assert "cook coconut fish" not in available_actions(world, "Alice")
    try:
        start_action(world, "Alice", "cook coconut fish")
    except ValueError as exc:
        assert "action unavailable: cook coconut fish" in str(exc)
    else:
        raise AssertionError("cook coconut fish started without concrete prerequisites")

    beach.placed.append(PlacedObject("fire", fuel=1, active=True))
    add_items(player.carried, "raw fish", 1)
    add_items(player.carried, "coconut meat", 1)
    add_items(player.carried, "seaweed", 1)
    add_items(player.carried, "cooking pot", 1, data={"liquid_capacity": 600, "sealed": 1, "cookable": 1})

    assert "cook coconut fish" in available_actions(world, "Alice")


def test_unattended_process_actions_do_not_block_player_work():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    beach.placed.append(PlacedObject("fire", fuel=2, active=True))
    add_items(player.carried, "unsafe water", 1)

    start_action(world, "Alice", "rest")
    rest_action = player.current_action

    start_action(world, "Alice", "boil water")

    assert player.current_action is rest_action
    assert count_item(player.carried, "unsafe water") == 0
    assert world.processes[-1].kind == "boiling"
    assert world.processes[-1].output == "clean water"

    try:
        start_action(world, "Alice", "gather")
    except ValueError as exc:
        assert "player already has an action" in str(exc)
    else:
        raise AssertionError("blocking action started while player was already busy")


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
    assert set(DISCOVERY_ORDER) <= set(AREA_DEFS)
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


def test_card_survival_inspired_actions_are_structured_and_bilingual():
    concrete_actions = {
        "harvest coconuts",
        "harvest aloe vera",
        "harvest lemongrass",
        "harvest ginger",
        "harvest spider lily",
        "harvest snakegrass",
        "dig wild yam",
        "collect bananas",
        "cut nipa fruit",
        "harvest coffee berries",
        "harvest chilies",
        "harvest jasmine",
        "harvest assorted mushrooms",
        "harvest puffballs",
        "harvest magic mushrooms",
        "forage tide pool",
        "crack coconut",
        "weave cord",
        "make aloe gel",
        "apply aloe leaf",
        "apply aloe gel",
        "brew ginger tea",
        "brew spider lily tea",
        "brew jasmine tea",
        "make bug repellent",
        "apply bug repellent",
        "prepare yam",
        "extract nipa seeds",
        "extract coffee beans",
        "roast coffee beans",
        "brew coffee",
        "craft leaf bed",
        "build drying rack",
        "dry fish",
        "make wood shavings",
        "build campfire",
        "build fish trap",
        "check fish trap",
        "build snare trap",
        "bait snare trap",
        "check snare trap",
        "cook meat",
        "build water filter",
        "filter water",
        "build solar still",
    }

    assert concrete_actions <= set(ACTION_DEFS)
    assert all("direct" not in data for data in ACTION_DEFS.values())
    assert "craft sharp stone" in PREREQUISITE_ACTIONS
    assert "build shelter" in PREREQUISITE_ACTIONS
    assert "harvest coconuts" not in PREREQUISITE_ACTIONS
    assert "treat wound" not in PREREQUISITE_ACTIONS
    assert ACTION_DESCRIPTIONS["en"]["harvest coconuts"].startswith("climb a palm")
    assert ACTION_DESCRIPTIONS["zh"]["forage tide pool"] == "在潮池里寻找贝类和海藻"


def test_palm_and_tide_pool_have_concrete_actions_instead_of_drag_interactions():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    assert "harvest coconuts" in available_actions(world, "Alice")
    start_action(world, "Alice", "harvest coconuts")
    run_minutes(world, 30)

    assert count_item(player.carried, "coconut") == 1
    assert beach.resources["coconut"]["qty"] == 1
    assert player.skills["climbing"] == 1

    player.location = "rocks"
    world.locations["rocks"].discovered = True
    world.locations["rocks"].location_cards.append("tide pool")

    assert "forage tide pool" in available_actions(world, "Alice")
    start_action(world, "Alice", "forage tide pool")
    run_minutes(world, 15)

    assert {stack.item for stack in player.carried} & set(TIDE_POOL_OUTPUTS)
    assert player.skills["fishing"] == 1


def test_concrete_crafting_and_processing_objects_extend_survival_loops():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    add_items(player.carried, "coconut", 1)
    start_action(world, "Alice", "crack coconut")
    run_minutes(world, 12)
    assert count_item(player.carried, "coconut water") == 1
    assert count_item(player.carried, "coconut meat") == 1
    assert count_item(player.carried, "coconut shell") == 1

    add_items(player.carried, "leaves", 8)
    add_items(player.carried, "vine", 1)
    start_action(world, "Alice", "weave cord")
    run_minutes(world, 30)
    assert count_item(player.carried, "fiber cord") == 1

    start_action(world, "Alice", "craft leaf bed")
    run_minutes(world, 30)
    assert any(obj.kind == "leaf bed" for obj in beach.placed)

    add_items(player.carried, "long stick", 5)
    add_items(player.carried, "fiber cord", 1)
    start_action(world, "Alice", "build drying rack")
    run_minutes(world, 60)
    assert any(obj.kind == "drying rack" for obj in beach.placed)

    add_items(player.carried, "raw fish", 1)
    start_action(world, "Alice", "dry fish")
    run_minutes(world, 12)
    assert world.processes[-1].kind == "drying"
    run_minutes(world, 12 * 60)
    assert count_item(beach.ground, "dried fish") == 1


def test_wood_shavings_campfire_and_meat_cooking_extend_fire_loop():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    add_items(player.carried, "wood", 1)
    assert "make wood shavings" in available_actions(world, "Alice")
    start_action(world, "Alice", "make wood shavings")
    run_minutes(world, 15)

    assert count_item(player.carried, "wood shavings") == 3

    add_items(player.carried, "stones", 4)
    add_items(player.carried, "sticks", 3)
    assert "build campfire" in available_actions(world, "Alice")
    start_action(world, "Alice", "build campfire")
    run_minutes(world, 60)

    campfire = next(obj for obj in beach.placed if obj.kind == "campfire")
    assert campfire.active is True
    assert campfire.fuel == 3

    add_items(player.carried, "raw meat", 1)
    assert "cook meat" in available_actions(world, "Alice")
    start_action(world, "Alice", "cook meat")
    run_minutes(world, 9)
    assert world.processes[-1].output == "cooked meat"

    run_minutes(world, 60)
    assert count_item(beach.ground, "cooked meat") == 1


def test_fish_trap_soaks_catches_and_resets_after_checking():
    world = new_world()
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    add_items(player.carried, "long stick", 3)
    add_items(player.carried, "fiber cord", 2)

    assert "build fish trap" in available_actions(world, "Alice")
    start_action(world, "Alice", "build fish trap")
    run_minutes(world, 75)

    trap = next(obj for obj in beach.placed if obj.kind == "fish trap")
    assert "check fish trap" not in available_actions(world, "Alice")

    assert FISH_TRAP_SOAK_RANGE == (25 * 60, 3 * 1440 + 3 * 60)
    assert FISH_TRAP_SOAK_RANGE[0] <= trap.data["target_minutes"] <= FISH_TRAP_SOAK_RANGE[1]
    remaining_soak = int(trap.data["target_minutes"]) - int(trap.data["soak_minutes"])
    run_minutes(world, remaining_soak - world.minutes_per_tick)
    assert "check fish trap" not in available_actions(world, "Alice")

    run_minutes(world, world.minutes_per_tick)
    assert trap.data["ready"] == 1
    assert trap.data["catch"] in FISH_TRAP_OUTPUTS
    assert "check fish trap" in available_actions(world, "Alice")

    start_action(world, "Alice", "check fish trap")
    run_minutes(world, 12)

    assert sum(count_item(player.carried, item) for item in FISH_TRAP_OUTPUTS) == 1
    assert not trap.data.get("ready")
    assert trap.data["soak_minutes"] < trap.data["target_minutes"]
    assert FISH_TRAP_SOAK_RANGE[0] <= trap.data["target_minutes"] <= FISH_TRAP_SOAK_RANGE[1]


def test_snare_trap_needs_bait_then_catches_raw_meat():
    world = new_world()
    player = join_player(world, "Alice")
    player.location = "jungle outskirts"
    world.locations["jungle outskirts"].discovered = True
    loc = world.locations["jungle outskirts"]
    add_items(player.carried, "sticks", 2)
    add_items(player.carried, "fiber cord", 1)

    assert "build snare trap" in available_actions(world, "Alice")
    start_action(world, "Alice", "build snare trap")
    run_minutes(world, 45)

    trap = next(obj for obj in loc.placed if obj.kind == "snare trap")
    assert trap.data == {"baited": 0, "soak_minutes": 0}
    assert "bait snare trap" not in available_actions(world, "Alice")

    add_items(player.carried, "coconut meat", 1)
    assert "bait snare trap" in available_actions(world, "Alice")
    start_action(world, "Alice", "bait snare trap")
    run_minutes(world, 6)

    assert trap.data["baited"] == 1
    assert SNARE_TRAP_SOAK_RANGE == (18 * 60 + 45, 2 * 1440 + 8 * 60 + 15)
    assert SNARE_TRAP_SOAK_RANGE[0] <= trap.data["target_minutes"] <= SNARE_TRAP_SOAK_RANGE[1]
    remaining_soak = int(trap.data["target_minutes"]) - int(trap.data["soak_minutes"])
    run_minutes(world, remaining_soak - world.minutes_per_tick)
    assert "check snare trap" not in available_actions(world, "Alice")

    run_minutes(world, world.minutes_per_tick)
    assert trap.data["ready"] == 1
    assert "check snare trap" in available_actions(world, "Alice")

    start_action(world, "Alice", "check snare trap")
    run_minutes(world, 12)

    assert count_item(player.carried, "raw meat") == 1
    assert trap.data == {"baited": 0, "soak_minutes": 0}


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


def test_player_snapshot_includes_current_player_and_public_nearby_player_state():
    world = new_world()
    alice = join_player(world, "Alice")
    bob = join_player(world, "Bob")
    cara = join_player(world, "Cara")
    cara.location = "rocks"
    dan = join_player(world, "Dan")
    dan.connected = False
    bob.carried.append(ItemStack("coconut", 1))
    bob.needs["thirst"] = 99
    start_action(world, "Bob", "rest")

    snapshot = world_snapshot(world, "Alice")

    assert set(snapshot["players"]) == {"Alice", "Bob"}
    assert snapshot["players"]["Alice"]["needs"] == alice.needs
    assert "available_actions" in snapshot["players"]["Alice"]
    assert "available_actions" in snapshot
    assert snapshot["players"]["Bob"] == {
        "name": "Bob",
        "location": "beach",
        "connected": True,
        "status": "alive",
        "current_action": {"name": "rest", "remaining_minutes": 18, "total_minutes": 18},
    }
    assert "Cara" not in snapshot["players"]
    assert "Dan" not in snapshot["players"]
    assert "needs" not in snapshot["players"]["Bob"]
    assert "carried" not in snapshot["players"]["Bob"]
    assert "available_actions" not in snapshot["players"]["Bob"]
    assert "skills" not in snapshot["players"]["Alice"]
    assert "processes" not in snapshot


def test_player_snapshot_normalizes_stats_to_0_100_higher_is_better():
    world = new_world()
    alice = join_player(world, "Alice")
    alice.needs.update({"thirst": 85, "hunger": 60, "fatigue": 75, "stress": 30, "health": 90})
    alice.conditions.update(
        {
            "pain": 40,
            "wetness": 85,
            "wounds": 3,
            "filth": 45,
            "sunburn": 120,
            "mania": 35,
            "derealization": 30,
            "isolation": 20,
            "food_poisoning": 80,
            "alcohol": 10,
            "psilocybin": 55,
        }
    )
    alice.stats["coconut_appetite"] = 18

    snapshot = world_snapshot(world, "Alice")
    stats = snapshot["players"]["Alice"]["stats"]

    assert stats["health"] == 90
    assert stats["hydration"] == 15
    assert stats["satiation"] == 40
    assert stats["stamina"] == 25
    assert stats["calm"] == 70
    assert stats["comfort"] == 60
    assert stats["dryness"] == 15
    assert stats["wound_recovery"] == 25
    assert stats["sun_safety"] == 0
    assert stats["mania_control"] == 65
    assert stats["derealization_control"] == 70
    assert stats["isolation_resilience"] == 80
    assert stats["food_poisoning_recovery"] == 20
    assert stats["sobriety"] == 90
    assert stats["psilocybin_grounding"] == 45
    assert stats["coconut_appetite"] == 18
    assert "ginger_settledness" in stats
    assert all(stat in stats for stat in SATURATION_STAT_KEYS)
    assert all(0 <= value <= 100 for value in stats.values())


def test_repeated_food_lowers_matching_saturation_and_raw_food_adds_poisoning():
    world = new_world()
    player = join_player(world, "Alice")
    player.needs["hunger"] = 80
    add_items(player.carried, "raw fish", 1)

    start_action(world, "Alice", "eat")
    run_minutes(world, 3)

    assert player.stats["fish_appetite"] == 82
    assert player.conditions["food_poisoning"] == 10
    assert player.conditions["nausea"] > 0
    assert world_snapshot(world, "Alice")["players"]["Alice"]["stats"]["food_poisoning_recovery"] == 90

    run_minutes(world, 57)

    assert player.stats["fish_appetite"] == 85
    assert player.conditions["food_poisoning"] == 8


def test_plant_resources_use_concrete_harvest_actions_and_regrow():
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["jungle outskirts"].discovered = True
    player.location = "jungle outskirts"
    loc = world.locations["jungle outskirts"]

    assert loc.resources["aloe vera"]["qty"] == 1
    assert "harvest aloe vera" in available_actions(world, "Alice")
    start_action(world, "Alice", "harvest aloe vera")
    run_minutes(world, 15)

    assert count_item(player.carried, "aloe vera leaf") == 1
    assert loc.resources["aloe vera"]["qty"] == 0
    assert "harvest aloe vera" not in available_actions(world, "Alice")
    assert player.skills["herbology"] == 1

    run_minutes(world, 7 * 1440)

    assert loc.resources["aloe vera"]["qty"] == 1
    assert "harvest aloe vera" in available_actions(world, "Alice")


def test_plant_processing_uses_tools_and_fire_without_consuming_tools():
    world = new_world()
    player = join_player(world, "Alice")
    loc = world.locations["beach"]
    add_items(player.carried, "aloe vera leaf", 2)
    add_items(player.carried, "sharp stone", 1)

    assert "make aloe gel" in available_actions(world, "Alice")
    start_action(world, "Alice", "make aloe gel")
    run_minutes(world, 30)

    assert count_item(player.carried, "aloe gel") == 3
    assert count_item(player.carried, "sharp stone") == 1

    add_items(player.carried, "ginger", 1)
    add_items(player.carried, "clean water", 1)
    assert "brew ginger tea" not in available_actions(world, "Alice")

    loc.placed.append(PlacedObject("fire", fuel=1, active=True))
    assert "brew ginger tea" in available_actions(world, "Alice")
    start_action(world, "Alice", "brew ginger tea")
    run_minutes(world, 15)

    assert count_item(player.carried, "ginger tea") == 1
    assert count_item(player.carried, "ginger") == 0
    assert count_item(player.carried, "clean water") == 0
    assert count_item(player.carried, "sharp stone") == 1


def test_aloe_and_bug_repellent_apply_condition_effects():
    world = new_world()
    player = join_player(world, "Alice")
    player.conditions.update({"sunburn": 30, "back_pain": 20, "bug_bites": 25, "burns": 15, "pain": 20})
    add_items(player.carried, "aloe vera leaf", 1)

    start_action(world, "Alice", "apply aloe leaf")
    run_minutes(world, 3)

    assert player.conditions["sunburn"] == 20
    assert player.conditions["bug_bites"] == 17
    assert player.conditions["pain"] == 16

    add_items(player.carried, "aloe gel", 1)
    start_action(world, "Alice", "apply aloe gel")
    run_minutes(world, 3)

    assert player.conditions["sunburn"] == 0
    assert player.conditions["burns"] == 1

    player.location = "jungle"
    world.locations["jungle"].discovered = True
    before = world_snapshot(world, "Alice")["players"]["Alice"]["stats"]["bug_protection"]
    add_items(player.carried, "bug repellent", 1)
    start_action(world, "Alice", "apply bug repellent")
    run_minutes(world, 3)
    after = world_snapshot(world, "Alice")["players"]["Alice"]["stats"]["bug_protection"]

    assert before == 55
    assert after == 100
    assert player.conditions["bug_repellent"] == 96

    run_minutes(world, 60)

    assert player.conditions["bug_repellent"] < 96


def test_yam_is_risky_raw_but_safe_after_preparation():
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["jungle"].discovered = True
    player.location = "jungle"

    assert "dig wild yam" in available_actions(world, "Alice")
    start_action(world, "Alice", "dig wild yam")
    run_minutes(world, 60)

    assert 2 <= count_item(player.carried, "yam") <= 4
    assert player.conditions["filth"] >= 50
    assert player.conditions["hand_damage"] >= 25

    player.needs["hunger"] = 80
    start_action(world, "Alice", "eat")
    run_minutes(world, 3)

    assert player.conditions["food_poisoning"] >= 10
    assert count_item(player.carried, "yam") >= 1

    add_items(player.carried, "clean water", 1)
    add_items(player.carried, "sharp stone", 1)
    world.locations["jungle"].placed.append(PlacedObject("fire", fuel=1, active=True))
    assert "prepare yam" in available_actions(world, "Alice")
    start_action(world, "Alice", "prepare yam")
    run_minutes(world, 30)

    assert count_item(player.carried, "cooked yam") == 1
    assert count_item(player.carried, "sharp stone") == 1


def test_medicinal_drinks_and_stimulants_apply_organic_effects():
    world = new_world()
    player = join_player(world, "Alice")

    player.needs.update({"thirst": 70, "fatigue": 70, "stress": 30, "morale": 40})
    player.conditions.update({"nausea": 30, "diarrhea": 25, "food_poisoning": 20, "fever": 20, "headache": 20})
    add_items(player.carried, "ginger tea", 1)
    start_action(world, "Alice", "drink")
    run_minutes(world, 3)

    assert player.needs["thirst"] == 31
    assert player.conditions["nausea"] == 12
    assert player.conditions["diarrhea"] == 13
    assert player.conditions["food_poisoning"] == 14

    add_items(player.carried, "spider lily tea", 1)
    start_action(world, "Alice", "drink")
    run_minutes(world, 3)

    assert player.conditions["fever"] == 5
    assert player.conditions["food_poisoning"] == 6

    add_items(player.carried, "jasmine tea", 1)
    start_action(world, "Alice", "drink")
    run_minutes(world, 3)

    assert player.needs["stress"] == 18
    assert player.needs["morale"] == 48

    add_items(player.carried, "coffee", 1)
    start_action(world, "Alice", "drink")
    run_minutes(world, 3)

    assert player.needs["fatigue"] == 51
    assert player.conditions["caffeine"] == 18


def test_nipa_and_coffee_processing_chain_has_direct_actions():
    world = new_world()
    player = join_player(world, "Alice")
    world.locations["mangrove forest"].discovered = True
    player.location = "mangrove forest"
    add_items(player.carried, "sharp stone", 1)

    assert "cut nipa fruit" in available_actions(world, "Alice")
    start_action(world, "Alice", "cut nipa fruit")
    run_minutes(world, 15)
    assert count_item(player.carried, "nipa fruit") == 1

    assert "extract nipa seeds" in available_actions(world, "Alice")
    start_action(world, "Alice", "extract nipa seeds")
    run_minutes(world, 30)
    assert count_item(player.carried, "nipa seeds") == 4
    assert count_item(player.carried, "sharp stone") == 1

    player.location = "jungle highlands"
    world.locations["jungle highlands"].discovered = True
    assert "harvest coffee berries" in available_actions(world, "Alice")
    start_action(world, "Alice", "harvest coffee berries")
    run_minutes(world, 30)
    assert 2 <= count_item(player.carried, "coffee berries") <= 3

    assert "extract coffee beans" in available_actions(world, "Alice")
    start_action(world, "Alice", "extract coffee beans")
    run_minutes(world, 15)
    assert count_item(player.carried, "coffee beans") >= 2

    world.locations["jungle highlands"].placed.append(PlacedObject("fire", fuel=1, active=True))
    assert "roast coffee beans" in available_actions(world, "Alice")
    start_action(world, "Alice", "roast coffee beans")
    run_minutes(world, 15)
    assert count_item(player.carried, "roasted coffee beans") == 1

    add_items(player.carried, "clean water", 1)
    assert "brew coffee" in available_actions(world, "Alice")
    start_action(world, "Alice", "brew coffee")
    run_minutes(world, 15)
    assert count_item(player.carried, "coffee") == 1


def test_sago_palm_chain_uses_concrete_actions_and_scaled_wiki_timing():
    world = new_world(seed=7)
    player = join_player(world, "Alice")
    player.location = "wetlands"
    wetlands = world.locations["wetlands"]
    wetlands.discovered = True

    assert "cut sago palm" not in available_actions(world, "Alice")

    add_items(player.carried, "sharp stone", 1)
    add_items(player.carried, "long stick", 1)
    add_items(player.carried, "fiber cord", 1)
    start_action(world, "Alice", "craft stone axe")
    run_minutes(world, 45)

    assert count_item(player.carried, "stone axe") == 1
    assert count_item(player.carried, "sharp stone") == 0

    player.needs["fatigue"] = 0
    player.conditions["hand_damage"] = 0
    assert "cut sago palm" in available_actions(world, "Alice")
    start_action(world, "Alice", "cut sago palm")
    run_minutes(world, 60)

    assert wetlands.resources["sago palm"]["qty"] == 1
    assert count_item(player.carried, "felled sago palm") == 1
    assert 12 <= count_item(player.carried, "palm fronds") <= 24
    assert count_item(player.carried, "sago seeds") == 1
    assert player.needs["fatigue"] >= 25
    assert player.conditions["hand_damage"] == 8

    start_action(world, "Alice", "split sago log")
    run_minutes(world, 60)

    assert count_item(player.carried, "felled sago palm") == 0
    assert count_item(player.carried, "sago pith section") == 16
    assert count_item(player.carried, "stone axe") == 1
    assert player.conditions["hand_damage"] == 16

    add_items(player.carried, "sharp stone", 1)
    start_action(world, "Alice", "scrape sago pith")
    run_minutes(world, 15)

    assert count_item(player.carried, "sago pith section") == 15
    assert count_item(player.carried, "sago sawdust") == 1
    assert count_item(player.carried, "sharp stone") == 1

    add_items(player.carried, "clean water", 1)
    start_action(world, "Alice", "soak sago sawdust")
    run_minutes(world, 15)

    assert count_item(player.carried, "sago sawdust") == 0
    assert count_item(player.carried, "clean water") == 0
    assert count_item(player.carried, "soaked sago") == 1

    start_action(world, "Alice", "grind soaked sago")
    run_minutes(world, 15)
    assert count_item(player.carried, "sago pulp") == 1

    start_action(world, "Alice", "dry sago pulp")
    run_minutes(world, 15)
    assert count_item(player.carried, "sago pulp") == 0
    assert world.processes[0].kind == "drying"
    assert world.processes[0].remaining_minutes == 24 * 60 - 15

    run_minutes(world, 24 * 60)
    assert count_item(wetlands.ground, "sago flour") == 2

    start_action(world, "Alice", "pick up", {"item": "sago flour"})
    run_minutes(world, 3)
    wetlands.placed.append(PlacedObject("fire", fuel=1, active=True))
    assert "cook sago flatbread" in available_actions(world, "Alice")
    start_action(world, "Alice", "cook sago flatbread")
    run_minutes(world, 30)

    assert count_item(player.carried, "sago flatbread") == 1
    assert count_item(wetlands.ground, "sago flour") == 1


def test_sago_food_effects_scale_wiki_stats_to_normalized_model():
    world = new_world()
    player = join_player(world, "Alice")

    assert FOOD_VALUES["soaked sago"] == 25
    assert FOOD_VALUES["sago pulp"] == 10
    assert FOOD_VALUES["sago flour"] == 20
    assert FOOD_VALUES["sago flatbread"] == 20
    assert FOOD_SATURATION_VALUES["soaked sago"] == 35
    assert FOOD_SATURATION_VALUES["sago pulp"] == 30
    assert FOOD_SATURATION_VALUES["sago flour"] == 30
    assert FOOD_SATURATION_VALUES["sago flatbread"] == 40

    player.needs.update({"hunger": 80, "thirst": 60, "morale": 50, "stress": 50})
    player.conditions["filth"] = 0
    player.stats.update({"vegetable_appetite": 100, "sago_appetite": 100})
    add_items(player.carried, "soaked sago", 1)
    start_action(world, "Alice", "eat")
    run_minutes(world, 3)

    assert player.needs["hunger"] == 55
    assert player.needs["thirst"] == 21
    assert player.needs["morale"] == 40
    assert player.conditions["food_poisoning"] == 24
    assert player.conditions["filth"] == 2
    assert player.stats["vegetable_appetite"] == 65
    assert player.stats["sago_appetite"] == 100

    player.needs.update({"hunger": 80, "thirst": 60, "morale": 50, "stress": 50})
    player.conditions.update({"filth": 0, "food_poisoning": 0})
    player.stats["sago_appetite"] = 100
    add_items(player.carried, "sago flatbread", 1)
    start_action(world, "Alice", "eat")
    run_minutes(world, 3)

    assert player.needs["hunger"] == 61
    assert player.needs["thirst"] == 62
    assert player.needs["stress"] == 40
    assert player.needs["morale"] == 51
    assert player.conditions["filth"] == 3
    assert player.stats["sago_appetite"] == 60


def test_mud_clay_and_salt_bed_loop_uses_direct_wiki_scaled_actions():
    world = new_world(seed=11)
    player = join_player(world, "Alice")
    player.location = "mangrove forest"
    loc = world.locations["mangrove forest"]
    loc.discovered = True

    assert RESOURCE_HARVESTS["dig up mud"]["resource"] == "mud deposit"
    assert "dig up mud" in available_actions(world, "Alice")
    start_action(world, "Alice", "dig up mud")
    run_minutes(world, 15)

    assert count_item(player.carried, "mud pile") == 3
    assert loc.resources["mud deposit"]["qty"] == 2
    assert player.conditions["filth"] == 20
    assert player.conditions["wetness"] >= 20

    start_action(world, "Alice", "make clay")
    run_minutes(world, 30)

    assert count_item(player.carried, "mud pile") == 2
    assert count_item(player.carried, "clay") == 1
    assert player.conditions["filth"] == 35

    add_items(player.carried, "ash", 1)
    start_action(world, "Alice", "make mud brick")
    run_minutes(world, 15)

    assert count_item(player.carried, "mud brick") == 1
    assert count_item(player.carried, "ash") == 0
    assert player.conditions["filth"] >= 50

    add_items(player.carried, "mud brick", 11)
    add_items(player.carried, "clay", 5)
    assert "build salt bed" in available_actions(world, "Alice")
    start_action(world, "Alice", "build salt bed")
    run_minutes(world, 120)

    bed = next(obj for obj in loc.placed if obj.kind == "salt bed")
    assert bed.data == {"liquid": 0, "salt": 0, "evap_minutes": 0}
    assert count_item(player.carried, "mud brick") == 0
    assert count_item(player.carried, "clay") == 0
    assert player.needs["stress"] == 0
    assert player.needs["morale"] == 60

    assert "collect salt water" in available_actions(world, "Alice")
    start_action(world, "Alice", "collect salt water")
    run_minutes(world, 12)

    assert count_item(player.carried, "salt water") == 1
    assert "fill salt bed" in available_actions(world, "Alice")
    start_action(world, "Alice", "fill salt bed")
    run_minutes(world, 15)

    assert count_item(player.carried, "salt water") == 0
    assert bed.data["liquid"] == 1200
    run_minutes(world, 6 * 60)

    assert bed.data["liquid"] == 0
    assert bed.data["salt"] == 48
    assert "scrape salt" in available_actions(world, "Alice")
    start_action(world, "Alice", "scrape salt")
    run_minutes(world, 15)

    assert count_item(player.carried, "salt") == 1
    assert bed.data["salt"] == 0


def test_dry_puddle_dirt_chain_and_mud_spoilage_are_structured():
    world = new_world(seed=12)
    player = join_player(world, "Alice")
    player.location = "wetlands"
    wetlands = world.locations["wetlands"]
    wetlands.discovered = True

    assert "dig up dirt" in available_actions(world, "Alice")
    start_action(world, "Alice", "dig up dirt")
    run_minutes(world, 15)

    assert count_item(player.carried, "dirt pile") == 3
    assert 0 <= count_item(player.carried, "bugs") <= 3

    start_action(world, "Alice", "crush dirt")
    run_minutes(world, 30)
    assert count_item(player.carried, "fine dirt") == 1

    add_items(player.carried, "unsafe water", 1)
    start_action(world, "Alice", "mix clay")
    run_minutes(world, 3)
    assert count_item(player.carried, "clay") == 1

    add_items(wetlands.ground, "mud pile", 1)
    run_minutes(world, 1440 + 21 * 60)
    assert count_item(wetlands.ground, "mud pile") == 0
    assert count_item(wetlands.ground, "dirt pile") == 1


def test_salt_preserves_meat_and_fish_with_scaled_sodium_tradeoff():
    world = new_world(seed=13)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    beach.placed.append(PlacedObject("fire", fuel=1, active=True))
    add_items(player.carried, "salt water", 1)

    assert "boil salt water" in available_actions(world, "Alice")
    start_action(world, "Alice", "boil salt water")
    run_minutes(world, 6)
    run_minutes(world, 45)
    assert count_item(beach.ground, "salt") == 1

    add_items(player.carried, "salt", 4)
    add_items(player.carried, "raw fish", 1)
    start_action(world, "Alice", "salt fish")
    run_minutes(world, 30)
    assert world.processes[-1].kind == "curing"
    run_minutes(world, 3 * 1440)
    assert count_item(beach.ground, "salted fish") == 1

    start_action(world, "Alice", "pick up", {"item": "salted fish"})
    run_minutes(world, 3)
    player.needs.update({"hunger": 50, "thirst": 20, "morale": 50})
    player.conditions["sodium_imbalance"] = 0
    start_action(world, "Alice", "eat")
    run_minutes(world, 3)

    assert player.needs["hunger"] == 35
    assert player.needs["thirst"] == 29
    assert player.needs["morale"] == 46
    assert player.conditions["sodium_imbalance"] == 5
    assert FOOD_VALUES["salted fish"] == 15
    assert FOOD_SATURATION_VALUES["salted fish"] == 35


def test_tool_durability_is_preserved_across_actions_and_item_movement():
    world = new_world(seed=14)
    player = join_player(world, "Alice")
    add_items(player.carried, "stones", 1)

    start_action(world, "Alice", "craft sharp stone")
    run_minutes(world, 24)

    sharp_stone = next(stack for stack in player.carried if stack.item == "sharp stone")
    assert sharp_stone.data == {"durability": TOOL_DURABILITY["sharp stone"], "max_durability": TOOL_DURABILITY["sharp stone"]}

    add_items(player.carried, "aloe vera leaf", 2)
    start_action(world, "Alice", "make aloe gel")
    run_minutes(world, 30)

    sharp_stone = next(stack for stack in player.carried if stack.item == "sharp stone")
    assert sharp_stone.data["durability"] == TOOL_DURABILITY["sharp stone"] - 4

    start_action(world, "Alice", "drop", {"item": "sharp stone"})
    run_minutes(world, 3)
    ground_tool = next(stack for stack in world.locations["beach"].ground if stack.item == "sharp stone")
    assert ground_tool.data["durability"] == TOOL_DURABILITY["sharp stone"] - 4

    start_action(world, "Alice", "pick up", {"item": "sharp stone"})
    run_minutes(world, 3)
    carried_tool = next(stack for stack in player.carried if stack.item == "sharp stone")
    assert carried_tool.data["durability"] == TOOL_DURABILITY["sharp stone"] - 4


def test_kiln_and_pottery_are_direct_prerequisite_content():
    world = new_world(seed=17)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    add_items(player.carried, "clay", 1)
    add_items(player.carried, "ash", 1)
    assert "shape clay jar" in available_actions(world, "Alice")
    start_action(world, "Alice", "shape clay jar")
    run_minutes(world, 45)

    assert count_item(player.carried, "unfired clay jar") == 1

    add_items(player.carried, "mud brick", 20)
    add_items(player.carried, "sticks", 2)
    assert "build kiln" in available_actions(world, "Alice")
    start_action(world, "Alice", "build kiln")
    run_minutes(world, 180)

    kiln = next(obj for obj in beach.placed if obj.kind == "kiln")
    assert kiln.active is False
    assert kiln.data["fuel"] == 0
    assert "fire clay jar" not in available_actions(world, "Alice")

    add_items(player.carried, "wood", 4)
    for _ in range(4):
        assert "fuel kiln" in available_actions(world, "Alice")
        start_action(world, "Alice", "fuel kiln")
        run_minutes(world, 6)
    assert kiln.data["fuel"] == 96

    beach.placed.append(PlacedObject("fire", fuel=1, active=True))
    assert "light kiln" in available_actions(world, "Alice")
    start_action(world, "Alice", "light kiln")
    run_minutes(world, 15)
    assert kiln.active is True

    run_minutes(world, 1125)
    assert kiln.data["temperature"] >= 600
    assert "fire clay jar" in available_actions(world, "Alice")
    start_action(world, "Alice", "fire clay jar")
    run_minutes(world, 15)

    assert world.processes[-1].kind == "firing"
    run_minutes(world, 180)

    fired_jar = next(stack for stack in beach.ground if stack.item == "clay jar")
    assert fired_jar.data == {"liquid_capacity": 150, "sealed": 1}


def test_advanced_kiln_forge_copper_and_stone_hut_extend_late_construction():
    world = new_world(seed=24)
    player = join_player(world, "Alice")
    rocks = world.locations["rocks"]
    rocks.discovered = True
    player.location = "rocks"

    add_items(player.carried, "heavy stone", 1)
    for _ in range(3):
        assert "mine copper ore" in available_actions(world, "Alice")
        start_action(world, "Alice", "mine copper ore")
        run_minutes(world, 60)

    assert count_item(player.carried, "copper ore") == 3
    assert "copper vein" not in rocks.location_cards
    assert "mine copper ore" not in available_actions(world, "Alice")
    assert player.conditions["hand_damage"] == 75

    add_items(player.carried, "mud brick", 20)
    add_items(player.carried, "mortar", 14)
    add_items(player.carried, "clay", 20)
    add_items(player.carried, "sand", 28)
    assert "build advanced kiln" in available_actions(world, "Alice")
    start_action(world, "Alice", "build advanced kiln")
    run_minutes(world, 60)

    advanced_kiln = next(obj for obj in rocks.placed if obj.kind == "advanced kiln")
    assert advanced_kiln.data["max_temperature"] == 1200
    assert player.skills["crafting"] >= 5
    assert "build advanced kiln" not in available_actions(world, "Alice")

    add_items(player.carried, "mud brick", 12)
    add_items(player.carried, "mortar", 8)
    add_items(player.carried, "clay", 12)
    add_items(player.carried, "sand", 16)
    assert "build forge" in available_actions(world, "Alice")
    start_action(world, "Alice", "build forge")
    run_minutes(world, 60)

    forge = next(obj for obj in rocks.placed if obj.kind == "forge")
    assert forge.data["max_temperature"] == 1800
    rocks.placed.remove(advanced_kiln)

    add_items(player.carried, "wood", 4)
    for _ in range(4):
        assert "fuel kiln" in available_actions(world, "Alice")
        start_action(world, "Alice", "fuel kiln")
        run_minutes(world, 6)
    rocks.placed.append(PlacedObject("fire", fuel=1, active=True))
    start_action(world, "Alice", "light kiln")
    run_minutes(world, 15)

    assert forge.active is True
    run_minutes(world, 690)
    assert forge.data["temperature"] >= 1100
    assert "smelt copper" in available_actions(world, "Alice")
    start_action(world, "Alice", "smelt copper")
    run_minutes(world, 15)
    assert world.processes[-1].kind == "smelting"
    run_minutes(world, 120)

    assert count_item(rocks.ground, "copper") == 1

    add_items(player.carried, "heavy stone", 40)
    add_items(player.carried, "mortar", 35)
    add_items(player.carried, "stones", 34)
    before_morale = player.needs["morale"]
    assert "build stone hut" in available_actions(world, "Alice")
    start_action(world, "Alice", "build stone hut")
    run_minutes(world, 630)

    assert any(obj.kind == "stone hut" for obj in rocks.placed)
    assert player.needs["morale"] > before_morale
    world.weather = "rain"
    stats = world_snapshot(world, "Alice")["players"]["Alice"]["stats"]
    assert stats["rain_protection"] == 100


def test_copper_molds_tools_sheets_and_vessels_extend_metalworking_chain():
    world = new_world(seed=25)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    beach.placed.append(
        PlacedObject(
            "forge",
            active=True,
            data={"fuel": 96, "temperature": 1100, "max_temperature": 1800, "burn_minutes": 0},
        )
    )
    add_items(player.carried, "mud pile", 4)
    add_items(player.carried, "ash", 4)
    add_items(player.carried, "copper", 14)

    mold_actions = {
        "shape knife mold": "knife mold",
        "shape axe mold": "axe mold",
        "shape shovel mold": "shovel mold",
        "shape spear mold": "spear mold",
    }
    for action, output in mold_actions.items():
        assert action in available_actions(world, "Alice")
        start_action(world, "Alice", action)
        run_minutes(world, 45)
        assert count_item(player.carried, output) == 1

    cast_actions = {
        "cast copper knife": "copper knife",
        "cast axe head": "axe head",
        "cast shovel head": "shovel head",
        "cast spear head": "spear head",
    }
    for action, output in cast_actions.items():
        assert action in available_actions(world, "Alice")
        start_action(world, "Alice", action)
        run_minutes(world, 15)
        assert count_item(player.carried, output) == 1

    copper_knife = next(stack for stack in player.carried if stack.item == "copper knife")
    assert copper_knife.data == {"durability": 40, "max_durability": 40}
    axe_head = next(stack for stack in player.carried if stack.item == "axe head")
    spear_head = next(stack for stack in player.carried if stack.item == "spear head")
    assert axe_head.data == {"durability": 150, "max_durability": 150}
    assert spear_head.data == {"durability": 150, "max_durability": 150}

    add_items(player.carried, "wood", 1)
    add_items(player.carried, "long stick", 2)
    add_items(player.carried, "fiber cord", 5)
    add_items(player.carried, "rope", 1)
    start_action(world, "Alice", "craft copper axe")
    run_minutes(world, 120)
    assert next(stack for stack in player.carried if stack.item == "copper axe").data["durability"] == 50

    assert "craft copper shovel" in available_actions(world, "Alice")
    start_action(world, "Alice", "craft copper shovel")
    run_minutes(world, 60)
    assert next(stack for stack in player.carried if stack.item == "copper shovel").data["durability"] == 50
    assert next(stack for stack in player.carried if stack.item == "copper knife").data["durability"] == 35

    start_action(world, "Alice", "craft copper spear")
    run_minutes(world, 60)
    assert next(stack for stack in player.carried if stack.item == "copper spear").data["durability"] == 120

    add_items(player.carried, "copper", 1)
    add_items(player.carried, "heavy stone", 1)
    assert "hammer copper sheet" in available_actions(world, "Alice")
    start_action(world, "Alice", "hammer copper sheet")
    run_minutes(world, 120)
    assert count_item(player.carried, "copper sheet") == 1
    assert player.conditions["hand_damage"] >= 60

    assert "make copper needles" in available_actions(world, "Alice")
    start_action(world, "Alice", "make copper needles")
    run_minutes(world, 90)
    assert count_item(player.carried, "copper needle") == 4
    assert next(stack for stack in player.carried if stack.item == "copper knife").data["durability"] == 31

    add_items(player.carried, "copper sheet", 7)
    add_items(player.carried, "fiber cord", 4)
    start_action(world, "Alice", "craft copper bottle")
    run_minutes(world, 120)
    copper_bottle = next(stack for stack in player.carried if stack.item == "copper bottle")
    assert copper_bottle.data == {"liquid_capacity": 600, "sealed": 1}

    start_action(world, "Alice", "craft copper jar")
    run_minutes(world, 120)
    copper_jar = next(stack for stack in player.carried if stack.item == "copper jar")
    assert copper_jar.data == {"liquid_capacity": 150, "sealed": 1, "cookable": 1}

    beach.placed.append(PlacedObject("fire", fuel=1, active=True))
    add_items(player.carried, "raw fish", 1)
    add_items(player.carried, "coconut meat", 1)
    add_items(player.carried, "seaweed", 1)
    assert "cook coconut fish" in available_actions(world, "Alice")

    player.location = "wetlands"
    wetlands = world.locations["wetlands"]
    wetlands.discovered = True
    add_items(player.carried, "stones", 20)
    add_items(player.carried, "mortar", 12)
    add_items(player.carried, "long stick", 3)
    add_items(player.carried, "fiber cord", 6)
    add_items(player.carried, "rope", 2)
    add_items(player.carried, "clay bowl", 1, data={"liquid_capacity": 300, "sealed": 0})

    assert "build well" in available_actions(world, "Alice")
    start_action(world, "Alice", "build well")
    run_minutes(world, 990)
    assert any(obj.kind == "well" for obj in wetlands.placed)
    assert next(stack for stack in player.carried if stack.item == "copper shovel").data["durability"] == 42


def test_clay_vessels_hold_rain_and_source_water_with_direct_actions():
    world = new_world(seed=18)
    player = join_player(world, "Alice")
    player.needs["thirst"] = 80
    world.weather = "rain"
    add_items(player.carried, "clay bowl", 2, data={"liquid_capacity": 300, "sealed": 0})

    assert "fill vessel" in available_actions(world, "Alice")
    start_action(world, "Alice", "fill vessel")
    run_minutes(world, 3)

    filled_bowl = next(stack for stack in player.carried if stack.data.get("liquid"))
    empty_bowl = next(stack for stack in player.carried if stack.item == "clay bowl" and not stack.data.get("liquid"))
    assert filled_bowl.qty == 1
    assert filled_bowl.data == {"liquid_capacity": 300, "sealed": 0, "liquid_type": "clean water", "liquid": 50}
    assert empty_bowl.qty == 1

    assert "drink from vessel" in available_actions(world, "Alice")
    start_action(world, "Alice", "drink from vessel")
    run_minutes(world, 3)
    assert player.needs["thirst"] == 71
    assert filled_bowl.data == {"liquid_capacity": 300, "sealed": 0, "liquid": 0}

    world.weather = "clear"
    assert "fill vessel" in available_actions(world, "Alice")
    start_action(world, "Alice", "fill vessel")
    run_minutes(world, 3)
    salt_bowl = next(stack for stack in player.carried if stack.data.get("liquid_type") == "salt water")
    assert salt_bowl.data["liquid"] == 300

    assert "empty vessel" in available_actions(world, "Alice")
    start_action(world, "Alice", "empty vessel")
    run_minutes(world, 3)
    assert salt_bowl.data == {"liquid_capacity": 300, "sealed": 0, "liquid": 0}


def test_used_carried_items_move_to_recent_end():
    world = new_world(seed=18)
    player = join_player(world, "Alice")
    world.weather = "rain"
    add_items(player.carried, "clay bowl", 1, data={"liquid_capacity": 300, "sealed": 0})
    add_items(player.carried, "stones", 1)

    start_action(world, "Alice", "fill vessel")
    run_minutes(world, 3)

    assert [stack.item for stack in player.carried] == ["stones", "clay bowl"]
    assert world_snapshot(world, "Alice")["players"]["Alice"]["carried"][-1]["item"] == "clay bowl"


def test_water_reservoir_builds_collects_rain_and_fills_vessels():
    world = new_world(seed=21)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    add_items(player.carried, "mud brick", 36)
    add_items(player.carried, "clay", 6)

    assert "build water reservoir" in available_actions(world, "Alice")
    start_action(world, "Alice", "build water reservoir")
    run_minutes(world, 180)

    reservoir = next(obj for obj in beach.placed if obj.kind == "water reservoir")
    assert reservoir.data["capacity"] == 12000
    assert reservoir.data["liquid"] == 0
    assert count_item(player.carried, "mud brick") == 0

    world.weather = "rain"
    update_world_processes(world, 15)
    assert reservoir.data["liquid"] == 50

    update_world_processes(world, 15)
    assert reservoir.data["liquid"] == 100

    add_items(player.carried, "clay jar", 1, data={"liquid_capacity": 150, "sealed": 1})
    assert "fill vessel" in available_actions(world, "Alice")
    start_action(world, "Alice", "fill vessel")
    run_minutes(world, 3)

    jar = next(stack for stack in player.carried if stack.item == "clay jar")
    assert jar.data == {"liquid_capacity": 150, "sealed": 1, "liquid_type": "clean water", "liquid": 100}
    assert reservoir.data["liquid"] == 0


def test_well_materials_quicklime_mortar_and_rope_extend_construction_chain():
    world = new_world(seed=22)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    add_items(player.carried, "fiber cord", 3)
    assert "weave rope" in available_actions(world, "Alice")
    start_action(world, "Alice", "weave rope")
    run_minutes(world, 60)
    assert count_item(player.carried, "rope") == 1

    add_items(player.carried, "sharp stone", 1)
    add_items(player.carried, "long stick", 1)
    add_items(player.carried, "fiber cord", 1)
    assert "craft digging stick" in available_actions(world, "Alice")
    start_action(world, "Alice", "craft digging stick")
    run_minutes(world, 30)
    digging_stick = next(stack for stack in player.carried if stack.item == "digging stick")
    assert digging_stick.data == {"durability": 16, "max_durability": 16}

    beach.placed.append(PlacedObject("kiln", active=True, data={"fuel": 96, "temperature": 600, "burn_minutes": 0}))
    add_items(player.carried, "pretty seashells", 2)
    assert "make quicklime" in available_actions(world, "Alice")
    start_action(world, "Alice", "make quicklime")
    run_minutes(world, 15)
    assert world.processes[-1].kind == "calcining"
    run_minutes(world, 240)
    assert count_item(beach.ground, "quicklime") == 2

    start_action(world, "Alice", "pick up", {"item": "quicklime"})
    run_minutes(world, 3)
    assert "collect sand" in available_actions(world, "Alice")
    start_action(world, "Alice", "collect sand")
    run_minutes(world, 6)

    add_items(player.carried, "clean water", 1)
    add_items(player.carried, "heavy stone", 1)
    assert "mix mortar" in available_actions(world, "Alice")
    start_action(world, "Alice", "mix mortar")
    run_minutes(world, 45)

    assert count_item(player.carried, "mortar") == 4


def test_palm_weave_baskets_and_storage_chests_are_concrete_storage_content():
    world = new_world(seed=31)
    player = join_player(world, "Alice")

    add_items(player.carried, "sharp stone", 1, data={"durability": 40, "max_durability": 40})
    assert "cut palm fronds" in available_actions(world, "Alice")
    start_action(world, "Alice", "cut palm fronds")
    run_minutes(world, 30)
    assert world.locations["beach"].resources["palm fronds"]["qty"] == 1
    assert 4 <= count_item(player.carried, "palm fronds") <= 8

    start_action(world, "Alice", "weave palm fronds")
    run_minutes(world, 45)
    assert count_item(player.carried, "palm weave") == 1

    add_items(player.carried, "palm weave", 5)
    add_items(player.carried, "palm fronds", 4)
    assert "craft woven basket" in available_actions(world, "Alice")
    start_action(world, "Alice", "craft woven basket")
    run_minutes(world, 120)
    basket = next(stack for stack in player.carried if stack.item == "basket")
    assert basket.data == {"storage_capacity": 1000, "slots": 4, "weight_reduction": 1000}

    assert "place basket" in available_actions(world, "Alice")
    start_action(world, "Alice", "place basket")
    run_minutes(world, 3)
    placed_basket = next(obj for obj in world.locations["beach"].placed if obj.kind == "basket")
    assert placed_basket.data["storage_capacity"] == 1000
    assert count_item(player.carried, "basket") == 0

    add_items(player.carried, "basket", 1, data={"storage_capacity": 1000, "slots": 4, "weight_reduction": 1000})
    add_items(player.carried, "rope", 1)
    assert "add rope to basket" in available_actions(world, "Alice")
    start_action(world, "Alice", "add rope to basket")
    run_minutes(world, 30)
    backpack = next(stack for stack in player.carried if stack.item == "woven backpack")
    assert backpack.data["equipped_weight_reduction"] == 250

    assert "detach rope from woven backpack" in available_actions(world, "Alice")
    start_action(world, "Alice", "detach rope from woven backpack")
    run_minutes(world, 15)
    assert count_item(player.carried, "basket") == 1
    assert count_item(player.carried, "rope") == 1

    add_items(player.carried, "long stick", 6)
    add_items(player.carried, "fiber cord", 10)
    add_items(player.carried, "palm weave", 6)
    add_items(player.carried, "stone axe", 1, data={"durability": 100, "max_durability": 100})
    assert "build storage chest" in available_actions(world, "Alice")
    start_action(world, "Alice", "build storage chest")
    run_minutes(world, 120)
    chest = next(obj for obj in world.locations["beach"].placed if obj.kind == "storage chest")
    assert chest.data == {"storage_capacity": 4000, "slots": 1, "weight_reduction": 4000}

    add_items(player.carried, "long stick", 8)
    add_items(player.carried, "fiber cord", 10)
    add_items(player.carried, "palm weave", 10)
    add_items(player.carried, "clay", 8)
    add_items(player.carried, "rope", 2)
    assert "build supply chest" in available_actions(world, "Alice")
    start_action(world, "Alice", "build supply chest")
    run_minutes(world, 180)
    supply = next(obj for obj in world.locations["beach"].placed if obj.kind == "supply chest")
    assert supply.data["storage_capacity"] == 3000
    assert supply.data["durability"] == 480


def test_carried_containers_use_slots_capacity_and_reduce_effective_load():
    world = new_world(seed=33)
    player = join_player(world, "Alice")
    basket_data = {"storage_capacity": 1000, "slots": 4, "weight_reduction": 1000}
    add_items(player.carried, "basket", 1, data=basket_data)
    add_items(player.carried, "stones", 4)

    before = world_snapshot(world, "Alice")["players"]["Alice"]["carrying"]
    assert before["effective_weight"] == 900
    assert "pack" in available_actions(world, "Alice")

    start_action(world, "Alice", "pack", {"item": "stones", "qty": 4})
    run_minutes(world, 3)

    basket = next(stack for stack in player.carried if stack.item == "basket")
    assert count_item(player.carried, "stones") == 0
    assert basket.data["contents"][0]["item"] == "stones"
    assert basket.data["contents"][0]["qty"] == 4

    after = world_snapshot(world, "Alice")["players"]["Alice"]["carrying"]
    assert after["packed_weight"] == 400
    assert after["relief"] == 400
    assert after["effective_weight"] == 500
    assert "unpack" in available_actions(world, "Alice")

    start_action(world, "Alice", "unpack", {"item": "stones", "qty": 2})
    run_minutes(world, 3)

    assert count_item(player.carried, "stones") == 2
    assert basket.data["contents"][0]["qty"] == 2

    start_action(world, "Alice", "pack", {"item": "stones", "qty": 2})
    run_minutes(world, 3)
    for item in ("leaves", "fiber cord", "sticks"):
        add_items(player.carried, item, 1)
        start_action(world, "Alice", "pack", {"item": item})
        run_minutes(world, 3)
    add_items(player.carried, "lemongrass", 1)

    assert len(basket.data["contents"]) == 4
    assert "pack" not in available_actions(world, "Alice")
    try:
        start_action(world, "Alice", "pack", {"item": "lemongrass"})
    except ValueError as exc:
        assert "action unavailable" in str(exc)
    else:
        raise AssertionError("full basket slot limit should block packing another item")


def test_placed_storage_enforces_weight_and_can_be_carried_with_contents():
    world = new_world(seed=34)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    beach.placed.append(
        PlacedObject(
            "basket",
            active=True,
            data={"storage_capacity": 1000, "slots": 4, "weight_reduction": 1000},
        )
    )
    add_items(player.carried, "stones", 10)

    assert "store" in available_actions(world, "Alice")
    start_action(world, "Alice", "store", {"item": "stones", "qty": 10})
    run_minutes(world, 3)

    placed_basket = next(obj for obj in beach.placed if obj.kind == "basket")
    assert count_item(player.carried, "stones") == 0
    assert placed_basket.data["contents"][0]["item"] == "stones"
    assert placed_basket.data["contents"][0]["qty"] == 10

    add_items(player.carried, "sticks", 1)
    assert "store" not in available_actions(world, "Alice")
    try:
        start_action(world, "Alice", "store", {"item": "sticks"})
    except ValueError as exc:
        assert "action unavailable" in str(exc)
    else:
        raise AssertionError("full basket weight capacity should block storing another item")

    start_action(world, "Alice", "retrieve", {"item": "stones", "qty": 2})
    run_minutes(world, 3)

    assert count_item(player.carried, "stones") == 2
    assert placed_basket.data["contents"][0]["qty"] == 8

    start_action(world, "Alice", "pick up", {"item": "basket"})
    run_minutes(world, 3)

    carried_basket = next(stack for stack in player.carried if stack.item == "basket")
    assert carried_basket.data["contents"][0]["qty"] == 8
    assert not any(obj.kind == "basket" for obj in beach.placed)
    load = world_snapshot(world, "Alice")["players"]["Alice"]["carrying"]
    assert load["packed_weight"] == 800
    assert load["effective_weight"] == 750


def test_overburdened_players_keep_inventory_actions_but_lose_travel_work():
    world = new_world(seed=35)
    player = join_player(world, "Alice")
    add_items(player.carried, "log", 3)

    load = world_snapshot(world, "Alice")["players"]["Alice"]["carrying"]
    actions = available_actions(world, "Alice")

    assert load["overburdened"] is True
    assert "explore" not in actions
    assert "gather" not in actions
    assert "drop" in actions


def test_dropped_storage_contents_continue_to_age():
    world = new_world(seed=36)
    join_player(world, "Alice")
    basket = ItemStack(
        "basket",
        data={
            "storage_capacity": 1000,
            "slots": 4,
            "weight_reduction": 1000,
            "contents": [
                ItemStack("raw fish", 1, age_minutes=719, exposed=True).to_dict(),
            ],
        },
    )
    world.locations["beach"].ground.append(basket)

    run_minutes(world, 3)

    assert "contents" not in basket.data
    assert "Raw fish spoiled at beach basket." in world.event_log


def test_shed_mud_hut_and_cellar_extend_shelter_storage_progression():
    world = new_world(seed=32)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]

    add_items(player.carried, "long stick", 12)
    add_items(player.carried, "fiber cord", 12)
    add_items(player.carried, "palm weave", 16)
    add_items(player.carried, "palm fronds", 46)
    assert "build shed" in available_actions(world, "Alice")
    start_action(world, "Alice", "build shed")
    run_minutes(world, 450)

    shed = next(obj for obj in beach.placed if obj.kind == "shed")
    assert shed.data["storage_capacity"] == 15000
    assert shed.data["rain_protection"] == 5
    assert player.skills["crafting"] >= 5
    assert player.needs["morale"] >= 70

    add_items(player.carried, "log", 5)
    add_items(player.carried, "long stick", 17)
    add_items(player.carried, "fiber cord", 22)
    add_items(player.carried, "mud brick", 28)
    add_items(player.carried, "sticks", 35)
    add_items(player.carried, "palm fronds", 60)
    assert "build mud hut" in available_actions(world, "Alice")
    start_action(world, "Alice", "build mud hut")
    run_minutes(world, 810)

    mud_hut = next(obj for obj in beach.placed if obj.kind == "mud hut")
    assert mud_hut.data["storage_capacity"] == 60000
    assert mud_hut.data["perceived_temperature"] == -1

    add_items(player.carried, "stones", 30)
    add_items(player.carried, "mortar", 24)
    add_items(player.carried, "clay", 22)
    add_items(player.carried, "log", 9)
    add_items(player.carried, "dirt pile", 15)
    add_items(player.carried, "fiber cord", 4)
    add_items(player.carried, "leather", 2)
    add_items(player.carried, "copper needle", 1)
    add_items(player.carried, "digging stick", 1, data={"durability": 16, "max_durability": 16})
    assert "build cellar" in available_actions(world, "Alice")
    start_action(world, "Alice", "build cellar")
    run_minutes(world, 1320)

    cellar = next(obj for obj in beach.placed if obj.kind == "cellar")
    assert cellar.data["storage_capacity"] == 30000
    assert cellar.data["cool_storage"] == 1
    assert count_item(beach.ground, "dirt pile") == 16
    digging_stick = next(stack for stack in player.carried if stack.item == "digging stick")
    assert digging_stick.data["durability"] == 8


def test_well_and_cistern_are_direct_water_storage_construction():
    world = new_world(seed=23)
    player = join_player(world, "Alice")
    wetlands = world.locations["wetlands"]
    assert "build well" not in available_actions(world, "Alice")

    player.location = "wetlands"
    wetlands.discovered = True
    add_items(player.carried, "digging stick", 1, data={"durability": 16, "max_durability": 16})
    add_items(player.carried, "stones", 20)
    add_items(player.carried, "mortar", 12)
    add_items(player.carried, "long stick", 3)
    add_items(player.carried, "fiber cord", 6)
    add_items(player.carried, "rope", 2)
    add_items(player.carried, "clay bowl", 1, data={"liquid_capacity": 300, "sealed": 0})

    assert "build well" in available_actions(world, "Alice")
    start_action(world, "Alice", "build well")
    run_minutes(world, 990)

    well = next(obj for obj in wetlands.placed if obj.kind == "well")
    assert well.data["capacity"] == 6000
    assert well.data["liquid"] == 0
    assert count_item(wetlands.ground, "dirt pile") == 10
    digging_stick = next(stack for stack in player.carried if stack.item == "digging stick")
    assert digging_stick.data["durability"] == 8

    world.weather = "clear"
    update_world_processes(world, 15)
    assert well.data["liquid"] == 4
    world.weather = "rain"
    update_world_processes(world, 15)
    assert well.data["liquid"] == 58

    add_items(player.carried, "clay jar", 1, data={"liquid_capacity": 150, "sealed": 1})
    world.weather = "clear"
    assert "fill vessel" in available_actions(world, "Alice")
    start_action(world, "Alice", "fill vessel")
    run_minutes(world, 3)
    jar = next(stack for stack in player.carried if stack.item == "clay jar")
    assert jar.data == {"liquid_capacity": 150, "sealed": 1, "liquid_type": "unsafe water", "liquid": 58}
    assert well.data["liquid"] == 0

    add_items(player.carried, "digging stick", 1, data={"durability": 16, "max_durability": 16})
    add_items(player.carried, "stones", 40)
    add_items(player.carried, "mortar", 24)
    add_items(player.carried, "quicklime", 12)
    add_items(player.carried, "clay vase", 3, data={"liquid_capacity": 1200, "sealed": 0})
    add_items(player.carried, "long stick", 3)
    add_items(player.carried, "fiber cord", 6)
    add_items(player.carried, "rope", 2)
    add_items(player.carried, "clay bowl", 1, data={"liquid_capacity": 300, "sealed": 0})

    assert "build cistern" in available_actions(world, "Alice")
    start_action(world, "Alice", "build cistern")
    run_minutes(world, 1560)

    cistern = next(obj for obj in wetlands.placed if obj.kind == "cistern")
    assert cistern.data["capacity"] == 24000
    world.weather = "rain"
    update_world_processes(world, 15)
    assert cistern.data["liquid"] == 50

    add_items(player.carried, "clay bowl", 1, data={"liquid_capacity": 300, "sealed": 0})
    start_action(world, "Alice", "fill vessel")
    run_minutes(world, 3)
    bowl = next(stack for stack in player.carried if stack.item == "clay bowl" and stack.data.get("liquid_type") == "clean water")
    assert bowl.data["liquid"] == 50
    assert cistern.data["liquid"] == 0


def test_cooking_pot_meals_use_pot_as_tool_and_apply_meal_effects():
    world = new_world(seed=19)
    player = join_player(world, "Alice")
    beach = world.locations["beach"]
    beach.placed.append(PlacedObject("fire", fuel=1, active=True))
    add_items(player.carried, "cooking pot", 1, data={"liquid_capacity": 600, "sealed": 1, "cookable": 1})
    add_items(player.carried, "raw fish", 1)
    add_items(player.carried, "coconut meat", 1)
    add_items(player.carried, "seaweed", 1)

    assert "cook coconut fish" in available_actions(world, "Alice")
    start_action(world, "Alice", "cook coconut fish")
    run_minutes(world, 15)

    assert count_item(player.carried, "cooking pot") == 1
    assert count_item(player.carried, "raw fish") == 0
    assert world.processes[-1].kind == "cooking"
    assert world.processes[-1].output == "coconut fish"

    run_minutes(world, 60)
    assert count_item(beach.ground, "coconut fish") == 1

    start_action(world, "Alice", "pick up", {"item": "coconut fish"})
    run_minutes(world, 3)
    player.needs.update({"hunger": 80, "thirst": 80, "stress": 20, "morale": 50})

    start_action(world, "Alice", "eat")
    run_minutes(world, 3)

    assert player.needs["hunger"] == 35
    assert player.needs["thirst"] == 59
    assert player.needs["stress"] == 10
    assert player.needs["morale"] == 65
    assert player.stats["fish_appetite"] == 72
    assert player.stats["coconut_appetite"] == 70
