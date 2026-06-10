from __future__ import annotations

import argparse
import asyncio
import contextlib
import re
from typing import Any

from .content import LOCATION_CARD_DEFS
from .game import ACTION_DURATIONS
from .models import MAX_EVENT_LOG
from .protocol import read_json_line, write_json_line

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, VerticalScroll
    from textual.suggester import SuggestFromList
    from textual.widgets import Input, Static
except Exception:  # pragma: no cover - allows protocol tests without textual installed
    App = object  # type: ignore
    ComposeResult = object  # type: ignore
    SuggestFromList = None  # type: ignore
    Horizontal = VerticalScroll = Input = Static = None  # type: ignore


CLIENT_COMMANDS = ["/cancel", "/exit", "/inspect", "/pause", "/resume", "/save"]
COMMAND_HELP_VISIBLE_MATCHES = 20
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
COMMAND_DESCRIPTIONS = {
    "en": {
        "boil water": "turn unsafe water into clean water",
        "build raincatcher": "build a raincatcher for water",
        "build shelter": "build a shelter for safer rest",
        "cancel": "cancel your current action",
        "cook fish": "cook raw fish over an active fire",
        "craft sharp stone": "make a sharp stone tool",
        "drink": "drink carried clean water or coconut",
        "drop": "drop an item at your location",
        "eat": "eat carried food",
        "exit": "save and exit the client",
        "explore": "search the current area for new locations",
        "fish": "catch fish in coastal fishing spots",
        "forage": "look for edible or medicinal plants",
        "gather": "collect nearby natural materials",
        "inspect": "request the latest world snapshot",
        "leisure": "take a morale-restoring break",
        "move": "travel to a discovered location",
        "pause": "pause the world simulation",
        "pick up": "pick up an item from the ground",
        "rest": "recover fatigue",
        "resume": "resume the world simulation",
        "save": "save the world",
        "start fire": "start a fire from carried materials",
        "swim": "swim to cool off and practice",
        "tend fire": "add fuel to an active fire",
        "treat wound": "treat wounds with bandage leaves",
        "wash": "wash off grime and stress",
    },
    "zh": {
        "boil water": "把不安全的水煮成净水",
        "build raincatcher": "建造接雨器收集雨水",
        "build shelter": "建造庇护所以便更安全地休息",
        "cancel": "取消当前行动",
        "cook fish": "在火堆上烤熟生鱼",
        "craft sharp stone": "制作锋利石片工具",
        "drink": "饮用携带的净水或椰子",
        "drop": "把物品放到当前位置",
        "eat": "吃掉携带的食物",
        "exit": "保存并退出客户端",
        "explore": "搜索当前区域的新地点",
        "fish": "在沿海渔点捕鱼",
        "forage": "觅食，寻找可食用或药用植物",
        "gather": "收集附近的自然材料",
        "inspect": "请求最新世界快照",
        "leisure": "放松休闲以恢复士气",
        "move": "前往已发现地点",
        "pause": "暂停世界模拟",
        "pick up": "从地上捡起物品",
        "rest": "恢复疲劳",
        "resume": "恢复世界模拟",
        "save": "保存世界",
        "start fire": "用携带材料生火",
        "swim": "游泳降温并练习水性",
        "tend fire": "给火堆添加燃料",
        "treat wound": "用绷带叶处理伤口",
        "wash": "清洗身体并降低压力",
    },
}
OBJECT_NAMES_ZH = {
    "beach": "海滩",
    "jungle outskirts": "丛林边缘",
    "rocks": "岩石",
    "tide pool": "潮池",
    "jungle": "丛林",
    "bay": "海湾",
    "mangrove forest": "红树林",
    "wetlands": "湿地",
    "deep jungle": "丛林深处",
    "secret cove": "秘密海湾",
    "acid lake": "酸湖",
    "atoll": "环礁",
    "bird rock": "鸟岩",
    "desolate beach": "荒凉海滩",
    "eastern grasslands": "东部草原",
    "western grasslands": "西部草原",
    "eastern highlands": "东部高地",
    "western highlands": "西部高地",
    "jungle highlands": "丛林高地",
    "secret valley": "秘密山谷",
    "volcano": "火山",
    "highland hole": "高地洞口",
    "enclosure": "围栏",
    "raft": "木筏",
    "bat cave": "蝙蝠洞",
    "cellar": "地窖",
    "dark cave": "黑暗洞穴",
    "grasslands cave": "草原洞穴",
    "macaque den": "猕猴巢穴",
    "mud hut": "泥屋",
    "plane crash": "坠机点",
    "sea cave": "海蚀洞",
    "shed": "棚屋",
    "stone hut": "石屋",
    "tidal cave": "潮汐洞穴",
    "crystal chamber": "水晶洞室",
    "damp chamber": "潮湿洞室",
    "darkness": "黑暗",
    "flooded chamber": "积水洞室",
    "high chamber": "高洞室",
    "medium chamber": "中洞室",
    "low chamber": "低洞室",
    "narrow tunnel": "狭窄隧道",
    "tunnel": "隧道",
    "bat colony": "蝙蝠群",
    "brimstone vent": "硫磺喷口",
    "collapsed tunnel entrance": "坍塌隧道口",
    "copper vein": "铜矿脉",
    "debris": "残骸",
    "dry acid lake": "干涸酸湖",
    "dry cave pond": "干涸洞池",
    "dry puddle": "干涸水洼",
    "flooded tide pool": "涨潮潮池",
    "hole": "洞口",
    "narrow passage": "狭窄通道",
    "seawater": "海水",
    "shaft": "竖井",
    "shipwreck": "沉船",
    "skeleton": "骸骨",
    "wall scratchings": "墙上刻痕",
    "sea": "海",
    "sand": "沙子",
    "coconut palms": "椰子树",
    "trees": "树木",
    "dense trees": "密林",
    "vines": "藤蔓",
    "leaf litter": "落叶",
    "stone outcrops": "露岩",
    "cliffs": "悬崖",
    "shallow pools": "浅水池",
    "mangrove roots": "红树根",
    "flooded mud": "淹水泥地",
    "palm fronds": "棕榈叶",
    "rain puddles": "雨水洼",
    "sago palms": "西米棕榈",
    "deep shade": "深荫",
    "acid shore": "酸湖岸",
    "seagull nests": "海鸥巢",
    "grass": "草地",
    "small trees": "小树",
    "open sun": "烈日空地",
    "high cliffs": "高崖",
    "dry grass": "干草",
    "wild yams": "野山药",
    "hot ground": "热地面",
    "hole": "洞口",
    "fence": "围栏",
    "trampled grass": "踩踏草地",
    "floating debris": "漂浮残骸",
    "darkness": "黑暗",
    "bat colony": "蝙蝠群",
    "storage shelves": "储物架",
    "cave puddle": "洞穴水洼",
    "debris": "残骸",
    "shelter walls": "遮蔽墙",
    "crystals": "水晶",
    "shaft": "竖井",
    "narrow passage": "狭窄通道",
    "copper vein": "铜矿脉",
    "dry mud": "干泥",
    "skeleton": "骸骨",
    "wall scratchings": "墙上刻痕",
    "brimstone vent": "硫磺喷口",
    "seawater": "海水",
    "fish": "鱼",
    "unsafe water": "不安全的水",
    "clean water": "净水",
    "raw fish": "生鱼",
    "cooked fish": "熟鱼",
    "bandage leaves": "绷带叶",
    "ash": "灰烬",
    "charcoal": "木炭",
    "coconut": "椰子",
    "sticks": "树枝",
    "leaves": "叶子",
    "vine": "藤条",
    "stones": "石头",
    "sharp stone": "锋利石片",
    "sand castle": "沙堡",
    "fire": "火堆",
    "shelter": "庇护所",
    "raincatcher": "接雨器",
    "basket": "篮子",
    "luggage": "行李",
    "storage chest": "储物箱",
    "supply chest": "补给箱",
    "tent": "帐篷",
    "trunk": "大箱子",
    "empty crop plot": "空农田",
    "banana tree": "香蕉树",
    "large tree": "大树",
    "small tree": "小树",
    "palm bush": "棕榈灌木",
    "palm tree": "棕榈树",
    "wild yam": "野山药",
    "fish trap": "捕鱼陷阱",
    "snare trap": "套索陷阱",
    "campfire": "营火",
    "drying rack": "晾晒架",
    "leaf bed": "叶床",
    "mud deposit": "泥土堆",
    "rain catcher": "接雨器",
    "salt bed": "盐床",
    "seagull nest": "海鸥巢",
    "solar still": "太阳能蒸馏器",
    "water filter": "滤水器",
    "well": "井",
}
ZH_ALIASES = {value: key for key, value in OBJECT_NAMES_ZH.items()}
FEATURE_DESCRIPTIONS = {
    "en": {
        "sea": "open salt water",
        "sand": "warm pale sand",
        "coconut palms": "shade and coconuts",
        "trees": "dense tropical trees",
        "dense trees": "thick tropical growth",
        "vines": "long flexible vines",
        "leaf litter": "damp leaves and forest debris",
        "stone outcrops": "hard exposed stone",
        "cliffs": "steep rocky faces",
        "shallow pools": "shallow tidal pools",
        "mangrove roots": "twisted roots in brackish water",
        "flooded mud": "wet mud under shallow water",
        "palm fronds": "broad fronds useful for cover",
        "rain puddles": "rain-fed puddles of unsafe water",
        "sago palms": "wetland palms with useful leaves",
        "deep shade": "cool dim cover under the canopy",
        "acid shore": "caustic mineral shore",
        "seagull nests": "noisy nests on exposed rock",
        "grass": "open tropical grass",
        "small trees": "thin trees and scrub",
        "open sun": "exposed heat and glare",
        "high cliffs": "steep high rock faces",
        "dry grass": "dry grass and brittle stems",
        "wild yams": "hidden edible roots",
        "hot ground": "warm volcanic ground",
        "hole": "a dark opening downward",
        "fence": "rough animal fencing",
        "trampled grass": "flattened grass underfoot",
        "floating debris": "driftwood and wreckage",
        "darkness": "lightless interior space",
        "bat colony": "restless bats overhead",
        "storage shelves": "old shelves and storage space",
        "cave puddle": "standing cave water",
        "debris": "scattered useful debris",
        "shelter walls": "weather-blocking walls",
        "crystals": "sharp glittering crystals",
        "shaft": "vertical cave passage",
        "narrow passage": "tight rocky passage",
        "copper vein": "green-streaked ore in stone",
        "dry mud": "cracked dry mud",
        "skeleton": "old bones and scraps",
        "wall scratchings": "marks cut into the wall",
        "brimstone vent": "sulfurous volcanic vent",
        "seawater": "salt water filling the passage",
        "fish": "quick flashes under the water",
        "unsafe water": "water that needs treatment",
    },
    "zh": {
        "sea": "开阔的咸水",
        "sand": "温暖的浅色沙地",
        "coconut palms": "树荫和椰子",
        "trees": "浓密的热带树木",
        "dense trees": "茂密的热带植被",
        "vines": "又长又韧的藤蔓",
        "leaf litter": "潮湿的落叶和林地碎屑",
        "stone outcrops": "裸露的坚硬岩石",
        "cliffs": "陡峭的岩壁",
        "shallow pools": "浅浅的潮水池",
        "mangrove roots": "咸淡水中的扭曲树根",
        "flooded mud": "浅水下的湿泥地",
        "palm fronds": "可用于遮蔽的大棕榈叶",
        "rain puddles": "雨水形成的未处理水洼",
        "sago palms": "湿地里的西米棕榈",
        "deep shade": "树冠下阴凉昏暗的遮蔽",
        "acid shore": "带腐蚀性的矿物湖岸",
        "seagull nests": "裸岩上吵闹的海鸥巢",
        "grass": "开阔的热带草地",
        "small trees": "细小树木和灌丛",
        "open sun": "暴露的热气和眩光",
        "high cliffs": "高耸陡峭的岩壁",
        "dry grass": "干草和脆茎",
        "wild yams": "藏在地下的可食根茎",
        "hot ground": "温热的火山地面",
        "hole": "向下的黑暗洞口",
        "fence": "粗糙的动物围栏",
        "trampled grass": "被踩平的草地",
        "floating debris": "漂来的木料和残骸",
        "darkness": "没有光的内部空间",
        "bat colony": "头顶躁动的蝙蝠群",
        "storage shelves": "旧架子和储物空间",
        "cave puddle": "洞穴里的积水",
        "debris": "散落的可用残骸",
        "shelter walls": "能挡住天气的墙",
        "crystals": "锋利闪光的水晶",
        "shaft": "垂直洞穴通道",
        "narrow passage": "狭窄的岩石通道",
        "copper vein": "岩石中带绿色纹路的矿脉",
        "dry mud": "龟裂的干泥",
        "skeleton": "旧骨头和碎物",
        "wall scratchings": "刻在墙上的痕迹",
        "brimstone vent": "带硫磺味的火山喷口",
        "seawater": "灌入通道的咸海水",
        "fish": "水下快速闪动的鱼影",
        "unsafe water": "需要处理的水",
    },
}
PLACED_DESCRIPTIONS = {
    "en": {
        "fire": "active fire",
        "fire remnants": "cold ash and charcoal",
        "shelter": "rough protection from weather",
        "raincatcher": "collects rain into clean water",
        "sand castle": "a fragile little monument",
    },
    "zh": {
        "fire": "燃烧中的火堆",
        "fire remnants": "冷掉的灰烬和木炭",
        "shelter": "抵挡天气的简陋庇护",
        "raincatcher": "把雨水收集成净水",
        "sand castle": "脆弱的小小纪念物",
    },
}
ITEM_DESCRIPTIONS = {
    "en": {
        "coconut": "fresh food and drink",
        "sticks": "dry fuel and building material",
        "leaves": "broad leaves for crafting",
        "vine": "flexible natural cordage",
        "stones": "hard stones for tools",
        "wood": "solid fuel and building material",
        "long stick": "long straight building material",
        "heavy stone": "large stone that may be useful later",
        "flint": "sharp stone useful for tools and sparks",
        "flint slab": "flat flint piece for future crafting",
        "obsidian": "glassy volcanic stone",
        "sulphurous stone": "brimstone-rich volcanic stone",
        "pretty seashells": "small shells good for morale",
        "guano": "mineral-rich droppings",
        "bugs": "small edible insects",
        "crab": "small coastal crab",
        "prawns": "small shellfish",
        "assorted mushrooms": "mixed wild mushrooms",
        "sharp stone": "a chipped cutting tool",
        "bandage leaves": "soft medicinal leaves",
        "ash": "powdery fire remains",
        "charcoal": "blackened fuel remains",
        "unsafe water": "untreated water",
        "clean water": "drinkable water",
    },
    "zh": {
        "coconut": "新鲜的食物和饮水",
        "sticks": "干燥的燃料和建材",
        "leaves": "可用于制作的宽叶",
        "vine": "柔韧的天然绳材",
        "stones": "可制工具的硬石头",
        "sharp stone": "打制出的切割工具",
        "bandage leaves": "柔软的药用叶子",
        "ash": "粉末状的火堆残留",
        "charcoal": "烧黑的燃料残留",
        "unsafe water": "未经处理的水",
        "clean water": "可以饮用的水",
    },
}
ACTION_NAMES_ZH = {
    "boil water": "煮水",
    "build raincatcher": "建造接雨器",
    "build shelter": "建造庇护所",
    "cancel": "取消",
    "cook fish": "烤鱼",
    "craft sharp stone": "制作锋利石片",
    "drink": "喝水",
    "drop": "放下",
    "eat": "进食",
    "explore": "探索",
    "fish": "捕鱼",
    "forage": "觅食",
    "gather": "收集",
    "leisure": "休闲",
    "move": "移动",
    "pick up": "捡起",
    "rest": "休息",
    "start fire": "生火",
    "swim": "游泳",
    "tend fire": "照看火堆",
    "treat wound": "处理伤口",
    "wash": "清洗",
}
TRANSLATIONS = {
    "en": {
        "players": "Players",
        "world": "World",
        "online": "online",
        "thirst": "thirst",
        "hunger": "hunger",
        "fatigue": "fatigue",
        "health": "health",
        "morale": "morale",
        "stress": "stress",
        "weather": "weather",
        "light": "light",
        "paused": "paused",
        "none": "none",
        "global": "Global",
        "scene": "Scene",
        "inventory": "Inventory",
        "empty_inventory": "empty",
        "commands": "Commands",
        "no_commands": "No matching commands",
        "placeholder": "chat, /forage, /explore, /move rocks, /pick up coconut, /save, /exit",
        "unknown_command": "unknown command",
        "client_error": "client error",
        "saved_exiting": "saved; exiting",
    },
    "zh": {
        "players": "玩家",
        "world": "世界",
        "online": "在线",
        "thirst": "口渴",
        "hunger": "饥饿",
        "fatigue": "疲劳",
        "health": "生命",
        "morale": "士气",
        "stress": "压力",
        "weather": "天气",
        "light": "光线",
        "paused": "暂停",
        "none": "无",
        "global": "全局",
        "scene": "现场",
        "inventory": "背包",
        "empty_inventory": "空",
        "commands": "命令",
        "no_commands": "没有匹配的命令",
        "placeholder": "聊天，/forage，/explore，/move rocks，/pick up coconut，/save，/exit",
        "unknown_command": "未知命令",
        "client_error": "客户端错误",
        "saved_exiting": "已保存；正在退出",
    },
}


def ui_text(key: str, lang: str = "en") -> str:
    return TRANSLATIONS[lang][key]


def object_name(name: str, lang: str = "en") -> str:
    return OBJECT_NAMES_ZH.get(name, name) if lang == "zh" else name


def canonical_object_name(name: str) -> str:
    return ZH_ALIASES.get(name, name)


def localized_action_name(action: str, lang: str = "en") -> str:
    return ACTION_NAMES_ZH.get(action, action) if lang == "zh" else action


def command_description(command: str, lang: str = "en") -> str:
    descriptions = COMMAND_DESCRIPTIONS.get(lang, COMMAND_DESCRIPTIONS["en"])
    fallback = COMMAND_DESCRIPTIONS["en"].get(command, "start this action")
    return descriptions.get(command, fallback)


def feature_description(feature: str, resource_notes: list[str], lang: str = "en") -> str:
    base = FEATURE_DESCRIPTIONS.get(lang, FEATURE_DESCRIPTIONS["en"]).get(feature, ui_text("none", lang))
    return "; ".join([base, *resource_notes])


def resource_description(item: str, resource: dict[str, Any], lang: str = "en") -> str:
    name = object_name(item, lang)
    if resource.get("infinite"):
        return f"{name} source: infinite" if lang == "en" else f"{name}来源：无限"
    qty = int(resource.get("qty", 0))
    capacity = int(resource.get("capacity", qty))
    regen_days = int(resource.get("regen_minutes", 0)) // 1440
    if lang == "zh":
        regrow = f"；每 {regen_days} 天再生" if regen_days else ""
        return f"{name}：{qty}/{capacity} 可用{regrow}"
    regrow = f"; regrows every {regen_days} days" if regen_days else ""
    return f"{name}: {qty}/{capacity} available{regrow}"


def placed_description(obj: dict[str, Any], lang: str = "en") -> str:
    kind = str(obj["kind"])
    base = PLACED_DESCRIPTIONS.get(lang, PLACED_DESCRIPTIONS["en"]).get(kind, "present in the scene" if lang == "en" else "在现场")
    if kind == "fire":
        fuel = int(obj.get("fuel", 0))
        return f"{base} with fuel {fuel}" if lang == "en" else f"{base}，燃料 {fuel}"
    if kind == "raincatcher" and obj.get("data", {}).get("rain_minutes"):
        rain_minutes = int(obj["data"]["rain_minutes"])
        return f"{base}; {rain_minutes} rain minutes stored" if lang == "en" else f"{base}；已积累 {rain_minutes} 分钟雨水"
    return base


def location_card_description(card: str, lang: str = "en") -> str:
    description = str(LOCATION_CARD_DEFS.get(card, {}).get("description") or "present in this area")
    if lang == "zh":
        return f"{object_name(card, 'zh')}位置卡"
    return description


def item_description(stack: dict[str, Any], lang: str = "en") -> str:
    item = str(stack["item"])
    age = int(stack.get("age_minutes", 0))
    spoil_minutes = {"raw fish": 720, "cooked fish": 1440}.get(item)
    if spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        ratio = age / spoil_minutes
        if lang == "zh":
            freshness = "新鲜" if ratio < 1 / 3 else "半新鲜" if ratio < 2 / 3 else "快变质"
            return f"{freshness}；{hours_left} 小时后腐坏"
        freshness = "fresh" if ratio < 1 / 3 else "half fresh" if ratio < 2 / 3 else "near spoiling"
        return f"{freshness}; spoils in {hours_left}h"
    if item in {"clean water", "unsafe water"} and stack.get("exposed", True):
        hours_left = max(0, (360 - age + 59) // 60)
        if lang == "zh":
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；暴露放置，约 {hours_left} 小时后蒸发"
        return f"{ITEM_DESCRIPTIONS['en'][item]}; exposed, evaporates in about {hours_left}h"
    return ITEM_DESCRIPTIONS.get(lang, ITEM_DESCRIPTIONS["en"]).get(item, "ordinary object" if lang == "en" else "普通物品")


def localize_event(event: str, lang: str = "en") -> str:
    if lang != "zh":
        return event
    if match := re.fullmatch(r"Day (\d+) begins\.", event):
        return f"第 {match[1]} 天开始了。"
    if match := re.fullmatch(r"(.+) started (.+)\.", event):
        return f"{match[1]} 开始{localized_action_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) completed (.+)\.", event):
        return f"{match[1]} 完成{localized_action_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) discovered (.+)\.", event):
        return f"{match[1]} 发现了{object_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"Raw fish spoiled at (.+)\.", event):
        return f"生鱼在{object_name(match[1], 'zh')}腐坏了。"
    if match := re.fullmatch(r"Cooked fish spoiled at (.+)\.", event):
        return f"熟鱼在{object_name(match[1], 'zh')}腐坏了。"
    if match := re.fullmatch(r"Exposed (.+) evaporated at (.+)\.", event):
        return f"暴露的{object_name(match[1], 'zh')}在{object_name(match[2], 'zh')}蒸发了。"
    return event


def action_feedback_event(msg: dict[str, Any], player_name: str) -> dict[str, Any] | None:
    del player_name
    if msg.get("type") != "start_action":
        return None
    action = str(msg.get("action") or "").strip()
    if not action:
        return None
    total = ACTION_DURATIONS.get(action, 0)
    return {"name": action, "remaining_minutes": total, "total_minutes": total}


def _ongoing_action_line(action: dict[str, Any], player_name: str, lang: str, spinner_frame: int) -> str:
    frame = SPINNER_FRAMES[spinner_frame % len(SPINNER_FRAMES)]
    name = str(action.get("name") or "")
    remaining = int(action.get("remaining_minutes", 0))
    if lang == "zh":
        return f"{frame} {player_name} 正在{localized_action_name(name, 'zh')}… 剩余 {remaining} 分钟"
    gerunds = {"explore": "exploring", "move": "moving", "swim": "swimming", "fish": "fishing", "wash": "washing"}
    verb = gerunds.get(name, f"{name}ing")
    return f"{frame} {player_name} {verb}… {remaining}m left"


def _without_started_event_for_active_action(events: list[str], active_action: dict[str, Any] | None, player_name: str | None) -> list[str]:
    if not active_action or not player_name:
        return events
    started = f"{player_name} started {active_action.get('name')}."
    return [event for event in events if event != started]


def command_choices(snapshot: dict[str, Any], player_name: str | None = None) -> list[str]:
    choices: list[str] = []
    players = snapshot.get("players", {})
    current_player = players.get(player_name) if player_name else None
    if current_player is None:
        current_player = next((p for p in players.values() if p.get("connected")), next(iter(players.values()), {})) if players else {}
    current_location = str(current_player.get("location") or "")
    locations = snapshot.get("locations", {})
    loc = locations.get(current_location, {}) if current_location else {}

    for action in available_actions_for_snapshot(snapshot, player_name):
        if action == "move":
            destinations = move_destinations_for_snapshot(snapshot, player_name)
            choices.extend(f"/move {name}" for name in destinations)
            choices.append("/move <location>")
        elif action == "pick up":
            choices.extend(f"/pick up {stack.get('item')}" for stack in reversed(loc.get("ground", [])) if stack.get("item"))
            choices.append("/pick up <item>")
        elif action == "drop":
            choices.extend(f"/drop {stack.get('item')}" for stack in reversed(current_player.get("carried", [])) if stack.get("item"))
            choices.append("/drop <item>")
        elif action in {"forage", "gather"}:
            choices.extend(
                f"/{action} {item}"
                for item, resource in loc.get("resources", {}).items()
                if resource.get("action", action) == action and (resource.get("infinite") or int(resource.get("qty", 0)) > 0)
            )
            choices.append(f"/{action}")
        else:
            choices.append(f"/{action}")
    return list(dict.fromkeys(choices + CLIENT_COMMANDS))


class CommandMenuState:
    def __init__(self, choices: list[str] | None = None):
        self.choices = list(dict.fromkeys(choices or []))
        self.matches: list[str] = []
        self.index = 0
        self.query = ""

    def set_choices(self, choices: list[str]) -> None:
        self.choices = list(dict.fromkeys(choices))
        self.update(self.query)

    def update(self, query: str) -> None:
        self.query = query
        if not query.startswith("/"):
            self.matches = []
            self.index = 0
            return
        self.matches = [choice for choice in self.choices if choice.startswith(query)]
        self.index = min(self.index, max(0, len(self.matches) - 1))

    @property
    def selected(self) -> str | None:
        if not self.matches:
            return None
        return self.matches[self.index]

    def move_down(self) -> None:
        if self.matches:
            self.index = (self.index + 1) % len(self.matches)

    def move_up(self) -> None:
        if self.matches:
            self.index = (self.index - 1) % len(self.matches)

    def completion_value(self) -> str | None:
        selected = self.selected
        if selected is None:
            return None
        if "<" in selected:
            return selected.split("<", 1)[0]
        return selected

    def description_for(self, choice: str, lang: str = "en") -> str:
        command = choice.removeprefix("/")
        if " <" in command:
            command = command.split(" <", 1)[0]
        elif command.startswith("move "):
            command = "move"
        elif command.startswith("pick up "):
            command = "pick up"
        elif command.startswith("drop "):
            command = "drop"
        return command_description(command, lang)

    def render(self, lang: str = "en") -> str:
        if not self.query.startswith("/"):
            return ""
        if not self.matches:
            return ui_text("no_commands", lang)
        lines = [f"{ui_text('commands', lang)} ({len(self.matches)}):"]
        start = self.index - COMMAND_HELP_VISIBLE_MATCHES // 2
        start = max(0, min(start, len(self.matches) - COMMAND_HELP_VISIBLE_MATCHES))
        visible = self.matches[start : start + COMMAND_HELP_VISIBLE_MATCHES]
        if start > 0:
            lines.append(f"  ↑ {start} more")
        for offset, choice in enumerate(visible):
            idx = start + offset
            marker = "›" if idx == self.index else " "
            lines.append(f"{marker} {choice} — {self.description_for(choice, lang)}")
        remaining = len(self.matches) - start - len(visible)
        if remaining > 0:
            lines.append(f"  ↓ {remaining} more")
        return "\n".join(lines)


def command_input_key_effect(menu: CommandMenuState, key: str, value: str) -> tuple[str, bool]:
    if not value.strip().startswith("/"):
        return value, False
    if key in {"escape", "esc"}:
        menu.update("")
        return "", True
    if key == "down":
        menu.move_down()
        return value, True
    if key == "up":
        menu.move_up()
        return value, True
    if key == "tab" and menu.selected:
        completion = menu.completion_value()
        if completion and value.strip() != menu.selected:
            menu.update(completion)
            return completion, True
        return value, True
    return value, False


def should_focus_command_input(key: str) -> bool:
    return key not in {"pageup", "pagedown", "home", "end", "ctrl+c"}


def command_to_message(text: str, snapshot: dict[str, Any], player_name: str | None = None) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if not text.startswith("/"):
        return {"type": "chat", "text": text}

    command = text[1:].strip()
    if command == "cancel":
        return {"type": "cancel_action"}
    if command == "exit":
        return {"type": "exit"}
    if command in {"inspect", "pause", "resume", "save"}:
        return {"type": command}
    if command == "move":
        return {"type": "start_action", "action": "move", "args": {}}
    if command.startswith("move "):
        destination = canonical_object_name(command.removeprefix("move ").strip())
        neighbors = move_neighbors_for_snapshot(snapshot, player_name)
        destinations = move_destinations_for_snapshot(snapshot, player_name)
        if neighbors is not None and destination not in destinations:
            return None
        location = snapshot.get("locations", {}).get(destination)
        if location is not None and not location.get("discovered", True):
            return None
        return {"type": "start_action", "action": "move", "args": {"location": destination}}
    if command in {"pick up", "pickup"}:
        return {"type": "start_action", "action": "pick up", "args": {}}
    if command.startswith("pick up "):
        return {"type": "start_action", "action": "pick up", "args": {"item": canonical_object_name(command.removeprefix("pick up ").strip())}}
    if command.startswith("pickup "):
        return {"type": "start_action", "action": "pick up", "args": {"item": canonical_object_name(command.removeprefix("pickup ").strip())}}
    if command == "drop":
        return {"type": "start_action", "action": "drop", "args": {}}
    if command.startswith("drop "):
        return {"type": "start_action", "action": "drop", "args": {"item": canonical_object_name(command.removeprefix("drop ").strip())}}
    if command.startswith("forage "):
        return {"type": "start_action", "action": "forage", "args": {"item": canonical_object_name(command.removeprefix("forage ").strip())}}
    if command.startswith("gather "):
        return {"type": "start_action", "action": "gather", "args": {"item": canonical_object_name(command.removeprefix("gather ").strip())}}
    if command in available_actions_for_snapshot(snapshot, player_name) or command in ACTION_DURATIONS:
        return {"type": "start_action", "action": command, "args": {}}
    return None


def available_actions_for_snapshot(snapshot: dict[str, Any], player_name: str | None = None) -> list[str]:
    if player_name:
        return list(snapshot.get("players", {}).get(player_name, {}).get("available_actions", []))
    return list(snapshot.get("available_actions", []))


def move_destinations_for_snapshot(snapshot: dict[str, Any], player_name: str | None = None) -> list[str]:
    neighbors = move_neighbors_for_snapshot(snapshot, player_name)
    locations = snapshot.get("locations", {})
    if neighbors is not None:
        return [
            name
            for name in neighbors
            if name in locations and locations[name].get("discovered", True)
        ]
    current_location = current_location_for_snapshot(snapshot, player_name)
    return [
        name
        for name, location in locations.items()
        if name != current_location and location.get("discovered", True)
    ]


def move_neighbors_for_snapshot(snapshot: dict[str, Any], player_name: str | None = None) -> list[str] | None:
    current_location = current_location_for_snapshot(snapshot, player_name)
    locations = snapshot.get("locations", {})
    loc = locations.get(current_location, {}) if current_location else {}
    neighbors = loc.get("neighbors")
    return neighbors if isinstance(neighbors, list) else None


def current_location_for_snapshot(snapshot: dict[str, Any], player_name: str | None = None) -> str:
    players = snapshot.get("players", {})
    current_player = players.get(player_name) if player_name else None
    if current_player is None:
        current_player = next((p for p in players.values() if p.get("connected")), next(iter(players.values()), {})) if players else {}
    return str(current_player.get("location") or "")


def _stat_danger(name: str, value: int) -> int:
    return value if name == "stress" else 100 - value


def format_players_panel(snapshot: dict[str, Any], player_name: str, lang: str = "en") -> str:
    current_player = snapshot["players"][player_name]
    name = str(current_player.get("name") or player_name or "Player")
    status = ui_text("online", lang) if current_player.get("connected") else "offline"
    lines = [f"{name} ({status}) @ {object_name(str(current_player.get('location')), lang)}"]
    needs = current_player.get("needs", {})
    stats = sorted(
        [(key, int(needs.get(key, 0))) for key in ["health", "hunger", "thirst", "fatigue", "morale", "stress"]],
        key=lambda item: (-_stat_danger(*item), item[0]),
    )
    width = max(len(ui_text(key, lang)) for key, _ in stats)
    lines.extend(f"  {ui_text(key, lang):<{width}} {value}" for key, value in stats)
    return "\n".join(lines)


def format_inventory_panel(snapshot: dict[str, Any], player_name: str, lang: str = "en") -> str:
    player = snapshot["players"][player_name]
    lines = [ui_text("inventory", lang)]
    if not player.get("carried"):
        lines.append(f"  {ui_text('empty_inventory', lang)}")
    else:
        for stack in reversed(player["carried"]):
            item = str(stack["item"])
            lines.append(f"  {stack['qty']} {object_name(item, lang)}")
    return "\n".join(lines)


def format_world_panel(snapshot: dict[str, Any], player_name: str, lang: str = "en") -> str:
    player = snapshot["players"][player_name]
    current = player["location"]
    minute = int(snapshot.get("minute", 0))
    if lang == "zh":
        clock = f"第 {snapshot.get('day')} 天 {minute // 60:02d}:{minute % 60:02d}"
    else:
        clock = f"Day {snapshot.get('day')} {minute // 60:02d}:{minute % 60:02d}"
    current_loc = snapshot["locations"][current]
    scene_lines = [f"{ui_text('scene', lang)}: {object_name(current, lang)}"]
    for feature in current_loc["features"]:
        feature = str(feature)
        resource_notes = [
            resource_description(str(item), resource, lang)
            for item, resource in current_loc["resources"].items()
            if resource.get("source") == feature
        ]
        scene_lines.append(f"  {object_name(feature, lang)} — {feature_description(feature, resource_notes, lang)}")
    for card in current_loc.get("location_cards", []):
        card = str(card)
        scene_lines.append(f"  {object_name(card, lang)} — {location_card_description(card, lang)}")
    for obj in current_loc["placed"]:
        kind = str(obj["kind"])
        name = object_name(kind, lang)
        if kind == "fire":
            name = f"{name}(fuel {obj['fuel']})"
        scene_lines.append(f"  {name} — {placed_description(obj, lang)}")
    for stack in reversed(current_loc["ground"]):
        item = str(stack["item"])
        scene_lines.append(f"  {stack['qty']} {object_name(item, lang)} — {item_description(stack, lang)}")
    for name, location in sorted(snapshot["locations"].items()):
        if name != current and location.get("discovered", True):
            path = f"通往 {object_name(name, lang)} 的路" if lang == "zh" else f"path to {name}"
            route_description = "已发现的路线" if lang == "zh" else "discovered route"
            scene_lines.append(f"  {path} — {route_description}")
    if len(scene_lines) == 1:
        scene_lines.append(f"  {ui_text('none', lang)}")
    light = str(snapshot.get("lights", {}).get(current, snapshot.get("light", "daylight")))
    lines = [
        ui_text("global", lang),
        f"  {clock}",
        f"  {ui_text('weather', lang)}: {snapshot['weather']} {ui_text('light', lang)}: {light} {ui_text('paused', lang)}: {snapshot['paused']}",
        "",
        *scene_lines,
    ]
    return "\n".join(lines)


def format_event_log(
    events: list[str],
    lang: str = "en",
    active_action: dict[str, Any] | None = None,
    player_name: str | None = None,
    spinner_frame: int = 0,
) -> str:
    visible_events = _without_started_event_for_active_action([str(event) for event in events], active_action, player_name)
    lines = [localize_event(event, lang) for event in visible_events[-MAX_EVENT_LOG:]]
    if active_action and player_name:
        lines = [*lines[-(MAX_EVENT_LOG - 1) :], _ongoing_action_line(active_action, player_name, lang, spinner_frame)]
    return "\n".join(lines)


class NetworkClient:
    def __init__(self, host: str, port: int, name: str, invite: str | None = None):
        self.host = host
        self.port = port
        self.name = name
        self.invite = invite
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        await write_json_line(self.writer, {"type": "join", "name": self.name, "invite": self.invite})
        asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self.reader is not None
        while True:
            try:
                msg = await read_json_line(self.reader)
            except ValueError as exc:
                msg = {"type": "error", "message": str(exc)}
            if msg is None:
                await self.queue.put({"type": "exit", "message": "server disconnected"})
                return
            await self.queue.put(msg)

    async def send(self, msg: dict[str, Any]) -> None:
        if not self.writer:
            raise RuntimeError("not connected")
        await write_json_line(self.writer, msg)

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()


if App is not object:
    class SurvivalApp(App):  # type: ignore[misc]
        CSS = """
        Screen { layout: vertical; overflow: hidden; }
        #main { height: 1fr; }
        #player-scroll { width: 1fr; height: 1fr; border: round $primary; padding: 1; overflow-y: auto; }
        #world-scroll { width: 2fr; height: 1fr; border: round $primary; padding: 1; overflow-y: auto; }
        #inventory-scroll { width: 1fr; height: 1fr; border: round $primary; padding: 1; overflow-y: auto; }
        #players, #world, #inventory { width: 100%; }
        #log { height: 7; border: round $secondary; }
        #command-help { display: none; layer: overlay; dock: bottom; margin-bottom: 3; height: 25; width: 100%; border: round $accent; color: $text-muted; padding: 0 1; overflow: hidden; }
        #input { dock: bottom; border: round $accent; }
        #input:focus { border: round $accent; }
        """
        ENABLE_COMMAND_PALETTE = False
        BINDINGS: list[tuple[str, str, str]] = []

        def __init__(self, net: NetworkClient, lang: str = "en"):
            super().__init__()
            self.net = net
            self.lang = lang
            self.snapshot: dict[str, Any] = {}
            self.event_lines: list[str] = []
            self.pending_action: dict[str, Any] | None = None
            self.spinner_frame = 0
            self.command_menu = CommandMenuState(command_choices({}))

        def compose(self) -> ComposeResult:
            with Horizontal(id="main"):
                with VerticalScroll(id="player-scroll"):
                    yield Static(ui_text("players", self.lang), id="players")
                with VerticalScroll(id="world-scroll"):
                    yield Static(ui_text("world", self.lang), id="world")
                with VerticalScroll(id="inventory-scroll"):
                    yield Static(ui_text("inventory", self.lang), id="inventory")
            yield Static("", id="log")
            yield Static("", id="command-help")
            yield Input(
                placeholder=ui_text("placeholder", self.lang),
                suggester=SuggestFromList(command_choices({}), case_sensitive=False),
                id="input",
            )

        async def on_mount(self) -> None:
            await self.net.connect()
            self.query_one("#input", Input).focus()
            self.set_interval(0.1, self.drain_messages)

        async def drain_messages(self) -> None:
            while not self.net.queue.empty():
                msg = await self.net.queue.get()
                kind = msg.get("type")
                if kind in {"joined", "snapshot"}:
                    self.snapshot = msg.get("snapshot", {})
                    self.render_snapshot()
                elif kind == "exit":
                    self.record_event(str(msg.get("message") or ui_text("saved_exiting", self.lang)))
                    await self.net.close()
                    self.exit()
                elif kind in {"event", "chat", "error"}:
                    self.record_event(str(msg.get("message") or msg))
            self.render_event_log()

        def render_snapshot(self) -> None:
            self.query_one("#players", Static).update(format_players_panel(self.snapshot, self.net.name, self.lang))
            self.query_one("#world", Static).update(format_world_panel(self.snapshot, self.net.name, self.lang))
            self.query_one("#inventory", Static).update(format_inventory_panel(self.snapshot, self.net.name, self.lang))
            choices = command_choices(self.snapshot, self.net.name)
            self.command_menu.set_choices(choices)
            self.query_one("#input", Input).suggester = SuggestFromList(choices, case_sensitive=False)
            self.render_command_menu()
            self.event_lines = [str(entry) for entry in self.snapshot.get("event_log", [])[-MAX_EVENT_LOG:]]
            current_action = self.snapshot.get("players", {}).get(self.net.name, {}).get("current_action")
            self.pending_action = dict(current_action) if current_action else None
            self.render_event_log()

        def record_event(self, event: str) -> None:
            self.event_lines = [*self.event_lines, event][-MAX_EVENT_LOG:]
            self.render_event_log()

        def render_event_log(self) -> None:
            self.spinner_frame += 1
            self.query_one("#log", Static).update(
                format_event_log(
                    self.event_lines,
                    self.lang,
                    active_action=self.pending_action,
                    player_name=self.net.name,
                    spinner_frame=self.spinner_frame,
                )
            )

        def render_command_menu(self) -> None:
            text = self.command_menu.render(self.lang)
            help_widget = self.query_one("#command-help", Static)
            help_widget.update(text)
            help_widget.styles.display = "block" if text else "none"

        async def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
            input_widget = self.query_one("#input", Input)
            if input_widget.value.strip().startswith("/") and event.key in {"up", "down", "tab", "escape", "esc"}:
                value, handled = command_input_key_effect(self.command_menu, event.key, input_widget.value)
                if handled:
                    input_widget.value = value
                    input_widget.cursor_position = len(value)
                    input_widget.focus()
                    self.render_command_menu()
                    event.prevent_default()
                    event.stop()
                    return
            if event.key in {"up", "down"}:
                input_widget.focus()
                event.prevent_default()
                event.stop()
                return
            if should_focus_command_input(event.key) and self.focused is not input_widget:
                input_widget.focus()
                if getattr(event, "character", None):
                    input_widget.value += event.character
                    input_widget.cursor_position = len(input_widget.value)
                    event.prevent_default()
                    event.stop()
                    return
            value, handled = command_input_key_effect(self.command_menu, event.key, input_widget.value)
            if handled:
                if value != input_widget.value:
                    input_widget.value = value
                    input_widget.cursor_position = len(value)
                self.render_command_menu()
                event.prevent_default()
                event.stop()

        async def on_input_changed(self, event: Input.Changed) -> None:  # type: ignore[name-defined]
            self.command_menu.update(event.value.strip())
            self.render_command_menu()

        async def on_click(self, event) -> None:  # type: ignore[no-untyped-def]
            self.query_one("#input", Input).focus()

        async def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[name-defined]
            text = event.value.strip()
            event.input.value = ""
            self.command_menu.update("")
            self.render_command_menu()
            if not text:
                return
            try:
                msg = command_to_message(text, self.snapshot, self.net.name)
                if msg:
                    feedback = action_feedback_event(msg, self.net.name)
                    if feedback:
                        self.pending_action = feedback
                        self.render_event_log()
                    await self.net.send(msg)
                elif text.startswith("/"):
                    self.record_event(f"{ui_text('unknown_command', self.lang)}: {text}")
                else:
                    await self.net.send({"type": "chat", "text": text})
            except Exception as exc:
                self.record_event(f"{ui_text('client_error', self.lang)}: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Tropical Adventure terminal client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--name", required=True)
    parser.add_argument("--invite")
    parser.add_argument("--lang", choices=sorted(TRANSLATIONS), default="en", help="UI language: en or zh")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    net = NetworkClient(args.host, args.port, args.name, args.invite)
    if App is object:
        raise SystemExit("textual is not installed; run with project dependencies")
    SurvivalApp(net, lang=args.lang).run()


if __name__ == "__main__":
    main()
