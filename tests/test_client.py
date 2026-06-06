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


def test_player_panel_sorts_stats_by_danger_and_only_lists_current_player_state():
    snapshot = {
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "location": "beach",
                "needs": {"health": 100, "hunger": 20, "thirst": 80, "fatigue": 60, "morale": 70, "stress": 10},
            },
            "Bob": {
                "name": "Bob",
                "connected": True,
                "location": "beach",
                "needs": {"health": 20, "hunger": 100, "thirst": 90, "fatigue": 90, "morale": 90, "stress": 90},
            },
        }
    }

    panel = format_players_panel(snapshot, player_name="Alice", lang="en")

    alice_lines = [line.strip() for line in panel.splitlines()]
    assert alice_lines.index("hunger  20") < alice_lines.index("health  100")
    assert "Alice" in panel
    assert "Bob" not in panel


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
    assert "1 raw fish — half fresh; spoils in 6h" in panel
    assert "1 coconut — fresh food and drink" in panel
    assert "3 sticks — dry fuel and building material" in panel
    assert panel.index("1 raw fish — half fresh; spoils in 6h") < panel.index("1 coconut — fresh food and drink") < panel.index("3 sticks — dry fuel and building material")
    assert "path to rocks — discovered route" in panel
    assert "/pick up" not in panel
    assert "/move" not in panel
    assert "/forage" not in panel
    assert "Inventory" not in panel

    inventory = format_inventory_panel(snapshot, player_name="Alice", lang="en")
    assert inventory.splitlines() == ["Inventory", "  1 stones", "  2 coconut"]


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

    assert "/explore" in choices
    assert "/craft sharp stone" in choices
    assert "/pick up <item>" in choices
    assert "/inspect" in choices
    assert "/pause" in choices
    assert "/exit" in choices
    assert "/action forage" not in choices


def test_slash_choices_use_current_player_location_and_inventory():
    snapshot = {
        "available_actions": ["move", "pick up", "drop"],
        "players": {
            "Alice": {"name": "Alice", "connected": True, "location": "beach", "carried": [{"item": "coconut", "qty": 1}]},
            "Bob": {"name": "Bob", "connected": True, "location": "rocks", "carried": [{"item": "stones", "qty": 1}]},
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


def test_exit_command_maps_to_exit_message():
    assert command_to_message("/exit", {}) == {"type": "exit"}
