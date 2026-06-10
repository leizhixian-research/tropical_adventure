from tropical_adventure.client import (
    COMMAND_HELP_VISIBLE_MATCHES,
    CommandMenuState,
    command_choices,
    command_input_key_effect,
    command_to_message,
    format_event_log,
    action_feedback_event,
    format_inventory_panel,
    format_players_panel,
    format_world_panel,
    should_focus_command_input,
    ui_text,
)
from tropical_adventure.content import RAFT_EVENT_PASSING_SHIP, RAFT_RESCUE_DISTANCE


def test_player_panel_sorts_normalized_stats_low_to_high_and_colors_urgency():
    snapshot = {
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "location": "beach",
                "stats": {
                    "health": 100,
                    "hydration": 15,
                    "stamina": 20,
                    "morale": 55,
                    "calm": 19,
                    "food_poisoning_recovery": 18,
                    "coconut_appetite": 45,
                },
            },
            "Bob": {
                "name": "Bob",
                "connected": True,
                "location": "beach",
                "stats": {"health": 1, "hydration": 1, "stamina": 1},
            },
        }
    }

    panel = format_players_panel(snapshot, player_name="Alice", lang="en")
    chinese_panel = format_players_panel(snapshot, player_name="Alice", lang="zh")

    assert (
        panel.index("hydration")
        < panel.index("food poisoning recovery")
        < panel.index("calm")
        < panel.index("stamina")
        < panel.index("coconut appetite")
        < panel.index("morale")
    )
    assert "[red] 15" in panel
    assert "[red] 18" in panel
    assert "[red] 19" in panel
    assert "[yellow] 20" in panel
    assert "[yellow] 45" in panel
    assert "[green] 55" in panel
    assert "Alice" in panel
    assert "Bob" not in panel
    assert "水分" in chinese_panel
    assert "体力" in chinese_panel
    assert "食物中毒恢复" in chinese_panel
    assert "椰子食欲" in chinese_panel


def test_outcomes_and_player_status_render_in_english_and_chinese():
    snapshot = {
        "day": 7,
        "minute": 14 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "outcome": {
            "kind": "win",
            "player": "Alice",
            "reason": "rescued by passing ship",
            "day": 7,
            "minute": 14 * 60,
        },
        "raft": {
            "distance": 672,
            "rescue_distance": RAFT_RESCUE_DISTANCE,
            "event": RAFT_EVENT_PASSING_SHIP,
            "event_remaining_minutes": 45,
            "signal_progress": 60,
            "missed_ships": 0,
        },
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "status": "escaped",
                "location": "raft",
                "stats": {"health": 75, "hydration": 60},
            },
        },
        "locations": {
            "raft": {
                "features": ["sea"],
                "location_cards": [],
                "resources": {},
                "ground": [],
                "placed": [],
            },
        },
    }

    world_en = format_world_panel(snapshot, "Alice", "en")
    world_zh = format_world_panel(snapshot, "Alice", "zh")
    assert "Alice (escaped) @ raft" in format_players_panel(snapshot, "Alice", "en")
    assert "Outcome: Victory — Alice: rescued by passing ship" in world_en
    assert f"Raft voyage: 672/{RAFT_RESCUE_DISTANCE}" in world_en
    assert "Passing ship: signal 60/100, 45m left" in world_en
    assert "Alice (已逃离) @ 木筏" in format_players_panel(snapshot, "Alice", "zh")
    assert "结局：胜利 — Alice：被过往船只救起" in world_zh
    assert f"木筏航程：672/{RAFT_RESCUE_DISTANCE}" in world_zh
    assert "过往船只：示意 60/100，剩余 45 分钟" in world_zh
    assert "Alice被船只救起了。" in format_event_log(
        ["Alice was rescued by a ship."],
        "zh",
    )


def test_world_panel_describes_scene_objects_without_duplicate_action_hints():
    snapshot = {
        "day": 2,
        "minute": 9 * 60 + 30,
        "weather": "rain",
        "light": "daylight",
        "paused": False,
        "players": {"Alice": {"name": "Alice", "location": "beach", "carried": [{"item": "coconut", "qty": 2}, {"item": "stones", "qty": 1}]}},
        "locations": {
            "beach": {
                "features": ["sea", "sand", "coconut palms"],
                "resources": {
                    "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
                    "coconut": {"source": "coconut palms", "qty": 2, "capacity": 2, "regen_minutes": 4320, "action": "forage"},
                },
                "ground": [
                    {"item": "sticks", "qty": 3},
                    {"item": "coconut", "qty": 1},
                    {"item": "raw fish", "qty": 1, "age_minutes": 360},
                ],
                "placed": [{"kind": "sand castle", "fuel": 0}, {"kind": "fire", "fuel": 4}],
            },
            "rocks": {"features": ["stone outcrops"], "resources": {}, "ground": [], "placed": []},
        },
    }

    panel = format_world_panel(snapshot, player_name="Alice", lang="en")

    assert "Global" in panel
    assert "Day 2 09:30" in panel
    assert "weather: rain light: daylight paused: False" in panel
    assert "Scene: beach" in panel
    assert "sea — open salt water; unsafe water source: infinite" in panel
    assert "sand — warm pale sand" in panel
    assert "coconut palms — shade and coconuts; coconut: 2/2 available; regrows every 3 days" in panel
    assert "sand castle — a fragile little monument" in panel
    assert "fire(fuel 4) — active fire with fuel 4" in panel
    assert "1 raw fish — half fresh; spoils in 6h; freshness  50 █████░░░░░" in panel
    assert "1 coconut — fresh food and drink" in panel
    assert "3 sticks — dry fuel and building material" in panel
    assert (
        panel.index("1 raw fish — half fresh; spoils in 6h")
        < panel.index("1 coconut — fresh food and drink")
        < panel.index("3 sticks — dry fuel and building material")
    )
    assert "path to rocks — discovered route" in panel
    assert "/pick up" not in panel
    assert "/move" not in panel
    assert "/forage" not in panel
    assert "Inventory" not in panel

    inventory = format_inventory_panel(snapshot, player_name="Alice", lang="en")
    assert inventory.splitlines() == [
        "Inventory",
        "  1 stones — hard stones for tools",
        "  2 coconut — fresh food and drink",
    ]


def test_world_panel_lists_other_players_as_scene_objects_with_public_action_only():
    snapshot = {
        "day": 1,
        "minute": 360,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {
            "Alice": {"name": "Alice", "connected": True, "location": "beach", "stats": {"health": 100}},
            "Bob": {
                "name": "Bob",
                "connected": True,
                "location": "beach",
                "current_action": {"name": "rest", "remaining_minutes": 12, "total_minutes": 30},
            },
            "Cara": {"name": "Cara", "connected": True, "location": "rocks"},
            "Dan": {"name": "Dan", "connected": False, "location": "beach"},
        },
        "locations": {
            "beach": {"features": [], "location_cards": [], "resources": {}, "ground": [], "placed": []},
            "rocks": {"features": [], "location_cards": [], "resources": {}, "ground": [], "placed": []},
        },
    }

    player_panel = format_players_panel(snapshot, "Alice", "en")
    world_en = format_world_panel(snapshot, "Alice", "en")
    world_zh = format_world_panel(snapshot, "Alice", "zh")

    assert "Alice" in player_panel
    assert "Bob" not in player_panel
    assert "Bob — survivor here, resting (12m left)" in world_en
    assert "Bob — 同伴在这里，正在休息，剩余 12 分钟" in world_zh
    assert "Cara" not in world_en
    assert "Dan" not in world_en
    assert "health" not in world_en


def test_event_log_panel_is_fixed_5_line_snapshot_without_scrollbars():
    from tropical_adventure.client import SurvivalApp

    assert "#log" in SurvivalApp.CSS
    log_rule = next(line.strip() for line in SurvivalApp.CSS.splitlines() if line.strip().startswith("#log"))
    assert "#log { height: 7;" in log_rule
    assert "overflow-x" not in log_rule
    assert "overflow-y" not in log_rule


def test_event_log_shows_rotating_spinner_for_ongoing_action_instead_of_started_text():
    events = ["Alice started explore.", "Bob joined"]
    action = {"name": "explore", "remaining_minutes": 12, "total_minutes": 18}

    first = format_event_log(events, lang="en", active_action=action, player_name="Alice", spinner_frame=0)
    second = format_event_log(events, lang="en", active_action=action, player_name="Alice", spinner_frame=1)
    chinese = format_event_log(events, lang="zh", active_action=action, player_name="Alice", spinner_frame=0)

    assert first.splitlines() == ["Bob joined", "⠋ Alice exploring… 12m left"]
    assert second.splitlines() == ["Bob joined", "⠙ Alice exploring… 12m left"]
    assert chinese.splitlines() == ["Bob joined", "⠋ Alice 正在探索… 剩余 12 分钟"]
    assert action_feedback_event({"type": "start_action", "action": "explore"}, player_name="Alice") == {
        "name": "explore",
        "remaining_minutes": 18,
        "total_minutes": 18,
    }
    assert action_feedback_event({"type": "inspect"}, player_name="Alice") is None


def test_format_event_log_shows_only_last_5_events_without_duplicates():
    events = [f"event {i}" for i in range(12)]

    rendered = format_event_log(events)

    assert rendered.splitlines() == [f"event {i}" for i in range(7, 12)]


def test_format_event_log_localizes_common_game_events_to_chinese():
    events = [
        "Day 2 begins.",
        "Alice started forage.",
        "Alice completed forage.",
        "Alice discovered rocks.",
        "Raw fish spoiled at beach.",
    ]

    rendered = format_event_log(events, lang="zh")

    assert rendered.splitlines() == [
        "第 2 天开始了。",
        "Alice 开始觅食。",
        "Alice 完成觅食。",
        "Alice 发现了岩石。",
        "生鱼在海滩腐坏了。",
    ]


def test_chinese_world_panel_localizes_objects_and_command_object_aliases_are_accepted():
    snapshot = {
        "day": 1,
        "minute": 360,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "available_actions": ["move", "pick up"],
        "players": {"Alice": {"name": "Alice", "location": "beach", "carried": [{"item": "coconut", "qty": 1}]}},
        "locations": {
            "beach": {"features": ["sea", "sand"], "resources": {}, "ground": [{"item": "sticks", "qty": 2}], "placed": []},
            "rocks": {"features": ["stone outcrops"], "resources": {}, "ground": [], "placed": []},
        },
    }

    panel = format_world_panel(snapshot, "Alice", "zh")

    assert "现场: 海滩" in panel
    assert "海 — 开阔的咸水" in panel
    assert "沙子 — 温暖的浅色沙地" in panel
    assert "2 树枝 — 干燥的燃料和建材" in panel
    assert "通往 岩石 的路 — 已发现的路线" in panel
    assert "/swim" not in panel
    assert "/pick up" not in panel
    assert "1 椰子" in format_inventory_panel(snapshot, "Alice", "zh")
    rich_snapshot = {
        **snapshot,
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "beach",
                "carried": [
                    {"item": "clean water", "qty": 1},
                    {"item": "raw fish", "qty": 1},
                    {"item": "cooked fish", "qty": 1},
                    {"item": "bandage leaves", "qty": 2},
                ],
            }
        },
        "locations": {
            "beach": {
                "features": [],
                "resources": {},
                "ground": [{"item": "ash", "qty": 1}, {"item": "charcoal", "qty": 1}],
                "placed": [],
            }
        },
    }
    rich_panel = format_world_panel(rich_snapshot, "Alice", "zh")
    rich_inventory = format_inventory_panel(rich_snapshot, "Alice", "zh")
    assert "净水" in rich_inventory
    assert "生鱼" in rich_inventory
    assert "熟鱼" in rich_inventory
    assert "绷带叶" in rich_inventory
    assert "灰烬" in rich_panel
    assert "木炭" in rich_panel
    assert command_to_message("/pick up 树枝", snapshot) == {
        "type": "start_action",
        "action": "pick up",
        "args": {"item": "sticks"},
    }
    assert command_to_message("/move 岩石", snapshot) == {
        "type": "start_action",
        "action": "move",
        "args": {"location": "rocks"},
    }
    assert command_to_message("/drop 绷带叶", snapshot) == {
        "type": "start_action",
        "action": "drop",
        "args": {"item": "bandage leaves"},
    }
    assert command_to_message("/pick up 生鱼", snapshot) == {
        "type": "start_action",
        "action": "pick up",
        "args": {"item": "raw fish"},
    }


def test_survival_app_layout_has_three_top_boxes_log_and_floating_command_menu():
    from tropical_adventure.client import SurvivalApp

    assert "#player-scroll { width: 1fr; height: 1fr;" in SurvivalApp.CSS
    assert "#world-scroll { width: 2fr; height: 1fr;" in SurvivalApp.CSS
    assert "#inventory-scroll { width: 1fr; height: 1fr;" in SurvivalApp.CSS
    assert "#players, #world, #inventory { width: 100%; }" in SurvivalApp.CSS
    assert "#log { height: 7;" in SurvivalApp.CSS
    assert "#command-help { display: none; layer: overlay; dock: bottom;" in SurvivalApp.CSS
    assert "#input { dock: bottom; border: round $accent;" in SurvivalApp.CSS
    assert "#input:focus { border: round $accent;" in SurvivalApp.CSS
    assert SurvivalApp.ENABLE_COMMAND_PALETTE is False
    assert SurvivalApp.BINDINGS == []


def test_command_input_stays_primary_focus_while_panel_scrolling_uses_page_keys():
    assert should_focus_command_input("a") is True
    assert should_focus_command_input("slash") is True
    assert should_focus_command_input("enter") is True
    assert should_focus_command_input("up") is True
    assert should_focus_command_input("down") is True
    assert should_focus_command_input("pageup") is False
    assert should_focus_command_input("pagedown") is False


def test_direct_slash_action_maps_to_start_action():
    snapshot = {"available_actions": ["explore", "craft sharp stone"]}

    assert command_to_message("/explore", snapshot) == {"type": "start_action", "action": "explore", "args": {}}
    assert command_to_message("/craft sharp stone", snapshot) == {
        "type": "start_action",
        "action": "craft sharp stone",
        "args": {},
    }


def test_defined_slash_action_maps_even_when_not_currently_available():
    snapshot = {"available_actions": []}

    assert command_to_message("/cook coconut fish", snapshot) == {
        "type": "start_action",
        "action": "cook coconut fish",
        "args": {},
    }


def test_direct_slash_actions_with_arguments_map_to_start_action_args():
    snapshot = {"available_actions": ["move", "pick up", "drop"]}

    assert command_to_message("/move rocks", snapshot) == {
        "type": "start_action",
        "action": "move",
        "args": {"location": "rocks"},
    }
    assert command_to_message("/pick up coconut", snapshot) == {
        "type": "start_action",
        "action": "pick up",
        "args": {"item": "coconut"},
    }
    assert command_to_message("/pickup coconut", snapshot) == {
        "type": "start_action",
        "action": "pick up",
        "args": {"item": "coconut"},
    }
    assert command_to_message("/drop coconut", snapshot) == {
        "type": "start_action",
        "action": "drop",
        "args": {"item": "coconut"},
    }


def test_slash_choices_include_available_actions_and_client_commands():
    snapshot = {"available_actions": ["explore", "craft sharp stone", "pick up"]}

    choices = command_choices(snapshot)

    assert choices[:3] == ["/explore", "/craft sharp stone", "/pick up <item>"]
    assert "/explore" in choices
    assert "/craft sharp stone" in choices
    assert "/pick up <item>" in choices
    assert "/inspect" in choices
    assert "/pause" in choices
    assert "/exit" in choices
    assert "/action forage" not in choices


def test_slash_menu_preserves_recent_action_order_from_snapshot():
    snapshot = {"available_actions": ["rest", "forage", "explore"]}

    menu = CommandMenuState(command_choices(snapshot))
    menu.update("/")

    assert menu.matches[:3] == ["/rest", "/forage", "/explore"]
    assert menu.selected == "/rest"


def test_slash_choices_use_current_player_location_and_inventory():
    snapshot = {
        "available_actions": ["move", "pick up", "drop"],
        "players": {
            "Alice": {"name": "Alice", "connected": True, "location": "beach", "carried": [{"item": "coconut", "qty": 1}]},
            "Bob": {
                "name": "Bob",
                "connected": True,
                "location": "rocks",
                "carried": [{"item": "stones", "qty": 1}],
                "available_actions": ["move", "pick up", "drop"],
            },
        },
        "locations": {
            "beach": {"ground": [{"item": "coconut", "qty": 1}]},
            "rocks": {"ground": [{"item": "stones", "qty": 2}]},
        },
    }

    choices = command_choices(snapshot, player_name="Bob")

    assert "/drop stones" in choices
    assert "/pick up stones" in choices
    assert "/move beach" in choices
    assert "/drop coconut" not in choices
    assert "/pick up coconut" not in choices


def test_slash_menu_keeps_selection_visible_in_a_sliding_window():
    snapshot = {
        "available_actions": [
            "boil water",
            "build raincatcher",
            "build shelter",
            "cancel",
            "cook fish",
            "craft sharp stone",
            "drink",
            "drop",
            "eat",
            "explore",
            "fish",
            "forage",
            "gather",
            "leisure",
            "move",
            "pick up",
            "rest",
            "start fire",
            "swim",
            "tend fire",
            "treat wound",
            "wash",
        ]
    }

    menu = CommandMenuState(command_choices(snapshot))
    menu.update("/")
    rendered = menu.render(lang="en")

    assert menu.selected == "/boil water"
    assert "/boil water" in rendered
    menu.move_down()
    assert menu.selected == "/build raincatcher"
    menu.move_up()
    assert menu.selected == "/boil water"

    for _ in range(12):
        menu.move_down()
    rendered = menu.render(lang="en")
    assert menu.selected in rendered
    assert "↑" in rendered
    assert "↓" in rendered
    visible_commands = [line for line in rendered.splitlines() if line.startswith(("› ", "  /"))]
    assert len(visible_commands) <= 20
    assert COMMAND_HELP_VISIBLE_MATCHES == 20


def test_command_help_panel_uses_floating_internal_window_not_layout_space():
    from tropical_adventure.client import SurvivalApp

    assert "#command-help" in SurvivalApp.CSS
    assert "display: none; layer: overlay; dock: bottom;" in SurvivalApp.CSS
    assert "margin-bottom: 3; height: 25;" in SurvivalApp.CSS
    assert "Screen { layout: vertical; overflow: hidden; }" in SurvivalApp.CSS


def test_slash_menu_filters_and_completes_placeholders():
    menu = CommandMenuState(["/move <location>", "/pause", "/pick up <item>"])

    menu.update("/p")
    assert menu.matches == ["/pause", "/pick up <item>"]
    assert menu.selected == "/pause"
    menu.move_down()
    assert menu.selected == "/pick up <item>"
    assert menu.completion_value() == "/pick up "


def test_slash_menu_shows_no_match_instead_of_falling_back_to_all_commands():
    menu = CommandMenuState(["/explore", "/forage"])

    menu.update("/zzz")

    assert menu.matches == []
    assert menu.selected is None
    assert "No matching commands" in menu.render(lang="en")


def test_slash_menu_renders_descriptions_for_each_command():
    menu = CommandMenuState(["/explore", "/move <location>", "/save"])
    menu.update("/")
    rendered = menu.render(lang="en")

    assert "/explore" in rendered
    assert "search the current area" in rendered
    assert "/move <location>" in rendered
    assert "travel to a discovered location" in rendered
    assert "/save" in rendered
    assert "save the world" in rendered


def test_slash_menu_renders_chinese_action_descriptions():
    menu = CommandMenuState(["/explore", "/move <location>", "/save"])
    menu.update("/")
    rendered = menu.render(lang="zh")

    assert "/explore" in rendered
    assert "搜索当前区域的新地点" in rendered
    assert "/move <location>" in rendered
    assert "前往已发现地点" in rendered
    assert "/save" in rendered
    assert "保存世界" in rendered


def test_tab_selects_autocompleted_command_but_enter_never_autocompletes():
    menu = CommandMenuState(["/pause", "/pick up <item>"])
    menu.update("/p")
    menu.move_down()

    value, handled = command_input_key_effect(menu, "tab", "/p")
    assert handled is True
    assert value == "/pick up "

    menu.update("/p")
    value, handled = command_input_key_effect(menu, "enter", "/p")
    assert handled is False
    assert value == "/p"


def test_escape_clears_input_and_tab_does_not_change_focus_when_command_menu_visible():
    menu = CommandMenuState(["/pause"])
    menu.update("/")

    value, handled = command_input_key_effect(menu, "escape", "/p")
    assert handled is True
    assert value == ""
    assert menu.render() == ""

    menu.update("/pause")
    value, handled = command_input_key_effect(menu, "tab", "/pause")
    assert handled is True
    assert value == "/pause"


def test_world_panel_shows_all_discovered_locations_not_only_current_location():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {"Alice": {"name": "Alice", "location": "beach"}},
        "locations": {
            "beach": {"features": ["sea"], "resources": {}, "ground": [], "placed": []},
            "rocks": {"features": ["stone outcrops"], "resources": {}, "ground": [{"item": "stones", "qty": 2}], "placed": []},
        },
    }

    panel = format_world_panel(snapshot, player_name="Alice", lang="en")

    assert "Scene: beach" in panel
    assert "sea — open salt water" in panel
    assert "path to rocks — discovered route" in panel


def test_world_panel_describes_new_card_survival_area_features():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {"Alice": {"name": "Alice", "location": "volcano"}},
        "locations": {
            "volcano": {
                "features": ["brimstone vent", "stone outcrops", "hot ground"],
                "resources": {
                    "ash": {"source": "hot ground", "infinite": True, "action": "forage"},
                    "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
                },
                "ground": [],
                "placed": [],
            }
        },
    }

    panel = format_world_panel(snapshot, player_name="Alice", lang="en")

    assert "Scene: volcano" in panel
    assert "brimstone vent" in panel
    assert "sulfurous volcanic vent" in panel
    assert "hot ground" in panel
    assert "ash source: infinite" in panel


def test_world_panel_renders_location_cards_inside_area():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "rocks",
                "available_actions": ["harvest coconuts", "forage tide pool"],
            }
        },
        "locations": {
            "rocks": {
                "features": ["stone outcrops"],
                "location_cards": ["tide pool", "flooded tide pool", "copper vein"],
                "resources": {},
                "ground": [],
                "placed": [],
            }
        },
    }

    panel = format_world_panel(snapshot, player_name="Alice", lang="en")

    assert "Scene: rocks" in panel
    assert "tide pool" in panel
    assert "shallow pools with small fish" in panel
    assert "flooded tide pool" in panel
    assert "green-streaked ore in stone" in panel


def test_full_snapshot_hides_undiscovered_locations_from_scene_and_move_choices():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {"Alice": {"name": "Alice", "location": "beach", "carried": [], "available_actions": ["move"]}},
        "locations": {
            "beach": {
                "name": "beach",
                "discovered": True,
                "features": [],
                "neighbors": ["jungle outskirts"],
                "resources": {},
                "ground": [],
                "placed": [],
            },
            "jungle outskirts": {"name": "jungle outskirts", "discovered": True, "features": [], "resources": {}, "ground": [], "placed": []},
            "rocks": {"name": "rocks", "discovered": False, "features": [], "resources": {}, "ground": [], "placed": []},
        },
    }

    panel = format_world_panel(snapshot, player_name="Alice", lang="en")
    choices = command_choices(snapshot, player_name="Alice")

    assert "path to jungle outskirts — discovered route" in panel
    assert "path to rocks" not in panel
    assert "/move jungle outskirts" in choices
    assert "/move rocks" not in choices
    assert "/move <location>" in choices
    assert command_to_message("/move rocks", snapshot, "Alice") is None
    assert command_to_message("/move jungle outskirts", snapshot, "Alice") == {
        "type": "start_action",
        "action": "move",
        "args": {"location": "jungle outskirts"},
    }


def test_client_ui_text_supports_english_and_chinese():
    assert ui_text("world", "en") == "World"
    assert ui_text("world", "zh") == "世界"
    menu = CommandMenuState(["/explore"])
    menu.update("/")
    assert "命令" in menu.render(lang="zh")
    assert "现场: 海滩" in format_world_panel(
        {
            "day": 1,
            "minute": 360,
            "weather": "clear",
            "light": "daylight",
            "paused": False,
            "players": {"Alice": {"name": "Alice", "location": "beach"}},
            "locations": {"beach": {"features": [], "resources": {}, "ground": [], "placed": []}},
        },
        "Alice",
        "zh",
    )


def test_new_card_survival_content_renders_with_chinese_support():
    snapshot = {
        "day": 1,
        "minute": 360,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "available_actions": [
            "harvest coconuts",
            "harvest aloe vera",
            "brew ginger tea",
            "apply bug repellent",
            "forage tide pool",
            "build fish trap",
            "check snare trap",
        ],
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "rocks",
                "carried": [{"item": "ginger tea", "qty": 1}, {"item": "bug repellent", "qty": 1}],
                "available_actions": [
                    "harvest coconuts",
                    "harvest aloe vera",
                    "brew ginger tea",
                    "apply bug repellent",
                    "forage tide pool",
                    "build fish trap",
                    "check snare trap",
                ],
            }
        },
        "locations": {
            "rocks": {
                "features": ["sand"],
                "location_cards": ["tide pool"],
                "resources": {
                    "aloe vera": {"source": "sand", "qty": 1, "capacity": 1, "regen_minutes": 10080, "action": "harvest aloe vera"}
                },
                "ground": [
                    {"item": "dried fish", "qty": 1},
                    {"item": "cooked meat", "qty": 1},
                    {"item": "nipa seeds", "qty": 4},
                    {"item": "coffee", "qty": 1},
                    {"item": "magic mushrooms", "qty": 1},
                ],
                "placed": [
                    {"kind": "drying rack", "fuel": 0},
                    {"kind": "fish trap", "fuel": 0, "data": {"soak_minutes": 120, "target_minutes": 1500}},
                    {"kind": "snare trap", "fuel": 0, "data": {"ready": 1, "catch": "raw meat"}},
                ],
            }
        },
    }
    menu = CommandMenuState(command_choices(snapshot, "Alice"))
    menu.update("/")

    panel = format_world_panel(snapshot, "Alice", "zh")
    rendered_menu = menu.render(lang="zh")
    log = format_event_log(["Alice started harvest coconuts."], lang="zh")
    process_log = format_event_log(["drying at beach produced dried fish."], lang="zh")

    assert "潮池" in panel
    assert "芦荟：1/1 可用" in panel
    assert "晾晒架" in panel
    assert "捕鱼陷阱" in panel
    assert "120/1500" in panel
    assert "生肉" in panel
    assert "鱼干" in panel
    assert "熟肉" in panel
    assert "水椰籽" in panel
    assert "咖啡" in panel
    assert "迷幻菇" in panel
    assert "姜茶" in format_inventory_panel(snapshot, "Alice", "zh")
    assert "驱虫膏" in format_inventory_panel(snapshot, "Alice", "zh")
    assert "/harvest coconuts" in rendered_menu
    assert "/harvest aloe vera" in rendered_menu
    assert "/brew ginger tea" in rendered_menu
    assert "/build fish trap" in rendered_menu
    assert "爬上棕榈树采下椰子" in rendered_menu
    assert "采下一片含凝胶的芦荟叶" in rendered_menu
    assert "用热水泡姜以缓解恶心并提升免疫" in rendered_menu
    assert "编一个会随时间捕获海产的沿海陷阱" in rendered_menu
    assert "Alice 开始采椰子。" in log
    assert "晾晒在海滩产出了鱼干。" in process_log
    assert command_to_message("/drop 姜茶", snapshot) == {
        "type": "start_action",
        "action": "drop",
        "args": {"item": "ginger tea"},
    }


def test_sago_content_renders_as_direct_scene_actions_with_chinese_support():
    snapshot = {
        "day": 1,
        "minute": 360,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "available_actions": ["cut sago palm", "split sago log", "scrape sago pith", "cook sago flatbread", "drop"],
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "wetlands",
                "carried": [{"item": "sago flatbread", "qty": 1}, {"item": "sago flour", "qty": 2}],
                "available_actions": ["cut sago palm", "split sago log", "scrape sago pith", "cook sago flatbread", "drop"],
            }
        },
        "locations": {
            "wetlands": {
                "features": ["sago palms"],
                "resources": {
                    "sago palm": {
                        "source": "sago palms",
                        "qty": 2,
                        "capacity": 2,
                        "regen_minutes": 20160,
                        "action": "cut sago palm",
                    }
                },
                "ground": [
                    {"item": "sago sawdust", "qty": 1},
                    {"item": "soaked sago", "qty": 1},
                    {"item": "sago pulp", "qty": 1},
                ],
                "placed": [{"kind": "fire", "fuel": 1}],
            }
        },
    }
    menu = CommandMenuState(command_choices(snapshot, "Alice"))
    menu.update("/")

    panel = format_world_panel(snapshot, "Alice", "zh")
    inventory = format_inventory_panel(snapshot, "Alice", "zh")
    rendered_menu = menu.render(lang="zh")

    assert "西米棕榈" in panel
    assert "西米棕榈：2/2 可用" in panel
    assert "西米木屑" in panel
    assert "湿西米" in panel
    assert "西米浆" in panel
    assert "西米薄饼" in inventory
    assert "西米粉" in inventory
    assert "/cut sago palm" in rendered_menu
    assert "/cook sago flatbread" in rendered_menu
    assert "砍倒西米棕榈以取得富含淀粉的髓心" in rendered_menu
    assert "把西米粉烤成饱腹的薄饼" in rendered_menu
    assert command_to_message("/drop 西米薄饼", snapshot, "Alice") == {
        "type": "start_action",
        "action": "drop",
        "args": {"item": "sago flatbread"},
    }


def test_mud_salt_and_item_stats_render_with_chinese_support():
    snapshot = {
        "day": 3,
        "minute": 10 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "available_actions": [
            "dig up mud",
            "make clay",
            "shape clay jar",
            "fill vessel",
            "drink from vessel",
            "cook coconut fish",
            "build salt bed",
            "build water reservoir",
            "build well",
            "build cistern",
            "build advanced kiln",
            "build forge",
            "mine copper ore",
            "smelt copper",
            "build stone hut",
            "fuel kiln",
            "fill salt bed",
            "scrape salt",
            "drop",
        ],
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "mangrove forest",
                "carried": [
                    {"item": "sharp stone", "qty": 1, "data": {"durability": 20, "max_durability": 40}},
                    {
                        "item": "clay jar",
                        "qty": 1,
                        "data": {"liquid_capacity": 150, "sealed": 1, "liquid_type": "clean water", "liquid": 50},
                    },
                    {"item": "coconut fish", "qty": 1, "age_minutes": 240},
                    {"item": "salt", "qty": 4},
                    {"item": "mud brick", "qty": 12},
                    {"item": "clay", "qty": 6},
                    {"item": "salt water", "qty": 1},
                    {"item": "copper ore", "qty": 1},
                    {"item": "copper", "qty": 1},
                ],
                "available_actions": [
                    "dig up mud",
                    "make clay",
                    "shape clay jar",
                    "fill vessel",
                    "drink from vessel",
                    "cook coconut fish",
                    "build salt bed",
                    "build water reservoir",
                    "build well",
                    "build cistern",
                    "build advanced kiln",
                    "build forge",
                    "mine copper ore",
                    "smelt copper",
                    "build stone hut",
                    "fuel kiln",
                    "fill salt bed",
                    "scrape salt",
                    "drop",
                ],
            }
        },
        "locations": {
            "mangrove forest": {
                "features": ["flooded mud"],
                "location_cards": ["mud deposit", "salt bed"],
                "resources": {
                    "mud deposit": {"source": "flooded mud", "qty": 2, "capacity": 3, "action": "dig up mud"}
                },
                "ground": [
                    {"item": "mud pile", "qty": 1, "age_minutes": 900},
                    {"item": "dirt pile", "qty": 2},
                ],
                "placed": [
                    {"kind": "kiln", "fuel": 0, "active": True, "data": {"fuel": 48, "temperature": 600}},
                    {
                        "kind": "advanced kiln",
                        "fuel": 0,
                        "active": True,
                        "data": {"fuel": 48, "temperature": 600, "max_temperature": 1200},
                    },
                    {
                        "kind": "forge",
                        "fuel": 0,
                        "active": False,
                        "data": {"fuel": 24, "temperature": 900, "max_temperature": 1800},
                    },
                    {"kind": "stone hut", "fuel": 0, "active": True, "data": {}},
                    {"kind": "salt bed", "fuel": 0, "data": {"liquid": 4800, "salt": 96}},
                    {
                        "kind": "water reservoir",
                        "fuel": 0,
                        "active": True,
                        "data": {"liquid": 600, "capacity": 12000, "mosquito_protection": 0},
                    },
                    {"kind": "well", "fuel": 0, "active": True, "data": {"liquid": 300, "capacity": 6000}},
                    {"kind": "cistern", "fuel": 0, "active": True, "data": {"liquid": 1200, "capacity": 24000}},
                ],
            }
        },
    }
    menu = CommandMenuState(command_choices(snapshot, "Alice"))
    menu.update("/")

    panel = format_world_panel(snapshot, "Alice", "zh")
    inventory = format_inventory_panel(snapshot, "Alice", "zh")
    rendered_menu = menu.render(lang="zh")
    log = format_event_log(["Alice's sharp stone wore out.", "curing at beach produced salted fish."], lang="zh")

    assert "泥土堆位置卡" in panel
    assert "盐床位置卡" in panel
    assert "泥土堆：2/3 可用" in panel
    assert "盐水  50 █████░░░░░" in panel
    assert "盐   5" in panel
    assert "蓄水池" in panel
    assert "净水 600/12000   5" in panel
    assert "水井" in panel
    assert "不安全的水 300/6000   5" in panel
    assert "水窖" in panel
    assert "净水 1200/24000   5" in panel
    assert "高级窑" in panel
    assert "锻炉" in panel
    assert "石屋" in panel
    assert "温度  66 ██████░░░░" in panel
    assert "泥堆" in panel
    assert "新鲜度" in panel
    assert "耐久  50 █████░░░░░" in inventory
    assert "容量 150" in inventory
    assert "密封" in inventory
    assert "净水 50/150" in inventory
    assert "椰子鱼" in inventory
    assert "泥砖" in inventory
    assert "黏土" in inventory
    assert "盐水" in inventory
    assert "铜矿石" in inventory
    assert "铜" in inventory
    assert "/dig up mud" in rendered_menu
    assert "/shape clay jar" in rendered_menu
    assert "/fill vessel" in rendered_menu
    assert "/cook coconut fish" in rendered_menu
    assert "/build salt bed" in rendered_menu
    assert "/build water reservoir" in rendered_menu
    assert "/build well" in rendered_menu
    assert "/build cistern" in rendered_menu
    assert "/build advanced kiln" in rendered_menu
    assert "/build forge" in rendered_menu
    assert "/mine copper ore" in rendered_menu
    assert "/smelt copper" in rendered_menu
    assert "/build stone hut" in rendered_menu
    assert "从泥堆或干涸水洼挖出可加工的泥" in rendered_menu
    assert "用黏土和灰烬塑成带盖陶罐" in rendered_menu
    assert "用雨水或附近水源装满携带的陶器" in rendered_menu
    assert "用陶锅把鱼、椰子和蔬菜煮成椰子鱼" in rendered_menu
    assert "用泥砖和黏土建造蒸发海水的盐床" in rendered_menu
    assert "用泥砖和黏土建造会接雨的大蓄水池" in rendered_menu
    assert "在湿地挖井并砌边，让它缓慢积蓄不安全的水" in rendered_menu
    assert "建造密封的地下水窖来储存雨水" in rendered_menu
    assert "建造可用于陶器和铜冶炼的高温砂浆窑" in rendered_menu
    assert "建造用于冶炼铜的紧凑高温锻炉" in rendered_menu
    assert "敲开铜矿脉，采出铜矿石" in rendered_menu
    assert "在高温高级窑或锻炉中开始冶炼铜矿石" in rendered_menu
    assert "用大石和砂浆建造能抵御风暴的石屋" in rendered_menu
    assert "Alice的锋利石片用坏了。" in log
    assert "腌制在海滩产出了咸鱼。" in log
    assert command_to_message("/drop 盐", snapshot, "Alice") == {
        "type": "start_action",
        "action": "drop",
        "args": {"item": "salt"},
    }


def test_storage_items_and_shelters_render_stats_in_english_and_chinese():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "beach",
                "carrying": {"effective_weight": 750, "capacity": 2500, "burden": 30, "relief": 500},
                "carried": [
                    {
                        "item": "basket",
                        "qty": 1,
                        "data": {
                            "storage_capacity": 1000,
                            "slots": 4,
                            "weight_reduction": 1000,
                            "contents": [{"item": "stones", "qty": 2, "age_minutes": 0, "exposed": True, "data": {}}],
                        },
                    },
                    {
                        "item": "woven backpack",
                        "qty": 1,
                        "data": {
                            "storage_capacity": 1000,
                            "slots": 4,
                            "weight_reduction": 1000,
                            "equipped_weight_reduction": 250,
                        },
                    },
                    {"item": "sticks", "qty": 1},
                ],
                "available_actions": ["pack", "unpack", "store", "retrieve", "build shed", "build storage chest", "build supply chest"],
            }
        },
        "locations": {
            "beach": {
                "features": ["coconut palms"],
                "resources": {},
                "ground": [],
                "placed": [
                    {
                        "kind": "shed",
                        "fuel": 0,
                        "active": True,
                        "data": {"storage_capacity": 15000, "rain_protection": 5, "sun_protection": 6},
                    },
                    {
                        "kind": "storage chest",
                        "fuel": 0,
                        "active": True,
                        "data": {
                            "storage_capacity": 4000,
                            "slots": 1,
                            "weight_reduction": 4000,
                            "contents": [{"item": "rope", "qty": 1, "age_minutes": 0, "exposed": True, "data": {}}],
                        },
                    },
                    {
                        "kind": "cellar",
                        "fuel": 0,
                        "active": True,
                        "data": {"storage_capacity": 30000, "cool_storage": 1, "rain_protection": 5},
                    },
                ],
            }
        },
    }

    world_en = format_world_panel(snapshot, "Alice", "en")
    inventory_zh = format_inventory_panel(snapshot, "Alice", "zh")
    menu = CommandMenuState(command_choices(snapshot, "Alice"))
    menu.update("/")
    rendered_menu = menu.render(lang="zh")

    assert "shed" in world_en
    assert "storage 0/15000" in world_en
    assert "storage chest" in world_en
    assert "storage 60/4000" in world_en
    assert "slots 1/1" in world_en
    assert "cellar" in world_en
    assert "cool storage" in world_en
    assert "负重 750/2500" in inventory_zh
    assert "篮子" in inventory_zh
    assert "储量 200/1000" in inventory_zh
    assert "格数 1/4" in inventory_zh
    assert "2 石头" in inventory_zh
    assert "装备减重 250" in inventory_zh
    assert "/pack sticks" in rendered_menu
    assert "/unpack stones" in rendered_menu
    assert "/store sticks" in rendered_menu
    assert "/retrieve rope" in rendered_menu
    assert "/build shed" in rendered_menu
    assert "建造可遮风雨和储物的棚屋" in rendered_menu
    assert command_to_message("/pack 树枝", snapshot, "Alice") == {
        "type": "start_action",
        "action": "pack",
        "args": {"item": "sticks"},
    }
    assert command_to_message("/retrieve 绳子", snapshot, "Alice") == {
        "type": "start_action",
        "action": "retrieve",
        "args": {"item": "rope"},
    }


def test_copper_metalworking_content_renders_with_chinese_support():
    snapshot = {
        "day": 4,
        "minute": 14 * 60,
        "weather": "rain",
        "light": "daylight",
        "paused": False,
        "available_actions": [
            "shape knife mold",
            "cast copper knife",
            "craft copper shovel",
            "hammer copper sheet",
            "make copper needles",
            "craft copper bottle",
            "craft copper jar",
        ],
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "beach",
                "carried": [
                    {"item": "copper knife", "qty": 1, "data": {"durability": 31, "max_durability": 40}},
                    {"item": "copper shovel", "qty": 1, "data": {"durability": 42, "max_durability": 50}},
                    {"item": "copper bottle", "qty": 1, "data": {"liquid_capacity": 600, "sealed": 1}},
                    {
                        "item": "copper jar",
                        "qty": 1,
                        "data": {"liquid_capacity": 150, "sealed": 1, "cookable": 1, "liquid_type": "clean water", "liquid": 50},
                    },
                    {"item": "copper sheet", "qty": 1},
                    {"item": "copper needle", "qty": 4},
                    {"item": "knife mold", "qty": 1},
                ],
                "available_actions": [
                    "shape knife mold",
                    "cast copper knife",
                    "craft copper shovel",
                    "hammer copper sheet",
                    "make copper needles",
                    "craft copper bottle",
                    "craft copper jar",
                ],
            }
        },
        "locations": {
            "beach": {
                "features": ["sea"],
                "location_cards": ["copper vein"],
                "resources": {},
                "ground": [{"item": "axe mold", "qty": 1}, {"item": "spear head", "qty": 1}],
                "placed": [
                    {
                        "kind": "forge",
                        "fuel": 0,
                        "active": True,
                        "data": {"fuel": 48, "temperature": 1100, "max_temperature": 1800},
                    }
                ],
            }
        },
    }
    menu = CommandMenuState(command_choices(snapshot, "Alice"))
    menu.update("/")

    panel = format_world_panel(snapshot, "Alice", "zh")
    inventory = format_inventory_panel(snapshot, "Alice", "zh")
    rendered_menu = menu.render(lang="zh")

    assert "铜矿脉位置卡" in panel
    assert "锻炉" in panel
    assert "斧头模具" in panel
    assert "矛头" in panel
    assert "铜刀" in inventory
    assert "耐久  77 ███████░░░" in inventory
    assert "铜铲" in inventory
    assert "耐久  84 ████████░░" in inventory
    assert "铜瓶" in inventory
    assert "容量 600" in inventory
    assert "铜罐" in inventory
    assert "净水 50/150" in inventory
    assert "铜板" in inventory
    assert "铜针" in inventory
    assert "刀模具" in inventory
    assert "/shape knife mold" in rendered_menu
    assert "/cast copper knife" in rendered_menu
    assert "/craft copper shovel" in rendered_menu
    assert "/hammer copper sheet" in rendered_menu
    assert "/make copper needles" in rendered_menu
    assert "/craft copper bottle" in rendered_menu
    assert "/craft copper jar" in rendered_menu
    assert "用调和泥和铜塑出铜刀模具" in rendered_menu
    assert "在高温高级窑或锻炉中烧出铜刀" in rendered_menu
    assert "把铜板做成小型密封铜罐" in rendered_menu


def test_exit_command_maps_to_exit_message():
    assert command_to_message("/exit", {}) == {"type": "exit"}
