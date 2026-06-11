from tropical_adventure.client import (
    COMMAND_HELP_VISIBLE_MATCHES,
    CommandMenuState,
    command_choices,
    command_input_key_effect,
    command_to_message,
    display_width,
    format_event_log,
    action_feedback_event,
    format_inventory_panel,
    format_players_panel,
    format_recipes_panel,
    format_world_panel,
    should_focus_command_input,
    ui_text,
)
from tropical_adventure.content import RAFT_EVENT_PASSING_SHIP, RAFT_RESCUE_DISTANCE, SPOIL_MINUTES


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
                    "parasite_control": 16,
                    "infection_control": 17,
                    "malaria_resistance": 21,
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
        < panel.index("parasite control")
        < panel.index("infection control")
        < panel.index("food poisoning recovery")
        < panel.index("calm")
        < panel.index("stamina")
        < panel.index("malaria resistance")
        < panel.index("coconut appetite")
        < panel.index("morale")
    )
    assert "[red] 15" in panel
    assert "[red] 16" in panel
    assert "[red] 17" in panel
    assert "[red] 18" in panel
    assert "[red] 19" in panel
    assert "[yellow] 20" in panel
    assert "[yellow] 21" in panel
    assert "[yellow] 45" in panel
    assert "[green] 55" in panel
    assert "Alice" in panel
    assert "Bob" not in panel
    assert "水分" in chinese_panel
    assert "寄生虫控制" in chinese_panel
    assert "感染控制" in chinese_panel
    assert "疟疾抵抗" in chinese_panel
    assert "体力" in chinese_panel
    assert "食物中毒恢复" in chinese_panel
    assert "椰子食欲" in chinese_panel
    chinese_stat_prefixes = [line.split("[", 1)[0] for line in chinese_panel.splitlines()[1:]]
    assert len({display_width(prefix) for prefix in chinese_stat_prefixes}) == 1


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


def test_world_panel_omits_global_win_loss_hints_before_outcome():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "outcome": None,
        "raft": {
            "distance": 0,
            "rescue_distance": RAFT_RESCUE_DISTANCE,
            "event": None,
            "event_remaining_minutes": 0,
            "signal_progress": 0,
            "missed_ships": 0,
        },
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "status": "alive",
                "location": "beach",
                "stats": {"health": 100},
            },
        },
        "locations": {
            "beach": {
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

    assert "Escape:" not in world_en
    assert "Death:" not in world_en
    assert "逃离：" not in world_zh
    assert "死亡：" not in world_zh


def test_world_panel_renders_sleep_and_blocked_action_hints_in_both_languages():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "outcome": None,
        "raft": {"distance": 0, "rescue_distance": RAFT_RESCUE_DISTANCE},
        "sleep": {"all_resting": False, "resting": ["Alice"], "waiting_for": ["Bob"]},
        "blocked_actions": [
            {
                "action": "build raft",
                "missing": [
                    {"kind": "item", "item": "log", "qty": 4, "have": 0, "nearby": True},
                    {"kind": "tool", "item": "stone axe", "qty": 1, "have": 0},
                    {"kind": "light"},
                ],
            }
        ],
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "status": "alive",
                "location": "beach",
                "stats": {"health": 100},
                "current_action": {"name": "rest", "remaining_minutes": 12, "total_minutes": 18},
            },
            "Bob": {"name": "Bob", "connected": True, "status": "alive", "location": "beach"},
        },
        "locations": {
            "beach": {
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
    recipes_en = format_recipes_panel(snapshot, "en")
    recipes_zh = format_recipes_panel(snapshot, "zh")

    assert "Rest: waiting for Bob; time stays normal" in world_en
    assert "Blocked:" not in world_en
    assert "build raft — 4 log, stone axe, usable light" in recipes_en
    assert "休息：等待 Bob 休息；时间保持正常速度" in world_zh
    assert "暂不可用：" not in world_zh
    assert "建造木筏 — 4 原木, 石斧, 可用光线" in recipes_zh

    snapshot["sleep"] = {"all_resting": True, "resting": ["Alice", "Bob"], "waiting_for": []}
    world_en = format_world_panel(snapshot, "Alice", "en")
    world_zh = format_world_panel(snapshot, "Alice", "zh")

    assert "Rest: everyone is resting; time skips ahead" in world_en
    assert "休息：所有玩家都在休息，时间会快进" in world_zh

    snapshot["paused"] = True
    paused_en = format_world_panel(snapshot, "Alice", "en")
    paused_zh = format_world_panel(snapshot, "Alice", "zh")

    assert "Rest: world is paused; resume to allow time skip" in paused_en
    assert "休息：世界已暂停；恢复后才会快进" in paused_zh


def test_world_panel_shows_unfinished_raft_status_and_next_components():
    snapshot = {
        "day": 3,
        "minute": 12 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "outcome": None,
        "raft": {"distance": 0, "rescue_distance": RAFT_RESCUE_DISTANCE},
        "players": {"Alice": {"name": "Alice", "location": "beach", "stats": {"health": 100}}},
        "locations": {
            "beach": {
                "features": ["sea"],
                "location_cards": [],
                "resources": {},
                "ground": [],
                "placed": [{"kind": "raft frame", "fuel": 0, "active": True, "data": {"stage": 2, "stages": 5}}],
            },
        },
    }

    world_en = format_world_panel(snapshot, "Alice", "en")
    world_zh = format_world_panel(snapshot, "Alice", "zh")

    assert "Raft build:" not in world_en
    assert "raft frame — unfinished escape raft frame; stage 2/5  40 ████░░░░░░; next: 3 log, 7 rope, 2 long stick" in world_en
    assert "木筏建造：" not in world_zh
    assert "木筏框架 — 尚未完成的逃生木筏框架；阶段 2/5  40 ████░░░░░░；下一步：3 原木, 7 绳子, 2 长树枝" in world_zh

    snapshot["locations"]["beach"]["placed"][0]["data"] = {"stage": 3, "stages": 5}
    later_stage_zh = format_world_panel(snapshot, "Alice", "zh")
    assert "下一步：4 皮革, 6 纤维绳, 2 绳子, 针损耗 2" in later_stage_zh
    assert "Alice把木筏框架推进到阶段 2/5。" in format_event_log(
        ["Alice advanced the raft frame to stage 2/5."],
        "zh",
    )


def test_world_panel_describes_scene_objects_without_duplicate_action_hints():
    snapshot = {
        "day": 2,
        "minute": 9 * 60 + 30,
        "weather": "rain",
        "light": "daylight",
        "paused": False,
        "players": {
            "Alice": {
                "name": "Alice",
                "location": "beach",
                "carried": [{"item": "coconut", "qty": 2}, {"item": "stones", "qty": 1}],
                "carrying": {
                    "effective_weight": 700,
                    "capacity": 2500,
                    "burden": 28,
                    "relief": 0,
                    "loose_slots": 2,
                    "loose_slot_capacity": 4,
                    "back_slots": 0,
                    "back_slot_capacity": 1,
                },
            }
        },
        "locations": {
            "beach": {
                "features": ["sea", "sand", "coconut palms"],
                "resources": {
                    "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
                    "coconut palm": {
                        "source": "coconut palms",
                        "qty": 2,
                        "capacity": 2,
                        "regen_minutes": 4320,
                        "action": "harvest coconuts",
                    },
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
    assert "weather: rain; light: daylight; tide: low" in panel
    assert "paused: False" in panel
    assert "Scene: beach" in panel
    assert "sea — open salt water" in panel
    assert "unsafe water source: infinite" not in panel
    assert "sand — warm pale sand" in panel
    assert "coconut palms — shade and coconuts; palms 2/2" in panel
    assert "regrows every" not in panel
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
        "  Load 700/2500  28 ██░░░░░░░░",
        "  Slots: hands 2/4, back 0/1",
        "  Index  Item                   Bar        Load",
        "  [1] 1 stones                          100",
        "  [2] 2 coconut                         600",
    ]


def test_world_panel_localizes_weather_season_tide_and_storm_integrity():
    snapshot = {
        "day": 2,
        "minute": 14 * 60,
        "weather": "heavy rain",
        "season": "wet",
        "rain_counter": 612,
        "rain_value": 5,
        "sun_strength": 0,
        "tide": "high",
        "light": "daylight",
        "paused": False,
        "players": {"Alice": {"name": "Alice", "location": "beach", "carried": []}},
        "locations": {
            "beach": {
                "features": [],
                "location_cards": ["flooded tide pool"],
                "resources": {},
                "ground": [],
                "placed": [{"kind": "raincatcher", "fuel": 0, "active": True, "data": {"storm_damage": 25}}],
            },
        },
    }

    panel_en = format_world_panel(snapshot, player_name="Alice", lang="en")
    panel_zh = format_world_panel(snapshot, player_name="Alice", lang="zh")

    assert "weather: heavy rain; light: daylight; tide: high" in panel_en
    assert "season: wet; rain counter: 612/700; rain: 5/5; sun: 0/6" in panel_en
    assert "paused: False" in panel_en
    assert "raincatcher — collects rain into clean water; storm integrity  75" in panel_en
    assert "天气: 大雨; 光线: 日光; 潮汐: 涨潮" in panel_zh
    assert "季节: 雨季; 雨势计数: 612/700; 雨量: 5/5; 日照: 0/6" in panel_zh
    assert "暂停: False" in panel_zh
    assert "接雨器 — 把雨水收集成净水；风暴完整度  75" in panel_zh


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
    assert chinese.splitlines() == ["Bob 加入了小岛。", "⠋ Alice 正在探索… 剩余 12 分钟"]
    assert action_feedback_event({"type": "start_action", "action": "explore"}, player_name="Alice") == {
        "name": "explore",
        "remaining_minutes": 18,
        "total_minutes": 18,
    }


def test_format_event_log_shows_only_last_5_events_without_duplicates():
    events = [f"event {i}" for i in range(12)]

    rendered = format_event_log(events)

    assert rendered.splitlines() == [f"event {i}" for i in range(7, 12)]


def test_format_event_log_localizes_common_game_events_to_chinese():
    events = [
        "Day 2 begins.",
        "Alice started gather.",
        "Alice completed gather.",
        "Alice discovered rocks.",
        "Raw fish spoiled at beach.",
    ]

    rendered = format_event_log(events, lang="zh")

    assert rendered.splitlines() == [
        "第 2 天开始了。",
        "Alice 开始收集。",
        "Alice 完成收集。",
        "Alice 发现了岩石。",
        "生鱼在海滩腐坏了。",
    ]
    assert format_event_log(["Alice launched a raft at the beach."], lang="zh") == "Alice在海滩放下了木筏。"
    assert format_event_log(["Leaves dried at Alice's pack."], lang="zh") == "叶子在Alice的背包变成干叶了。"
    assert format_event_log(["Fleshed skin cured at Alice's pack."], lang="zh") == "刮净兽皮在Alice的背包变成皮革了。"
    assert format_event_log(["Lit tinder burned out at Alice's pack."], lang="zh") == "点燃的火绒在Alice的背包熄灭了。"
    assert format_event_log(["Lit torch burned out at Alice's pack."], lang="zh") == "点燃的火把在Alice的背包熄灭了。"
    assert format_event_log(["Heavy rain starts over the island."], lang="zh") == "岛上下起了大雨。"
    assert format_event_log(["A storm lashes the island."], lang="zh") == "风暴抽打着小岛。"
    assert format_event_log(["The sky clears."], lang="zh") == "天空放晴了。"
    assert format_event_log(["Storm winds battered Alice at beach."], lang="zh") == "风暴在海滩吹打着Alice。"
    assert format_event_log(["Storm damaged raincatcher at beach."], lang="zh") == "风暴损坏了海滩的接雨器。"
    assert format_event_log(["A raincatcher at beach was wrecked by the storm."], lang="zh") == "海滩的接雨器被风暴毁坏了。"
    assert format_event_log(["Day 1 dawns on the beach."], lang="zh") == "第 1 天在海滩破晓。"
    assert (
        format_event_log(
            ["Tip: pick up a coconut and drink it for quick water; gather unsafe water and boil it for safer water."],
            lang="zh",
        )
        == "提示：捡起椰子后可以饮用；也可以收集不安全的水并煮成净水。"
    )
    assert format_event_log(["Alice reconnected."], lang="zh") == "Alice 重新连接了。"
    assert format_event_log(["Alice cancelled gather."], lang="zh") == "Alice 取消了收集。"
    assert format_event_log(["Alice found nothing while walking beach."], lang="zh") == "Alice 在散步海滩时什么也没找到。"
    assert format_event_log(["Alice found nothing while diving bay."], lang="zh") == "Alice 在潜水海湾时什么也没找到。"
    assert format_event_log(["Alice caught nothing while fishing beach."], lang="zh") == "Alice 在海滩钓鱼时一无所获。"
    assert format_event_log(["Alice caught nothing while spear fishing bay."], lang="zh") == "Alice 在海湾叉鱼时一无所获。"
    assert format_event_log(["Aloe vera regrew at beach."], lang="zh") == "芦荟在海滩重新长出来了。"
    assert (
        format_event_log(["Alice had no free carry slot, so 1 raw fish was left at beach."], lang="zh")
        == "Alice没有空余携带格，1个生鱼留在了海滩。"
    )


def test_format_event_log_localizes_server_and_exploration_events_to_chinese():
    events = [
        "Alice joined the island.",
        "Bob disconnected",
        "Alice found brimstone vent at acid lake.",
        "Alice found 1 wood while exploring beach.",
        "manual save complete",
        "save already in progress",
        "server disconnected",
        "Alice paused the world.",
        "world paused",
        "Alice resumed the world.",
        "world resumed",
        "Alice cancelled action.",
    ]

    rendered = format_event_log(events, lang="zh")

    assert "joined the island" not in rendered
    assert "disconnected" not in rendered
    assert "found brimstone vent at acid lake" not in rendered
    assert "while exploring" not in rendered
    assert "manual save complete" not in rendered
    assert "save already in progress" not in rendered
    assert "server disconnected" not in rendered
    assert "paused the world" not in rendered
    assert "world paused" not in rendered
    assert "resumed the world" not in rendered
    assert "world resumed" not in rendered
    assert "cancelled action" not in rendered


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
                "placed": [{"kind": "fire remnants", "fuel": 0, "active": True, "data": {}}],
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
    assert "火堆残迹" in rich_panel
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
    assert command_to_message("/pause", snapshot) == {"type": "pause"}
    assert command_to_message("/resume", snapshot) == {"type": "resume"}
    assert command_to_message("/go for a walk", snapshot) == {
        "type": "start_action",
        "action": "go for a walk",
        "args": {},
    }
    assert command_to_message("/forage tide pool", snapshot) == {
        "type": "start_action",
        "action": "forage tide pool",
        "args": {},
    }
    assert command_to_message("/dive", snapshot) == {
        "type": "start_action",
        "action": "dive",
        "args": {},
    }
    assert command_to_message("/spear fish", snapshot) == {
        "type": "start_action",
        "action": "spear fish",
        "args": {},
    }
    assert command_to_message("/fish with bait", snapshot) == {
        "type": "start_action",
        "action": "fish with bait",
        "args": {},
    }
    assert command_to_message("/break conch", snapshot) == {
        "type": "start_action",
        "action": "break conch",
        "args": {},
    }
    assert command_to_message("/cook conch meat", snapshot) == {
        "type": "start_action",
        "action": "cook conch meat",
        "args": {},
    }
    assert command_to_message("/forage", snapshot) is None
    assert command_to_message("/forage dry leaves", snapshot) is None


def test_slash_choices_include_available_actions_and_client_commands():
    snapshot = {"available_actions": ["explore", "craft sharp stone", "pick up"]}

    choices = command_choices(snapshot)

    assert choices[:3] == ["/explore", "/craft sharp stone", "/pick up"]
    assert "/explore" in choices
    assert "/craft sharp stone" in choices
    assert "/pick up" in choices
    assert "/inspect" not in choices
    assert "/crafts" in choices
    assert "/pause" in choices
    assert "/recipes" in choices
    assert "/exit" in choices
    assert "/action forage" not in choices
    assert command_to_message("/inspect", snapshot) is None
    assert command_to_message("/recipes", snapshot) is None


def test_recipes_panel_lists_available_and_missing_recipe_requirements():
    snapshot = {
        "available_actions": ["explore", "craft sharp stone", "build raft"],
        "blocked_actions": [
            {
                "action": "build raft",
                "missing": [
                    {"kind": "item", "item": "log", "qty": 4},
                    {"kind": "tool", "item": "stone axe"},
                ],
            }
        ],
    }

    panel_en = format_recipes_panel(snapshot, "en")
    panel_zh = format_recipes_panel(snapshot, "zh")

    assert "Recipes" in panel_en
    assert "craft sharp stone — 1 stones" in panel_en
    assert "build raft — 4 log, stone axe" in panel_en
    assert "配方" in panel_zh
    assert "制作锋利石片 — 1 石头" in panel_zh
    assert "建造木筏 — 4 原木, 石斧" in panel_zh


def test_slash_menu_preserves_recent_action_order_from_snapshot():
    snapshot = {"available_actions": ["rest", "gather", "explore"]}

    menu = CommandMenuState(command_choices(snapshot))
    menu.update("/")

    assert menu.matches[:3] == ["/rest", "/gather", "/explore"]
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

    assert "/drop 1(stones) 1" in choices
    assert "/pick up 1(stones) 1" in choices
    assert "/move 1(beach)" in choices
    assert "/drop 1(coconut) 1" not in choices
    assert "/pick up 1(coconut) 1" not in choices


def test_scene_items_show_indexes_and_pickup_commands_use_them():
    snapshot = {
        "day": 1,
        "minute": 360,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "location": "beach",
                "available_actions": ["pick up"],
                "carried": [],
            }
        },
        "locations": {
            "beach": {
                "features": [],
                "resources": {},
                "placed": [
                    {"kind": "fire", "fuel": 2, "active": True, "data": {}},
                    {"kind": "basket", "fuel": 0, "active": True, "data": {"storage_capacity": 1000, "slots": 4}},
                ],
                "ground": [
                    {"item": "coconut", "qty": 1},
                    {"item": "raw fish", "qty": 1, "age_minutes": 30},
                ],
            }
        },
    }

    panel = format_world_panel(snapshot, "Alice", "en")
    choices = command_choices(snapshot, "Alice")

    assert "  [1] fire(fuel 2)" in panel
    assert "  [2] basket" in panel
    assert "  [3] 1 raw fish" in panel
    assert "  [4] 1 coconut" in panel
    assert "/pick up fire 1" not in choices
    assert "/pick up 2(basket) 1" in choices
    assert "/pick up 3(raw fish) 1" in choices
    assert "/pick up 4(coconut) 1" in choices
    menu = CommandMenuState(choices)
    menu.update("/")
    assert "/pick up" in menu.matches
    assert "/pick up 3(raw fish) 1" not in menu.matches
    menu.update("/pick up ")
    assert "/pick up 3(raw fish) 1" in menu.matches
    assert command_to_message("/pick up 3(raw fish) 1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "pick up",
        "args": {"ground_index": 1, "item": "raw fish", "qty": 1},
    }
    assert command_to_message("/pick up 2(basket) 1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "pick up",
        "args": {"placed_index": 1, "item": "basket"},
    }
    assert command_to_message("/pick up 生鱼 3", snapshot, "Alice") == {
        "type": "start_action",
        "action": "pick up",
        "args": {"ground_index": 1, "item": "raw fish"},
    }


def test_hand_drill_tinder_commands_and_item_stats_render():
    snapshot = {
        "available_actions": [],
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "location": "beach",
                "available_actions": [
                    "light tinder with hand drill",
                    "light tinder with bow drill",
                    "light tinder from fire",
                    "light tinder with mirror",
                ],
                "carried": [
                    {"item": "hand drill", "qty": 1, "data": {"durability": 29, "max_durability": 30}},
                    {"item": "bow drill", "qty": 1, "data": {"durability": 30, "max_durability": 30}},
                    {"item": "leaves", "qty": 1, "age_minutes": SPOIL_MINUTES["leaves"] - 60},
                    {"item": "dry leaves", "qty": 1},
                    {"item": "wood shavings", "qty": 1},
                    {"item": "lit tinder", "qty": 1, "data": {"fuel": 6, "max_fuel": 6}},
                ],
            }
        },
        "locations": {"beach": {"ground": [], "placed": []}},
    }

    choices = command_choices(snapshot, "Alice")
    menu = CommandMenuState(choices)
    menu.update("/light tinder")
    inventory = format_inventory_panel(snapshot, "Alice", "zh")

    assert "/light tinder with hand drill 3(dry leaves) 1" in choices
    assert "/light tinder with hand drill 2(wood shavings) 1" in choices
    assert "/light tinder with hand drill 3(leaves) 1" not in choices
    assert "/light tinder with bow drill 2(wood shavings) 1" in choices
    assert "/light tinder from fire 3(dry leaves) 1" in choices
    assert "/light tinder with mirror 3(dry leaves) 1" in choices
    menu.update("/light tinder with hand drill ")
    assert "/light tinder with hand drill 2(wood shavings) 1 (用手钻点火绒 木屑 2)" in menu.render(lang="zh")
    menu.update("/light tinder from fire ")
    assert "/light tinder from fire 3(dry leaves) 1 (从火堆点火绒 干叶 3)" in menu.render(lang="zh")
    menu.update("/light tinder with mirror ")
    assert "/light tinder with mirror 3(dry leaves) 1 (用信号镜点火绒 干叶 3)" in menu.render(lang="zh")
    assert "弓钻" in inventory
    assert "手钻" in inventory
    assert "干叶" in inventory
    assert "点燃的火绒" in inventory
    assert "██████████" in inventory
    assert "█████████░" in inventory
    assert command_to_message("/light tinder with hand drill 木屑", snapshot, "Alice") == {
        "type": "start_action",
        "action": "light tinder with hand drill",
        "args": {"item": "wood shavings"},
    }
    assert command_to_message("/light tinder with hand drill 2(wood shavings) 1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "light tinder with hand drill",
        "args": {"item": "wood shavings"},
    }
    assert command_to_message("/light tinder with bow drill 木屑", snapshot, "Alice") == {
        "type": "start_action",
        "action": "light tinder with bow drill",
        "args": {"item": "wood shavings"},
    }
    assert command_to_message("/light tinder from fire 干叶", snapshot, "Alice") == {
        "type": "start_action",
        "action": "light tinder from fire",
        "args": {"item": "dry leaves"},
    }
    assert command_to_message("/light tinder with mirror 干叶", snapshot, "Alice") == {
        "type": "start_action",
        "action": "light tinder with mirror",
        "args": {"item": "dry leaves"},
    }


def test_torch_commands_item_stats_and_chinese_light_render():
    snapshot = {
        "day": 1,
        "minute": 23 * 60,
        "weather": "clear",
        "paused": False,
        "light": "torchlit",
        "available_actions": [],
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "location": "beach",
                "available_actions": ["craft torch", "light torch", "extinguish torch"],
                "carried": [
                    {"item": "torch", "qty": 1, "data": {"fuel": 12, "max_fuel": 16}},
                    {"item": "lit torch", "qty": 1, "age_minutes": 60, "data": {"max_fuel": 16}},
                ],
            }
        },
        "locations": {
            "beach": {
                "name": "beach",
                "discovered": True,
                "features": [],
                "location_cards": [],
                "ground": [],
                "placed": [],
                "resources": {},
                "neighbors": [],
            }
        },
        "raft": {},
    }

    choices = command_choices(snapshot, "Alice")
    menu = CommandMenuState(choices)
    menu.update("/light")
    inventory = format_inventory_panel(snapshot, "Alice", "zh")
    world = format_world_panel(snapshot, "Alice", "zh")

    assert "/craft torch" in choices
    assert "/light torch" in choices
    assert "/extinguish torch" in choices
    assert "/light torch (点燃火把)" in menu.render(lang="zh")
    assert command_to_message("/light torch", snapshot, "Alice") == {
        "type": "start_action",
        "action": "light torch",
        "args": {},
    }
    assert "火把" in inventory
    assert "点燃的火把" in inventory
    assert "███████░░░" in inventory
    assert "光线: 火把光" in world


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
    assert menu.matches == ["/pause", "/pick up"]
    assert menu.selected == "/pause"
    menu.move_down()
    assert menu.selected == "/pick up"
    assert menu.completion_value() == "/pick up "


def test_slash_menu_shows_no_match_instead_of_falling_back_to_all_commands():
    menu = CommandMenuState(["/explore", "/gather"])

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
    assert "/move" in rendered
    assert "travel to a discovered location" in rendered
    assert "/save" in rendered
    assert "save the world" in rendered


def test_slash_menu_renders_chinese_action_descriptions():
    menu = CommandMenuState(["/explore", "/move 1(beach)", "/move <location>", "/save"])
    menu.update("/")
    rendered = menu.render(lang="zh")

    assert "/explore" in rendered
    assert "/explore (探索)" in rendered
    assert "搜索当前区域的新地点" in rendered
    assert "/move (移动)" in rendered
    assert "前往已发现地点" in rendered
    assert "/save" in rendered
    assert "保存世界" in rendered
    menu.update("/move ")
    assert "/move 1(beach) (移动 海滩 1)" in menu.render(lang="zh")


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
                    "ash": {"source": "hot ground", "infinite": True, "action": "gather"},
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
    assert "ash source: infinite" not in panel


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


def test_world_panel_skips_location_cards_already_shown_as_features():
    snapshot = {
        "day": 1,
        "minute": 6 * 60,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {"Alice": {"name": "Alice", "location": "beach"}},
        "locations": {
            "beach": {
                "features": ["sea", "sand"],
                "location_cards": ["sea", "sand", "palm tree"],
                "resources": {},
                "ground": [],
                "placed": [],
            }
        },
    }

    panel = format_world_panel(snapshot, player_name="Alice", lang="en")

    assert panel.count("sea —") == 1
    assert panel.count("sand —") == 1
    assert "palm tree — a tall palm tree" in panel


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
    assert "/move 1(jungle outskirts)" in choices
    assert "/move rocks" not in choices
    assert "/move" in choices
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


def test_renderable_content_has_chinese_translation_coverage():
    from tropical_adventure import client, content
    from tropical_adventure.game import SHELTER_STORAGE_CAPACITY, STORAGE_DATA

    items = set(content.ITEM_WEIGHTS) | set(content.FOOD_VALUES) | set(content.DRINK_VALUES)
    for recipe in content.ACTION_INPUTS.values():
        items.update(recipe)
    for stage in content.RAFT_BUILD_STAGES:
        items.update(stage.get("materials", {}))
        items.update(stage.get("tool_wear", {}))
    for data in content.RESOURCE_HARVESTS.values():
        items.add(data["resource"])
        for output in data.get("outputs", []):
            items.add(output[0])
    items.update(content.TIDE_POOL_OUTPUTS)
    for weights in content.DIVE_OUTPUT_WEIGHTS.values():
        items.update(dict(weights))
    items.update(content.FISH_TRAP_OUTPUTS)
    items.update(content.SNARE_TRAP_OUTPUTS)
    features = set()
    resources = set()
    for area in content.AREA_DEFS.values():
        items.update(area.get("ground", {}))
        resources.update(area.get("resources", {}))
        features.update(area.get("features", []))
        features.update(str(resource["source"]) for resource in area.get("resources", {}).values() if resource.get("source"))
    location_cards = set(content.LOCATION_CARD_DEFS)
    for cards in content.AREA_LOCATION_CARDS.values():
        location_cards.update(cards)
    for cards in content.AREA_EXPLORE_CARDS.values():
        location_cards.update(cards)
    placed = {
        "fire",
        "fire remnants",
        "sand castle",
        "raft frame",
        "basket",
        *STORAGE_DATA.keys(),
        *SHELTER_STORAGE_CAPACITY.keys(),
        *content.STORM_DAMAGE_OBJECTS,
    }
    for action in content.ACTION_DEFS:
        if action.startswith("build "):
            placed.add(action.removeprefix("build "))
    if "craft leaf bed" in content.ACTION_DEFS:
        placed.add("leaf bed")

    missing = {
        "object_names_zh": sorted(
            name
            for name in items | set(content.AREA_DEFS) | features | resources | location_cards | placed
            if name not in client.OBJECT_NAMES_ZH
        ),
        "item_descriptions_zh": sorted(name for name in items if name not in client.ITEM_DESCRIPTIONS["zh"]),
        "item_descriptions_en": sorted(name for name in items if name not in client.ITEM_DESCRIPTIONS["en"]),
        "feature_descriptions_zh": sorted(name for name in features if name not in client.FEATURE_DESCRIPTIONS["zh"]),
        "placed_descriptions_zh": sorted(name for name in placed if name not in client.PLACED_DESCRIPTIONS["zh"]),
        "action_names_zh": sorted(name for name in content.ACTION_DEFS if name not in client.ACTION_NAMES_ZH),
        "command_descriptions_zh": sorted(name for name in content.ACTION_DEFS if name not in client.COMMAND_DESCRIPTIONS["zh"]),
        "ui_text_zh": sorted(set(client.TRANSLATIONS["en"]) - set(client.TRANSLATIONS["zh"])),
    }

    assert {key: values for key, values in missing.items() if values} == {}


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
    assert "芦荟 1/1" in panel
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
    assert "爬上结果的棕榈树采下椰子" in rendered_menu
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
    assert "西米棕榈 2/2" in panel
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
    assert "泥土堆 2/3" in panel
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
    assert "█████░░░░░" in inventory
    assert "███░░░░░░░" in inventory
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
                "carrying": {
                    "effective_weight": 800,
                    "capacity": 2500,
                    "burden": 32,
                    "relief": 450,
                    "loose_slots": 3,
                    "loose_slot_capacity": 4,
                    "back_slots": 1,
                    "back_slot_capacity": 1,
                },
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
                            "equipped_slot": "back",
                        },
                    },
                    {"item": "sticks", "qty": 1},
                ],
                "available_actions": [
                    "pick up",
                    "pack",
                    "unpack",
                    "store",
                    "retrieve",
                    "place basket",
                    "take off backpack",
                    "build shed",
                    "build storage chest",
                    "build supply chest",
                ],
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
    inventory_en = format_inventory_panel(snapshot, "Alice", "en")
    inventory_zh = format_inventory_panel(snapshot, "Alice", "zh")
    choices = command_choices(snapshot, "Alice")
    menu = CommandMenuState(choices)
    menu.update("/")
    rendered_menu = menu.render(lang="zh")

    assert "shed" in world_en
    assert "storage 0/15000" in world_en
    assert "storage chest" in world_en
    assert "storage 60/4000" in world_en
    assert "storage 60/4000   1 ░░░░░░░░░░" in world_en
    assert "slots 1/1" in world_en
    assert "slots 1/1 100 ██████████" in world_en
    assert "[2.1] 1 rope" in world_en
    assert "cellar" in world_en
    assert "cool storage" in world_en
    assert "hands 3/4" in inventory_en
    assert "back 1/1" in inventory_en
    assert "[1] 1 sticks" in inventory_en
    assert "[3] 1 basket" in inventory_en
    assert "[3.1] 2 stones" in inventory_en
    assert "[1] 1 sticks                          50" in inventory_en
    assert "250/500" in inventory_en
    assert "500/700" in inventory_en
    assert "负重 800/2500" in inventory_zh
    assert "手持 3/4" in inventory_zh
    assert "背部 1/1" in inventory_zh
    assert "[1] 1 树枝" in inventory_zh
    assert "[3] 1 篮子" in inventory_zh
    assert "[3.1] 2 石头" in inventory_zh
    assert "篮子" in inventory_zh
    assert "██░░░░░░░░" in inventory_zh
    assert "50" in inventory_zh
    assert "250/500" in inventory_zh
    assert "500/700" in inventory_zh
    assert "2 石头" in inventory_zh
    assert "/pick up storage chest" not in choices
    assert "/pack" in rendered_menu
    assert "/unpack" in rendered_menu
    assert "/store" in rendered_menu
    assert "/retrieve" in rendered_menu
    assert "/place basket" in rendered_menu
    assert "/take off backpack" in rendered_menu
    assert "/build shed" in rendered_menu
    assert "建造可遮风雨和储物的棚屋" in rendered_menu
    menu.update("/pack ")
    assert "/pack 1(sticks) 1" in menu.render(lang="zh")
    menu.update("/unpack ")
    assert "/unpack 3.1(stones) 1" in menu.render(lang="zh")
    menu.update("/store ")
    assert "/store 1(sticks) 1" in menu.render(lang="zh")
    menu.update("/retrieve ")
    assert "/retrieve 2.1(rope) 1" in menu.render(lang="zh")
    menu.update("/place basket ")
    assert "/place basket 3(basket) 1" in menu.render(lang="zh")
    assert command_to_message("/pack 树枝", snapshot, "Alice") == {
        "type": "start_action",
        "action": "pack",
        "args": {"item": "sticks"},
    }
    assert command_to_message("/pack 树枝 1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "pack",
        "args": {"carried_index": 2, "item": "sticks"},
    }
    assert command_to_message("/unpack 石头 3.1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "unpack",
        "args": {"carried_index": 0, "content_index": 0, "item": "stones"},
    }
    assert command_to_message("/retrieve 绳子", snapshot, "Alice") == {
        "type": "start_action",
        "action": "retrieve",
        "args": {"item": "rope"},
    }
    assert command_to_message("/retrieve 绳子 2.1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "retrieve",
        "args": {"placed_index": 1, "content_index": 0, "item": "rope"},
    }
    assert command_to_message("/place basket 3", snapshot, "Alice") == {
        "type": "start_action",
        "action": "place basket",
        "args": {"carried_index": 0, "item": "basket"},
    }
    assert command_to_message("/take off backpack", snapshot, "Alice") == {
        "type": "start_action",
        "action": "take off backpack",
        "args": {},
    }


def test_scene_storage_contents_show_retrieve_indexes_and_dynamic_state():
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
                "carried": [],
                "available_actions": ["retrieve"],
            }
        },
        "locations": {
            "beach": {
                "features": [],
                "resources": {},
                "ground": [],
                "placed": [
                    {"kind": "fire", "fuel": 2, "active": True, "data": {}},
                    {
                        "kind": "storage chest",
                        "fuel": 0,
                        "active": True,
                        "data": {
                            "storage_capacity": 4000,
                            "slots": 2,
                            "weight_reduction": 4000,
                            "contents": [{"item": "raw fish", "qty": 1, "age_minutes": 360, "exposed": True, "data": {}}],
                        },
                    },
                ],
            }
        },
    }

    world_en = format_world_panel(snapshot, "Alice", "en")
    world_zh = format_world_panel(snapshot, "Alice", "zh")
    choices = command_choices(snapshot, "Alice")

    assert "  [1] fire(fuel 2)" in world_en
    assert "  [2] storage chest" in world_en
    assert "storage 180/4000   4 ░░░░░░░░░░" in world_en
    assert "slots 1/2  50 █████░░░░░" in world_en
    assert "    [2.1] 1 raw fish — half fresh; spoils in 6h; freshness  50 █████░░░░░" in world_en
    assert "    [2.1] 1 生鱼 — 半新鲜；6 小时后腐坏；新鲜度  50 █████░░░░░" in world_zh
    assert "/retrieve 2.1(raw fish) 1" in choices
    assert command_to_message("/retrieve raw fish 2.1", snapshot, "Alice") == {
        "type": "start_action",
        "action": "retrieve",
        "args": {"placed_index": 1, "content_index": 0, "item": "raw fish"},
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
    assert "███████░░░" in inventory
    assert "铜铲" in inventory
    assert "████████░░" in inventory
    assert "铜瓶" in inventory
    assert "铜罐" in inventory
    assert "███░░░░░░░" in inventory
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
