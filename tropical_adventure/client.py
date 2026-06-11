from __future__ import annotations

import argparse
import asyncio
import contextlib
import re
import unicodedata
from typing import Any

from .content import (
    ACTION_DEFS as CONTENT_ACTION_DEFS,
    ACTION_DESCRIPTIONS as CONTENT_ACTION_DESCRIPTIONS,
    ACTION_NAMES_ZH as CONTENT_ACTION_NAMES_ZH,
    LOCATION_CARD_DEFS,
    RAFT_BUILD_STAGES,
    RAFT_EVENT_PASSING_SHIP,
    RAFT_RESCUE_DISTANCE,
    SPOIL_MINUTES,
    DEFAULT_ITEM_WEIGHT,
    ITEM_WEIGHTS,
    RAIN_COUNTER_MAX,
    RAIN_COUNTER_START,
    TINDER_LIGHTING_ACTIONS,
    TINDER_ITEMS,
    WEATHER_ALIASES,
    WEATHER_DEFS,
)
from .game import ACTION_DURATIONS, HAND_CARRIED_STORAGE_KINDS, PICKABLE_STORAGE_KINDS
from .models import MAX_EVENT_LOG, PLAYER_STAT_KEYS
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


CLIENT_COMMANDS = ["/cancel", "/crafts", "/exit", "/pause", "/recipes", "/resume", "/save"]
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
        "gather": "collect nearby natural materials",
        "leisure": "take a morale-restoring break",
        "move": "travel to a discovered location",
        "pause": "pause the world simulation",
        "pick up": "pick up an item from the current scene",
        "recipes": "show available crafts and missing recipe requirements",
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
        "gather": "收集附近的自然材料",
        "leisure": "放松休闲以恢复士气",
        "move": "前往已发现地点",
        "pause": "暂停世界模拟",
        "pick up": "从当前位置捡起物品",
        "recipes": "查看可制作物品和缺少的配方材料",
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
    "raft frame": "木筏框架",
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
    "fence": "围栏",
    "trampled grass": "踩踏草地",
    "floating debris": "漂浮残骸",
    "storage shelves": "储物架",
    "cave puddle": "洞穴水洼",
    "shelter walls": "遮蔽墙",
    "crystals": "水晶",
    "dry mud": "干泥",
    "fish": "鱼",
    "fire remnants": "火堆残迹",
    "unsafe water": "不安全的水",
    "clean water": "净水",
    "raw fish": "生鱼",
    "cooked fish": "熟鱼",
    "signaling mirror": "信号镜",
    "bandage leaves": "绷带叶",
    "ash": "灰烬",
    "charcoal": "木炭",
    "bird bones": "鸟骨",
    "bone hook": "骨钩",
    "bone splinters": "骨片",
    "coconut": "椰子",
    "coconut palm": "结果椰树",
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
    "exit": "出口",
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
OBJECT_NAMES_ZH.update(
    {
        "harvest coconuts": "采椰子",
        "forage tide pool": "搜寻潮池",
        "filter water": "过滤水",
        "crack coconut": "敲开椰子",
        "weave cord": "搓绳",
        "dry fish": "晾鱼",
        "craft leaf bed": "铺叶床",
        "build drying rack": "建造晾晒架",
        "build water filter": "建造滤水器",
        "build solar still": "建造太阳能蒸馏器",
        "coconut water": "椰子水",
        "coconut meat": "椰肉",
        "coconut shell": "椰壳",
        "coconut fish": "椰子鱼",
        "conch": "海螺",
        "conch meat": "海螺肉",
        "cooked conch meat": "熟海螺肉",
        "crushed conch": "碎海螺壳",
        "sago cake": "西米糕",
        "yam curry": "山药咖喱",
        "fried puffballs": "炒马勃菌",
        "bow drill": "弓钻",
        "fiber cord": "纤维绳",
        "hand drill": "手钻",
        "lit tinder": "点燃的火绒",
        "lit torch": "点燃的火把",
        "torch": "火把",
        "wood shavings": "木屑",
        "long stick": "长树枝",
        "dried fish": "鱼干",
        "raw meat": "生肉",
        "cooked meat": "熟肉",
        "dry leaves": "干叶",
        "dry leaf litter": "干落叶层",
        "dry palm litter": "干棕榈叶层",
        "prawns": "虾",
        "crab": "螃蟹",
        "seaweed": "海藻",
        "urchin": "海胆",
        "wood": "木材",
        "heavy stone": "重石",
        "flint": "燧石",
        "flint slab": "燧石板",
        "obsidian": "黑曜石",
        "sulphurous stone": "硫磺石",
        "pretty seashells": "漂亮贝壳",
        "feathers": "羽毛",
        "fish bait": "鱼饵",
        "fishing line": "鱼线",
        "fishing rod": "鱼竿",
        "flesh skin": "刮净兽皮",
        "fresh skin": "新鲜兽皮",
        "fleshed skin": "刮净兽皮",
        "guano": "鸟粪",
        "bugs": "虫子",
        "assorted mushrooms": "混合蘑菇",
        "yam": "山药",
        "aloe vera": "芦荟",
        "geode": "晶洞石",
        "calcite crystal": "方解石晶体",
        "copper ore": "铜矿石",
        "copper": "铜",
        "knife mold": "刀模具",
        "axe mold": "斧头模具",
        "shovel mold": "铲头模具",
        "spear mold": "矛头模具",
        "copper knife": "铜刀",
        "axe head": "斧头",
        "shovel head": "铲头",
        "spear head": "矛头",
        "copper axe": "铜斧",
        "copper shovel": "铜铲",
        "copper spear": "铜矛",
        "copper sheet": "铜板",
        "copper needle": "铜针",
        "copper bottle": "铜瓶",
        "copper jar": "铜罐",
        "log": "原木",
        "leather": "皮革",
        "palm weave": "棕榈编片",
        "woven backpack": "背篓",
        "plastic bottle": "塑料瓶",
        "drying rack": "晾晒架",
        "leaf bed": "叶床",
        "aloe vera leaf": "芦荟叶",
        "aloe gel": "芦荟凝胶",
        "lemongrass": "柠檬草",
        "ginger plant": "姜株",
        "ginger": "姜",
        "ginger tea": "姜茶",
        "spider lily": "蜘蛛兰",
        "spider lily leaves": "蜘蛛兰叶",
        "spider lily tea": "蜘蛛兰茶",
        "snakegrass patch": "蛇草丛",
        "snake grass": "蛇草",
        "snakegrass seeds": "蛇草种子",
        "bug repellent": "驱虫膏",
        "cooked yam": "熟山药",
        "banana": "香蕉",
        "nipa palm": "水椰",
        "nipa fruit": "水椰果",
        "nipa seeds": "水椰籽",
        "coffee bush": "咖啡灌木",
        "coffee berries": "咖啡果",
        "coffee beans": "咖啡豆",
        "roasted coffee beans": "烘焙咖啡豆",
        "coffee": "咖啡",
        "cinchona bark": "金鸡纳树皮",
        "cinchona tree": "金鸡纳树",
        "chilli plant": "辣椒株",
        "chillies": "辣椒",
        "jasmine flowers": "茉莉花",
        "jasmine tea": "茉莉茶",
        "assorted mushrooms patch": "混合蘑菇丛",
        "puffballs patch": "马勃菌丛",
        "puffballs": "马勃菌",
        "dried cinchona bark": "干金鸡纳树皮",
        "quinine powder": "奎宁粉",
        "magic mushroom patch": "迷幻菇丛",
        "magic mushrooms": "迷幻菇",
        "stone axe": "石斧",
        "sago palm": "西米棕榈",
        "felled sago palm": "倒下的西米棕榈",
        "palm fronds": "棕榈叶片",
        "sago seeds": "西米种子",
        "sago pith section": "西米髓心段",
        "sago sawdust": "西米木屑",
        "soaked sago": "湿西米",
        "sago pulp": "西米浆",
        "sago flour": "西米粉",
        "sago flatbread": "西米薄饼",
        "mud pile": "泥堆",
        "dirt pile": "土堆",
        "fine dirt": "细土",
        "clay": "黏土",
        "mud brick": "泥砖",
        "unfired clay bowl": "未烧黏土碗",
        "unfired clay jar": "未烧黏土罐",
        "unfired cooking pot": "未烧陶锅",
        "clay bowl": "陶碗",
        "clay jar": "陶罐",
        "cooking pot": "陶锅",
        "kiln": "窑",
        "advanced kiln": "高级窑",
        "forge": "锻炉",
        "water reservoir": "蓄水池",
        "well": "水井",
        "cistern": "水窖",
        "stone hut": "石屋",
        "digging stick": "挖掘杖",
        "rope": "绳子",
        "sand": "沙子",
        "quicklime": "生石灰",
        "mortar": "砂浆",
        "unfired clay vase": "未烧陶罐",
        "clay vase": "陶罐",
        "salt water": "盐水",
        "salt": "盐",
        "salted fish": "咸鱼",
        "salted meat": "咸肉",
        "signaling mirror": "信号镜",
        "dry puddle dirt": "干水洼土",
        "needle": "针",
    }
)
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
        "dry leaf litter": "dry leaves under forest cover",
        "dry palm litter": "dry palm leaves under the trees",
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
        "dry leaf litter": "林下干燥落叶",
        "dry palm litter": "树下干燥棕榈叶",
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
        "salt bed": "a shallow bed for evaporating seawater",
    },
    "zh": {
        "fire": "燃烧中的火堆",
        "fire remnants": "冷掉的灰烬和木炭",
        "shelter": "抵挡天气的简陋庇护",
        "raincatcher": "把雨水收集成净水",
        "sand castle": "脆弱的小小纪念物",
        "salt bed": "用于蒸发海水的浅盐床",
    },
}
PLACED_DESCRIPTIONS["en"].update(
    {
        "leaf bed": "a simple bed of leaves",
        "campfire": "a stone-ringed fire that burns longer",
        "fish trap": "a coastal trap soaking for seafood",
        "snare trap": "a small-animal snare",
        "drying rack": "hangs food to dry in the air",
        "water filter": "filters unsafe water with sand and charcoal",
        "solar still": "slowly condenses clean water in sun",
        "kiln": "an earthen kiln for firing clay vessels",
        "advanced kiln": "a hotter kiln for clay and copper work",
        "forge": "a high-heat furnace for smelting copper",
        "water reservoir": "a large open reservoir for rainwater",
        "well": "a dug source of unsafe groundwater",
        "cistern": "a sealed underground rainwater store",
        "basket": "a small woven storage basket",
        "woven backpack": "a worn storage basket with rope straps",
        "storage chest": "a heavy chest for base storage",
        "supply chest": "a reinforced chest for food and travel supplies",
        "shed": "woven palm shelter with storage space",
        "mud hut": "mud-brick shelter with good weather protection",
        "cellar": "cool underground storage room",
        "stone hut": "storm-resistant stone shelter",
        "raft frame": "unfinished escape raft frame",
        "raft": "seaworthy escape raft",
    }
)
PLACED_DESCRIPTIONS["zh"].update(
    {
        "leaf bed": "简易叶床",
        "campfire": "燃烧更持久的石圈营火",
        "fish trap": "正在海边浸泡的捕鱼陷阱",
        "snare trap": "小动物套索陷阱",
        "drying rack": "把食物挂起来风干",
        "water filter": "用沙子和木炭过滤不安全的水",
        "solar still": "在阳光下缓慢凝结净水",
        "kiln": "用于烧制陶器的土窑",
        "advanced kiln": "可用于陶器和铜冶炼的高温窑",
        "forge": "用于冶炼铜的高温炉",
        "water reservoir": "用于接雨和储水的大型开口蓄水池",
        "well": "会缓慢蓄积不安全地下水的水井",
        "cistern": "密封的地下雨水储仓",
        "basket": "小型棕榈编织储物篮",
        "woven backpack": "带绳背带的随身储物背篓",
        "storage chest": "沉重的基地储物箱",
        "supply chest": "适合食物和旅行补给的加固箱",
        "shed": "带储物空间的棕榈棚屋",
        "mud hut": "能良好遮风雨的泥砖屋",
        "cellar": "阴凉的地下储藏室",
        "stone hut": "能抵御风暴的石屋庇护",
        "raft frame": "尚未完成的逃生木筏框架",
        "raft": "可驶离小岛的逃生木筏",
    }
)
ITEM_DESCRIPTIONS = {
    "en": {
        "coconut": "fresh food and drink",
        "coconut palm": "climbable palm with reachable coconuts",
        "sticks": "dry fuel and building material",
        "leaves": "broad leaves for crafting",
        "vine": "flexible natural cordage",
        "stones": "hard stones for tools",
        "wood": "solid fuel and building material",
        "wood shavings": "dry tinder for lighting better fires",
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
        "raw meat": "fresh trap meat that should be cooked",
        "raw fish": "fresh fish that should be cooked or preserved",
        "cooked fish": "cooked fish ready to eat",
        "cooked meat": "cooked meat from a small catch",
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
        "coconut palm": "可攀爬并采到椰子的棕榈树",
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
ITEM_DESCRIPTIONS["en"].update(
    {
        "coconut water": "sweet drink sealed in a shell",
        "coconut meat": "white coconut flesh",
        "coconut shell": "a small natural cup",
        "coconut fish": "rich fish cooked with coconut and greens",
        "conch": "large shellfish with meat inside",
        "conch meat": "rubbery raw mollusk meat that should be cooked",
        "cooked conch meat": "cooked but still chewy mollusk meat",
        "crushed conch": "crushed shell temper for clay or quicklime",
        "sago cake": "soft steamed sago and coconut cake",
        "yam curry": "warm yam curry with coconut and chilies",
        "fried puffballs": "savory cooked wild mushrooms",
        "bird bones": "small bones that can be carved into hooks",
        "bone hook": "small carved hook for fishing gear",
        "bone splinters": "sharp bone pieces for hooks and fine craft",
        "feathers": "loose bird feathers for tinder and fish bait",
        "fish bait": "artificial bait that improves line fishing",
        "fishing line": "simple cord and hook for sea fishing",
        "fishing rod": "sturdier fishing tool that improves line fishing",
        "fiber cord": "twisted plant fiber cordage",
        "rope": "thick braided cord for heavy construction",
        "bow drill": "faster fire-starting tool that is gentler on your hands",
        "digging stick": "a stone-tipped digging tool",
        "hand drill": "simple fire-starting tool for tinder",
        "lit tinder": "small burning tinder that can start a fire",
        "lit torch": "portable flame for night travel and dark places",
        "sand": "clean sand for mortar and filters",
        "quicklime": "caustic lime for mortar and advanced crafting",
        "mortar": "wet stone-building mortar",
        "unfired clay vase": "large shaped clay vase that needs kiln firing",
        "clay vase": "large fired clay water container",
        "long stick": "straight pole for frames and racks",
        "dried fish": "preserved fish that lasts longer",
        "dry leaves": "dry leaf litter that works well as tinder",
        "prawns": "small tide-pool shellfish",
        "crab": "small coastal crab",
        "seaweed": "edible sea greens",
        "urchin": "spiny tide-pool food",
        "plastic bottle": "lightweight container material",
        "copper ore": "greenish ore for later metalwork",
        "copper": "smelted copper ready for casting",
        "knife mold": "tempered mud mold ready for a hot forge",
        "axe mold": "heavy tempered mold for casting an axe head",
        "shovel mold": "heavy tempered mold for casting a shovel head",
        "spear mold": "tempered mold for casting a spear head",
        "copper knife": "durable copper cutting and scraping tool",
        "axe head": "sharp copper axe head for lashing into a tool",
        "shovel head": "copper shovel head for a digging tool",
        "spear head": "durable copper spear head for a long weapon",
        "copper axe": "advanced chopping tool with a copper head",
        "copper shovel": "metal digging tool for wells, cisterns, mud, and sand",
        "copper spear": "long spear with a durable copper head",
        "copper sheet": "thin hammered copper for vessels and needles",
        "copper needle": "small copper sewing needle",
        "copper bottle": "sealed copper bottle for carrying water",
        "copper jar": "small sealed copper jar that can also cook",
        "log": "heavy building log for larger structures",
        "leather": "worked hide for durable construction",
        "fresh skin": "fresh hide that should be scraped before it rots",
        "fleshed skin": "scraped hide curing into leather",
        "palm weave": "woven palm mat for baskets, chests, and roofs",
        "basket": "woven palm basket for small storage",
        "woven backpack": "rope-backed woven basket for carrying supplies",
        "torch": "unlit portable torch with reusable fuel",
        "calcite crystal": "pale crystal from a cave",
        "aloe vera": "a living aloe plant with soothing leaves",
        "aloe vera leaf": "cool gel-filled leaf for skin care",
        "aloe gel": "processed soothing gel for burns, bites, and sun",
        "lemongrass": "edible citrus grass that lightly repels insects",
        "ginger plant": "wetland plant with medicinal roots",
        "ginger": "sharp medicinal root for stomach trouble",
        "ginger tea": "warm tea that settles nausea and digestion",
        "spider lily": "medicinal lily with antibiotic leaves",
        "spider lily leaves": "medicinal leaves for antibiotic tea",
        "spider lily tea": "bitter tea that supports fever and infection recovery",
        "snakegrass patch": "patch of fibrous grass for cordage and repellent",
        "snake grass": "fibrous grass for cordage and repellent",
        "snakegrass seeds": "small seeds from harvested snakegrass",
        "bug repellent": "plant salve that keeps biting insects away",
        "yam": "raw wild tuber that must be prepared",
        "cooked yam": "safe cooked wild yam",
        "banana": "sweet quick fruit",
        "nipa palm": "mangrove palm with edible fruit",
        "nipa fruit": "mangrove palm fruit with edible seeds inside",
        "nipa seeds": "soft edible nipa palm seeds",
        "coffee bush": "highland bush with coffee berries",
        "coffee berries": "fresh berries with beans inside",
        "coffee beans": "unroasted coffee beans",
        "roasted coffee beans": "roasted beans ready for brewing",
        "coffee": "bitter drink that fights fatigue",
        "cinchona bark": "fresh medicinal bark that can be dried for quinine",
        "dried cinchona bark": "dry bark ready to grind into quinine powder",
        "quinine powder": "bitter antimalarial medicine with stomach side effects",
        "chilli plant": "grassland plant with hot peppers",
        "chillies": "hot peppers with a harsh stimulant bite",
        "jasmine flowers": "fragrant flowers for relaxing tea",
        "jasmine tea": "gentle tea for stress and morale",
        "assorted mushrooms patch": "mixed wild mushroom patch",
        "puffballs": "mild edible wild mushrooms",
        "puffballs patch": "patch of edible puffball mushrooms",
        "magic mushroom patch": "patch of psychoactive mushrooms",
        "magic mushrooms": "psychoactive mushrooms that disturb clarity",
        "stone axe": "a lashed stone chopping tool",
        "sago palm": "wetland palm with starch-rich pith",
        "felled sago palm": "a cut palm ready to split for starch",
        "palm fronds": "broad palm leaves from a felled tree",
        "sago seeds": "seeds from a harvested sago palm",
        "sago pith section": "split palm pith ready for scraping",
        "sago sawdust": "starchy scrapings that need washing",
        "soaked sago": "wet sago mash that is unsafe unless processed",
        "sago pulp": "soft sago pulp that can dry into flour",
        "sago flour": "dry palm starch for cooking",
        "sago flatbread": "cooked sago bread, plain but filling",
        "mud pile": "workable wet mud for clay and bricks",
        "dirt pile": "loose dirt that can become mud or fine dirt",
        "fine dirt": "powdery dirt ready to mix into clay",
        "clay": "workable clay for construction",
        "mud brick": "tempered mud brick for larger builds",
        "unfired clay bowl": "shaped clay bowl that needs firing",
        "unfired clay jar": "shaped clay jar that needs kiln firing",
        "unfired cooking pot": "large shaped clay pot that needs kiln firing",
        "clay bowl": "small fired clay water and cooking bowl",
        "clay jar": "sealed fired clay liquid container",
        "cooking pot": "sealed fired clay pot for advanced cooking",
        "salt water": "seawater for salt making",
        "salt": "mineral salt for cooking and preserving",
        "salted fish": "salt-cured fish that lasts much longer",
        "salted meat": "salt-cured meat that lasts much longer",
        "signaling mirror": "polished emergency mirror for catching a ship's attention",
        "banana tree": "fruiting tree with a harvestable hand of bananas",
        "cinchona tree": "medicinal tree with bark for quinine",
        "dry puddle dirt": "loose dirt in a dried puddle",
        "large tree": "tree large enough to hew into a log",
        "mud deposit": "workable wet mud deposit",
        "needle": "sewing needle for leather and raft work",
        "seagull nest": "exposed nest with feathers and scraps",
        "skeleton": "old bones that can be worked into hooks",
        "storage chest": "heavy built chest for base storage",
        "supply chest": "reinforced chest for food and travel supplies",
        "wild yam": "wild tuber vine with toxic roots",
    }
)
ITEM_DESCRIPTIONS["zh"].update(
    {
        "wood": "结实的燃料和建材",
        "wood shavings": "适合点火的干木屑",
        "long stick": "可用于框架和架子的直长枝",
        "heavy stone": "以后可能有用的大石块",
        "flint": "适合制工具和打火的锋利燧石",
        "flint slab": "适合进一步加工的扁燧石片",
        "obsidian": "玻璃质火山石",
        "sulphurous stone": "富含硫磺的火山石",
        "pretty seashells": "能提振士气的小贝壳",
        "guano": "富含矿物质的鸟粪",
        "bugs": "可食用的小虫",
        "crab": "小型海岸螃蟹",
        "prawns": "小型贝类食物",
        "raw meat": "最好烤熟的新鲜陷阱肉",
        "raw fish": "最好烤熟或保存的新鲜鱼",
        "cooked fish": "可以直接食用的熟鱼",
        "cooked meat": "烤熟的小型猎物肉",
        "dry leaves": "适合点火的干燥落叶",
        "assorted mushrooms": "混合野生蘑菇",
        "coconut water": "封在壳里的清甜饮水",
        "coconut meat": "白色椰肉",
        "coconut shell": "天然小杯",
        "coconut fish": "用椰子和蔬菜煮出的浓郁鱼料理",
        "conch": "内含可食肉的大海螺",
        "conch meat": "有韧性的生贝肉，最好先烤熟",
        "cooked conch meat": "烤熟但仍有嚼劲的贝肉",
        "crushed conch": "可作陶土调和料或烧生石灰的碎贝壳",
        "sago cake": "用西米和椰肉蒸成的软糕",
        "yam curry": "加入椰肉和辣椒的热山药咖喱",
        "fried puffballs": "炒熟的鲜香野蘑菇",
        "bird bones": "可削成鱼钩的小鸟骨",
        "bone hook": "用于钓具的小骨钩",
        "bone splinters": "可制作鱼钩和细工的锋利骨片",
        "feathers": "可作火绒和鱼饵的散落羽毛",
        "fish bait": "能提高钓鱼上钩率的人工鱼饵",
        "fishing line": "由绳和鱼钩做成的简易钓线",
        "fishing rod": "更结实、上钩率更好的钓竿",
        "fiber cord": "搓成的植物纤维绳",
        "rope": "用于大型建造的粗编绳",
        "bow drill": "更快点火且更省手的取火工具",
        "digging stick": "带石刃的挖掘工具",
        "hand drill": "用于点燃火绒的简易取火工具",
        "lit tinder": "可用来引燃火堆的小团火绒",
        "lit torch": "可用于夜间行走和黑暗地点的随身火光",
        "sand": "可用于砂浆和过滤的干净沙子",
        "quicklime": "可制作砂浆和进阶材料的生石灰",
        "mortar": "用于石质建筑的湿砂浆",
        "unfired clay vase": "已经塑形但需要入窑烧制的大陶罐",
        "clay vase": "烧制好的大型储水陶罐",
        "dried fish": "更耐放的鱼干",
        "seaweed": "可食用海藻",
        "urchin": "带刺的潮池食物",
        "yam": "需要处理后食用的野生根茎",
        "aloe vera": "可用于护理的芦荟",
        "geode": "可能藏有晶体的石头",
        "calcite crystal": "洞穴里的浅色晶体",
        "copper ore": "可用于后续冶炼的绿色矿石",
        "copper": "可用于铸造的冶炼铜",
        "knife mold": "可放入高温锻炉的调和泥刀模具",
        "axe mold": "用于铸造斧头的厚重调和泥模具",
        "shovel mold": "用于铸造铲头的厚重调和泥模具",
        "spear mold": "用于铸造矛头的调和泥模具",
        "copper knife": "耐用的铜制切割和刮削工具",
        "axe head": "可绑成斧子的锋利铜斧头",
        "shovel head": "可制成挖掘工具的铜铲头",
        "spear head": "可绑成长矛的耐用铜矛头",
        "copper axe": "装有铜斧头的进阶砍伐工具",
        "copper shovel": "可用于水井、水窖、泥土和沙子的金属挖掘工具",
        "copper spear": "带耐用铜矛头的长矛",
        "copper sheet": "可加工容器和针的薄铜板",
        "copper needle": "小巧的铜制缝纫针",
        "copper bottle": "可携带水的密封铜瓶",
        "copper jar": "可做饭的小型密封铜罐",
        "log": "用于大型结构的沉重原木",
        "leather": "经过处理的耐用皮革",
        "fresh skin": "需要刮净否则会腐坏的新鲜兽皮",
        "fleshed skin": "正在风干成皮革的刮净兽皮",
        "palm weave": "可用于篮子、箱子和屋顶的棕榈编片",
        "basket": "可小量储物的棕榈编篮",
        "woven backpack": "带绳背带、可携带补给的编织背篓",
        "torch": "未点燃的可携带火把，保留剩余燃料",
        "plastic bottle": "轻便的容器材料",
        "aloe vera leaf": "含有清凉凝胶的护肤叶片",
        "aloe gel": "处理好的舒缓凝胶，可护理晒伤、虫咬和烧伤",
        "lemongrass": "带柑橘香的可食草，也能略微驱虫",
        "ginger": "辛辣药用根茎，可缓解胃部不适",
        "ginger tea": "能缓解恶心和消化问题的热姜茶",
        "spider lily": "可采叶制药茶的蜘蛛兰",
        "spider lily leaves": "可泡抗生素茶的药用叶片",
        "spider lily tea": "苦味药茶，帮助退热和抗感染",
        "snakegrass patch": "可收获纤维草的蛇草丛",
        "snake grass": "可搓绳并制作驱虫膏的纤维草",
        "snakegrass seeds": "采蛇草时得到的小种子",
        "bug repellent": "能驱赶叮咬昆虫的植物膏",
        "cooked yam": "处理并煮熟后的安全野山药",
        "banana": "清甜方便的水果",
        "nipa palm": "长在红树林里的水椰",
        "nipa fruit": "里面有可食籽的水椰果",
        "nipa seeds": "柔软可食的水椰籽",
        "coffee bush": "高地里的咖啡灌木",
        "coffee berries": "内含咖啡豆的新鲜咖啡果",
        "coffee beans": "还没烘焙的咖啡豆",
        "roasted coffee beans": "可用来冲煮的烘焙咖啡豆",
        "coffee": "苦味饮品，可以暂时抵抗疲劳",
        "cinchona bark": "可晒干制奎宁的药用鲜树皮",
        "dried cinchona bark": "可磨成奎宁粉的干树皮",
        "quinine powder": "苦味抗疟药，可能刺激肠胃",
        "chilli plant": "结辣椒的草地植物",
        "chillies": "刺激性很强的辣椒",
        "jasmine flowers": "芳香的茉莉花，可泡安神茶",
        "jasmine tea": "能缓解压力、提振士气的温和花茶",
        "assorted mushrooms patch": "混杂野蘑菇生长处",
        "puffballs patch": "马勃菌生长处",
        "puffballs": "温和可食的野生马勃菌",
        "magic mushroom patch": "迷幻菇生长处",
        "magic mushrooms": "会扰乱心智清晰度的迷幻菇",
        "stone axe": "绑扎好的石制砍伐工具",
        "sago palm": "可加工出西米淀粉的棕榈",
        "felled sago palm": "砍倒后可继续劈开的西米棕榈",
        "palm fronds": "砍树时得到的大棕榈叶片",
        "sago seeds": "采伐西米棕榈时得到的种子",
        "sago pith section": "可刮出淀粉木屑的西米髓心段",
        "sago sawdust": "需要洗去杂质的含淀粉木屑",
        "soaked sago": "湿润的西米糊，未处理时有风险",
        "sago pulp": "可晾干成西米粉的软浆",
        "sago flour": "可用来烤饼的干燥西米淀粉",
        "sago flatbread": "朴素但饱腹的西米薄饼",
        "mud pile": "可加工成黏土和泥砖的湿泥",
        "dirt pile": "可调成泥或碾成细土的松土",
        "fine dirt": "可拌成黏土的粉状细土",
        "clay": "可用于建造的可塑黏土",
        "mud brick": "调和后可用于大型建造的泥砖",
        "unfired clay bowl": "已经塑形但需要烧制的黏土碗",
        "unfired clay jar": "已经塑形但需要入窑烧制的黏土罐",
        "unfired cooking pot": "已经塑形但需要入窑烧制的大陶锅",
        "clay bowl": "烧制好的小陶碗，可盛水和做饭",
        "clay jar": "烧制好的带盖陶罐，可盛液体",
        "cooking pot": "烧制好的带盖陶锅，可用于进阶烹饪",
        "salt water": "可用于制盐的海水",
        "salt": "可烹饪和腌制的矿物盐",
        "salted fish": "更耐放的腌咸鱼",
        "salted meat": "更耐放的腌咸肉",
        "signaling mirror": "可向船只反光示意的应急镜",
        "banana tree": "长着可采香蕉串的果树",
        "cinchona tree": "树皮可制奎宁的药用树",
        "dry puddle dirt": "干水洼里的松土",
        "ginger plant": "根部有药用价值的湿地植物",
        "large tree": "可修整成原木的大树",
        "mud deposit": "可挖取加工的湿泥堆",
        "needle": "用于缝皮革和木筏部件的针",
        "seagull nest": "有羽毛和零碎材料的裸岩鸟巢",
        "skeleton": "可加工成鱼钩的旧骨头",
        "storage chest": "用于基地储物的沉重木箱",
        "supply chest": "适合食物和旅行补给的加固箱",
        "wild yam": "藏有有毒根茎的野山药藤",
    }
)
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
ACTION_NAMES_ZH.update(CONTENT_ACTION_NAMES_ZH)
COMMAND_DESCRIPTIONS["en"].update(CONTENT_ACTION_DESCRIPTIONS["en"])
COMMAND_DESCRIPTIONS["zh"].update(CONTENT_ACTION_DESCRIPTIONS["zh"])
WEATHER_NAMES_ZH = {
    "clear": "晴朗",
    "partially cloudy": "少云",
    "cloudy": "多云",
    "rain": "雨",
    "light rain": "小雨",
    "heavy rain": "大雨",
    "storm": "风暴",
}
TRANSLATIONS = {
    "en": {
        "players": "Players",
        "world": "World",
        "online": "online",
        "offline": "offline",
        "status_dead": "dead",
        "status_escaped": "escaped",
        "outcome": "Outcome",
        "win": "Victory",
        "loss": "Defeat",
        "escape_path": "Escape",
        "death_path": "Death",
        "raft_build": "Raft build",
        "raft_voyage": "Raft voyage",
        "passing_ship": "Passing ship",
        "thirst": "thirst",
        "hunger": "hunger",
        "fatigue": "fatigue",
        "health": "health",
        "morale": "morale",
        "stress": "stress",
        "hydration": "hydration",
        "satiation": "satiation",
        "stamina": "stamina",
        "calm": "calm",
        "wakefulness": "wakefulness",
        "comfort": "comfort",
        "dryness": "dryness",
        "cleanliness": "cleanliness",
        "wound_recovery": "wound recovery",
        "appetite": "appetite",
        "entertainment": "entertainment",
        "courage": "courage",
        "companionship": "companionship",
        "mental_clarity": "mental clarity",
        "altered_mind_stability": "altered mind stability",
        "mania_control": "mania control",
        "derealization_control": "derealization control",
        "mental_structure": "mental structure",
        "isolation_resilience": "isolation resilience",
        "healthy_weight": "healthy weight",
        "skin_integrity": "skin integrity",
        "tanning": "tanning",
        "foot_callouses": "foot callouses",
        "hand_callouses": "hand callouses",
        "eyesight": "eyesight",
        "sun_safety": "sun safety",
        "back_comfort": "back comfort",
        "bite_comfort": "bite comfort",
        "foot_health": "foot health",
        "hand_health": "hand health",
        "blood_volume": "blood volume",
        "bruise_recovery": "bruise recovery",
        "burn_recovery": "burn recovery",
        "eye_health": "eye health",
        "lung_health": "lung health",
        "heat_balance": "heat balance",
        "cold_balance": "cold balance",
        "blood_pressure_stability": "blood pressure",
        "parasite_control": "parasite control",
        "malaria_resistance": "malaria resistance",
        "infection_control": "infection control",
        "fever_control": "fever control",
        "stomach_stability": "stomach stability",
        "digestion": "digestion",
        "immunity": "immunity",
        "headache_comfort": "headache comfort",
        "analgesia_coverage": "analgesia coverage",
        "spider_lily_recovery": "spider lily recovery",
        "ginger_settledness": "ginger settledness",
        "antibiotic_coverage": "antibiotic coverage",
        "sobriety": "sobriety",
        "sodium_balance": "sodium balance",
        "quinine_safety": "quinine safety",
        "caffeine_balance": "caffeine balance",
        "capsaicin_cooling": "capsaicin cooling",
        "psilocybin_grounding": "psilocybin grounding",
        "jasmine_restfulness": "jasmine restfulness",
        "food_poisoning_recovery": "food poisoning recovery",
        "china_rose_balance": "china rose balance",
        "rice_tolerance": "rice tolerance",
        "venom_krait_resistance": "venom krait resistance",
        "heat_protection": "heat protection",
        "cold_protection": "cold protection",
        "sun_protection": "sun protection",
        "rain_protection": "rain protection",
        "bug_protection": "bug protection",
        "foot_protection": "foot protection",
        "armor": "armor",
        "coconut_appetite": "coconut appetite",
        "crustacean_appetite": "crustacean appetite",
        "mollusk_appetite": "mollusk appetite",
        "fish_appetite": "fish appetite",
        "bird_appetite": "bird appetite",
        "meat_appetite": "meat appetite",
        "reptile_appetite": "reptile appetite",
        "banana_appetite": "banana appetite",
        "fruit_appetite": "fruit appetite",
        "vegetable_appetite": "vegetable appetite",
        "sago_appetite": "sago appetite",
        "sugar_appetite": "sugar appetite",
        "rice_appetite": "rice appetite",
        "nut_appetite": "nut appetite",
        "ration_appetite": "ration appetite",
        "egg_appetite": "egg appetite",
        "dairy_appetite": "dairy appetite",
        "mushroom_appetite": "mushroom appetite",
        "yam_appetite": "yam appetite",
        "weather": "weather",
        "season": "season",
        "rain_counter": "rain counter",
        "rain_value": "rain",
        "sun_strength": "sun",
        "tide": "tide",
        "high_tide": "high",
        "low_tide": "low",
        "light": "light",
        "paused": "paused",
        "none": "none",
        "global": "Global",
        "scene": "Scene",
        "inventory": "Inventory",
        "empty_inventory": "empty",
        "survivor_here": "survivor here",
        "commands": "Commands",
        "no_commands": "No matching commands",
        "placeholder": "chat, /gather, /explore, /move 1(beach), /pick up 2(coconut) 1, /save, /exit",
        "unknown_command": "unknown command",
        "client_error": "client error",
        "saved_exiting": "saved; exiting",
    },
    "zh": {
        "players": "玩家",
        "world": "世界",
        "online": "在线",
        "offline": "离线",
        "status_dead": "死亡",
        "status_escaped": "已逃离",
        "outcome": "结局",
        "win": "胜利",
        "loss": "失败",
        "escape_path": "逃离",
        "death_path": "死亡",
        "raft_build": "木筏建造",
        "raft_voyage": "木筏航程",
        "passing_ship": "过往船只",
        "thirst": "口渴",
        "hunger": "饥饿",
        "fatigue": "疲劳",
        "health": "生命",
        "morale": "士气",
        "stress": "压力",
        "hydration": "水分",
        "satiation": "饱腹",
        "stamina": "体力",
        "calm": "镇定",
        "wakefulness": "清醒",
        "comfort": "舒适",
        "dryness": "干燥",
        "cleanliness": "清洁",
        "wound_recovery": "伤口恢复",
        "appetite": "食欲",
        "entertainment": "娱乐",
        "courage": "勇气",
        "companionship": "陪伴",
        "mental_clarity": "心智清晰",
        "altered_mind_stability": "心智状态稳定",
        "mania_control": "狂躁控制",
        "derealization_control": "现实感",
        "mental_structure": "心智稳定",
        "isolation_resilience": "孤立韧性",
        "healthy_weight": "健康体重",
        "skin_integrity": "皮肤完整",
        "tanning": "日晒适应",
        "foot_callouses": "脚部茧皮",
        "hand_callouses": "手部茧皮",
        "eyesight": "视力",
        "sun_safety": "晒伤恢复",
        "back_comfort": "背部舒适",
        "bite_comfort": "叮咬恢复",
        "foot_health": "脚部健康",
        "hand_health": "手部健康",
        "blood_volume": "血量",
        "bruise_recovery": "瘀伤恢复",
        "burn_recovery": "烧伤恢复",
        "eye_health": "眼部健康",
        "lung_health": "肺部健康",
        "heat_balance": "热平衡",
        "cold_balance": "冷平衡",
        "blood_pressure_stability": "血压稳定",
        "parasite_control": "寄生虫控制",
        "malaria_resistance": "疟疾抵抗",
        "infection_control": "感染控制",
        "fever_control": "发热控制",
        "stomach_stability": "胃部稳定",
        "digestion": "消化",
        "immunity": "免疫",
        "headache_comfort": "头痛缓解",
        "analgesia_coverage": "镇痛覆盖",
        "spider_lily_recovery": "蜘蛛兰恢复",
        "ginger_settledness": "姜效稳定",
        "antibiotic_coverage": "抗生素覆盖",
        "sobriety": "清醒",
        "sodium_balance": "钠平衡",
        "quinine_safety": "奎宁安全",
        "caffeine_balance": "咖啡因平衡",
        "capsaicin_cooling": "辣椒素冷却",
        "psilocybin_grounding": "裸盖菇素稳定",
        "jasmine_restfulness": "茉莉安神",
        "food_poisoning_recovery": "食物中毒恢复",
        "china_rose_balance": "朱槿平衡",
        "rice_tolerance": "稻米耐受",
        "venom_krait_resistance": "海蛇毒抵抗",
        "heat_protection": "防暑",
        "cold_protection": "保暖",
        "sun_protection": "防晒",
        "rain_protection": "防雨",
        "bug_protection": "防虫",
        "foot_protection": "护脚",
        "armor": "护甲",
        "coconut_appetite": "椰子食欲",
        "crustacean_appetite": "甲壳类食欲",
        "mollusk_appetite": "贝类食欲",
        "fish_appetite": "鱼类食欲",
        "bird_appetite": "鸟类食欲",
        "meat_appetite": "肉类食欲",
        "reptile_appetite": "爬行动物食欲",
        "banana_appetite": "香蕉食欲",
        "fruit_appetite": "水果食欲",
        "vegetable_appetite": "蔬菜食欲",
        "sago_appetite": "西米食欲",
        "sugar_appetite": "糖分食欲",
        "rice_appetite": "稻米食欲",
        "nut_appetite": "坚果食欲",
        "ration_appetite": "口粮食欲",
        "egg_appetite": "蛋类食欲",
        "dairy_appetite": "乳制品食欲",
        "mushroom_appetite": "蘑菇食欲",
        "yam_appetite": "山药食欲",
        "weather": "天气",
        "season": "季节",
        "rain_counter": "雨势计数",
        "rain_value": "雨量",
        "sun_strength": "日照",
        "tide": "潮汐",
        "high_tide": "涨潮",
        "low_tide": "退潮",
        "light": "光线",
        "paused": "暂停",
        "none": "无",
        "global": "全局",
        "scene": "现场",
        "inventory": "背包",
        "empty_inventory": "空",
        "survivor_here": "同伴在这里",
        "commands": "命令",
        "no_commands": "没有匹配的命令",
        "placeholder": "聊天，/gather，/explore，/move 1(beach)，/pick up 2(coconut) 1，/save，/exit",
        "unknown_command": "未知命令",
        "client_error": "客户端错误",
        "saved_exiting": "已保存；正在退出",
    },
}
OUTCOME_REASONS_ZH = {
    "dehydration": "脱水",
    "starvation": "饥饿",
    "dehydration and starvation": "脱水和饥饿",
    "injuries and exhaustion": "伤病和虚脱",
    "disease": "疾病",
    "rescued by passing ship": "被过往船只救起",
    "rescued after completing raft voyage": "完成木筏航程后获救",
}


def ui_text(key: str, lang: str = "en") -> str:
    return TRANSLATIONS[lang][key]


def object_name(name: str, lang: str = "en") -> str:
    if lang != "zh":
        return name
    if name.endswith("'s pack"):
        owner = name.removesuffix("'s pack")
        return f"{owner}的背包"
    return OBJECT_NAMES_ZH.get(name, name)


def light_name(name: str, lang: str = "en") -> str:
    if lang != "zh":
        return name
    return {
        "daylight": "日光",
        "firelit": "火光",
        "torchlit": "火把光",
        "dark": "黑暗",
    }.get(name, name)


def canonical_weather_name(name: str) -> str:
    return WEATHER_ALIASES.get(name, name)


def weather_name(name: str, lang: str = "en") -> str:
    canonical = canonical_weather_name(name)
    if lang == "zh":
        return WEATHER_NAMES_ZH.get(canonical, WEATHER_NAMES_ZH.get(name, name))
    return name if name == "rain" else canonical


def season_name(name: str, lang: str = "en") -> str:
    if lang != "zh":
        return name
    return {"dry": "旱季", "wet": "雨季"}.get(name, name)


def tide_name(name: str, lang: str = "en") -> str:
    if name == "high":
        return ui_text("high_tide", lang)
    if name == "low":
        return ui_text("low_tide", lang)
    return name


def canonical_object_name(name: str) -> str:
    return ZH_ALIASES.get(name, name)


def localized_action_name(action: str, lang: str = "en") -> str:
    return ACTION_NAMES_ZH.get(action, action) if lang == "zh" else action


def action_label(action: str, lang: str = "en") -> str:
    if lang == "zh":
        return localized_action_name(action, lang)
    gerunds = {
        "drink": "drinking",
        "break conch": "breaking a conch",
        "cook conch meat": "cooking conch meat",
        "dive": "diving",
        "eat": "eating",
        "pick up": "picking up items",
        "drop": "dropping items",
        "build raft": "building a raft",
        "explore": "exploring",
        "fish": "fishing",
        "fish with bait": "fishing with bait",
        "spear fish": "spear fishing",
        "gather": "gathering",
        "go for a walk": "walking",
        "leisure": "relaxing",
        "move": "moving",
        "rest": "resting",
        "sail raft": "sailing the raft",
        "signal with mirror": "signaling with mirror",
        "swim": "swimming",
        "wave and shout": "waving and shouting",
        "wash": "washing",
    }
    return gerunds.get(action, f"doing {action}")


def localized_outcome_reason(reason: str | None, lang: str = "en") -> str:
    if not reason:
        return ""
    return OUTCOME_REASONS_ZH.get(reason, reason) if lang == "zh" else reason


def command_description(command: str, lang: str = "en") -> str:
    if command == "crafts":
        command = "recipes"
    descriptions = COMMAND_DESCRIPTIONS.get(lang, COMMAND_DESCRIPTIONS["en"])
    if command in descriptions:
        return descriptions[command]
    if lang == "zh":
        label = localized_action_name(command, lang)
        if label != command:
            return label
    return COMMAND_DESCRIPTIONS["en"].get(command, "start this action")


def feature_description(feature: str, resource_notes: list[str], lang: str = "en") -> str:
    base = FEATURE_DESCRIPTIONS.get(lang, FEATURE_DESCRIPTIONS["en"]).get(feature, ui_text("none", lang))
    return "; ".join([base, *resource_notes])


def scene_resource_notes(feature: str, resources: dict[str, Any], lang: str = "en") -> list[str]:
    matching = [
        (str(item), resource)
        for item, resource in resources.items()
        if resource.get("source") == feature
    ]
    if feature == "coconut palms":
        matching = [
            (item, resource)
            for item, resource in matching
            if item in {"coconut palm", "palm fronds"}
        ]
    notes = []
    for item, resource in matching[:2]:
        label = "palms" if item == "coconut palm" and lang == "en" else object_name(item, lang)
        if resource.get("infinite"):
            notes.append(label)
        else:
            qty = int(resource.get("qty", 0))
            capacity = int(resource.get("capacity", qty))
            notes.append(f"{label} {qty}/{capacity}")
    extra = len(matching) - len(notes)
    if extra > 0:
        notes.append(f"另有 {extra} 种" if lang == "zh" else f"+{extra} more")
    return notes


def raft_stage_component_text(stage: dict[str, Any], lang: str = "en") -> str:
    materials = [
        f"{qty} {object_name(str(item), lang)}"
        for item, qty in stage.get("materials", {}).items()
    ]
    tool_wear = [
        (
            f"{object_name(str(item), lang)} wear {wear}"
            if lang == "en"
            else f"{object_name(str(item), lang)}损耗 {wear}"
        )
        for item, wear in stage.get("tool_wear", {}).items()
    ]
    return ", ".join([*materials, *tool_wear])


def placed_storm_integrity_text(obj: dict[str, Any], lang: str = "en") -> str | None:
    data = obj.get("data") or {}
    if not isinstance(data, dict) or "storm_damage" not in data:
        return None
    integrity = max(0, min(100, 100 - int(data.get("storm_damage", 0))))
    if lang == "zh":
        return f"风暴完整度 {integrity:3d} {_stat_bar(integrity)}"
    return f"storm integrity {integrity:3d} {_stat_bar(integrity)}"


def with_placed_storm_integrity(base: str, obj: dict[str, Any], lang: str = "en") -> str:
    detail = placed_storm_integrity_text(obj, lang)
    if not detail:
        return base
    return f"{base}; {detail}" if lang == "en" else f"{base}；{detail}"


def durability_detail(data: dict[str, Any], lang: str = "en") -> str:
    durability = int(data.get("durability", 0))
    max_durability = max(1, int(data.get("max_durability", durability or 1)))
    pct = max(0, min(100, durability * 100 // max_durability))
    return f"耐久 {pct:3d} {_stat_bar(pct)}" if lang == "zh" else f"durability {pct:3d} {_stat_bar(pct)}"


def storage_state_details(data: dict[str, Any], lang: str = "en") -> list[str]:
    capacity = int(data.get("storage_capacity", 0))
    slots = data.get("slots")
    used_weight = storage_used_weight(data)
    used_slots = len(storage_contents(data))
    weight_pct = max(0, min(100, used_weight * 100 // max(1, capacity)))
    if lang == "zh":
        details = [f"储量 {used_weight}/{capacity} {weight_pct:3d} {_stat_bar(weight_pct)}"]
        if slots is not None:
            slot_capacity = int(slots)
            slot_pct = max(0, min(100, used_slots * 100 // max(1, slot_capacity)))
            details.append(f"格数 {used_slots}/{slot_capacity} {slot_pct:3d} {_stat_bar(slot_pct)}")
        if "weight_reduction" in data:
            details.append(f"减重 {int(data.get('weight_reduction', 0))}")
        if "equipped_weight_reduction" in data:
            details.append(f"装备减重 {int(data.get('equipped_weight_reduction', 0))}")
        if "cool_storage" in data:
            details.append("阴凉储藏")
        if "rain_protection" in data:
            details.append(f"防雨 +{int(data.get('rain_protection', 0))}")
        return details
    details = [f"storage {used_weight}/{capacity} {weight_pct:3d} {_stat_bar(weight_pct)}"]
    if slots is not None:
        slot_capacity = int(slots)
        slot_pct = max(0, min(100, used_slots * 100 // max(1, slot_capacity)))
        details.append(f"slots {used_slots}/{slot_capacity} {slot_pct:3d} {_stat_bar(slot_pct)}")
    if "weight_reduction" in data:
        details.append(f"load relief {int(data.get('weight_reduction', 0))}")
    if "equipped_weight_reduction" in data:
        details.append(f"equipped relief {int(data.get('equipped_weight_reduction', 0))}")
    if "cool_storage" in data:
        details.append("cool storage")
    if "rain_protection" in data:
        details.append(f"rain +{int(data.get('rain_protection', 0))}")
    return details


def placed_description(obj: dict[str, Any], lang: str = "en") -> str:
    kind = str(obj["kind"])
    base = PLACED_DESCRIPTIONS.get(lang, PLACED_DESCRIPTIONS["en"]).get(kind, "present in the scene" if lang == "en" else "在现场")
    base = with_placed_storm_integrity(base, obj, lang)
    if kind in {"fire", "campfire"}:
        fuel = int(obj.get("fuel", 0))
        if not obj.get("active", True):
            return f"{base}; unlit" if lang == "en" else f"{base}；已熄灭"
        return f"{base} with fuel {fuel}" if lang == "en" else f"{base}，燃料 {fuel}"
    if kind == "fish trap":
        data = obj.get("data", {})
        if data.get("ready"):
            catch = object_name(str(data.get("catch", "seafood")), lang)
            return f"{base}; ready with {catch}" if lang == "en" else f"{base}；已捕到{catch}"
        soak_minutes = int(data.get("soak_minutes", 0))
        target = int(data.get("target_minutes", 0))
        if target:
            return (
                f"{base}; soaking {soak_minutes}/{target}m"
                if lang == "en"
                else f"{base}；已浸泡 {soak_minutes}/{target} 分钟"
            )
        return f"{base}; soaking {soak_minutes}m" if lang == "en" else f"{base}；已浸泡 {soak_minutes} 分钟"
    if kind == "snare trap":
        data = obj.get("data", {})
        if data.get("ready"):
            catch = object_name(str(data.get("catch", "prey")), lang)
            return f"{base}; sprung with {catch}" if lang == "en" else f"{base}；已套住{catch}"
        if data.get("baited"):
            soak_minutes = int(data.get("soak_minutes", 0))
            target = int(data.get("target_minutes", 0))
            if target:
                return (
                    f"{base}; baited {soak_minutes}/{target}m"
                    if lang == "en"
                    else f"{base}；已放饵 {soak_minutes}/{target} 分钟"
                )
            return f"{base}; baited" if lang == "en" else f"{base}；已放饵"
        return f"{base}; needs bait" if lang == "en" else f"{base}；需要诱饵"
    if kind == "raincatcher" and obj.get("data", {}).get("rain_minutes"):
        rain_minutes = int(obj["data"]["rain_minutes"])
        return f"{base}; {rain_minutes} rain minutes stored" if lang == "en" else f"{base}；已积累 {rain_minutes} 分钟雨水"
    if kind in {"kiln", "advanced kiln", "forge"}:
        data = obj.get("data", {})
        fuel = int(data.get("fuel", 0))
        temperature = int(data.get("temperature", 0))
        max_fuel = max(1, int(data.get("max_fuel", 96)))
        default_temperature = 1800 if kind == "forge" else 1200 if kind == "advanced kiln" else 900
        max_temperature = max(1, int(data.get("max_temperature", default_temperature)))
        fuel_pct = max(0, min(100, fuel * 100 // max_fuel))
        temperature_pct = max(0, min(100, temperature * 100 // max_temperature))
        state = "lit" if obj.get("active") else "unlit"
        if lang == "zh":
            state_zh = "点燃" if obj.get("active") else "未点燃"
            return f"{base}；{state_zh}；燃料 {fuel_pct:3d} {_stat_bar(fuel_pct)}；温度 {temperature_pct:3d} {_stat_bar(temperature_pct)}"
        return f"{base}; {state}; fuel {fuel_pct:3d} {_stat_bar(fuel_pct)}; heat {temperature_pct:3d} {_stat_bar(temperature_pct)}"
    if kind == "salt bed":
        data = obj.get("data", {})
        liquid = int(data.get("liquid", 0))
        salt = int(data.get("salt", 0))
        liquid_pct = max(0, min(100, liquid * 100 // 9600))
        salt_pct = max(0, min(100, salt * 100 // 1920))
        if lang == "zh":
            return f"{base}；盐水 {liquid_pct:3d} {_stat_bar(liquid_pct)}；盐 {salt_pct:3d} {_stat_bar(salt_pct)}"
        return f"{base}; brine {liquid_pct:3d} {_stat_bar(liquid_pct)}; salt {salt_pct:3d} {_stat_bar(salt_pct)}"
    if kind in {"water reservoir", "well", "cistern"}:
        data = obj.get("data", {})
        liquid = int(data.get("liquid", 0))
        default_capacity = 6000 if kind == "well" else 24000 if kind == "cistern" else 12000
        capacity = int(data.get("capacity", default_capacity))
        mosquito_protection = int(data.get("mosquito_protection", 0))
        water_pct = max(0, min(100, liquid * 100 // max(1, capacity)))
        protection_pct = max(0, min(100, mosquito_protection * 100 // 672))
        liquid_name = "unsafe water" if kind == "well" else "clean water"
        if lang == "zh":
            water = f"{object_name(liquid_name, 'zh')} {liquid}/{capacity} {water_pct:3d} {_stat_bar(water_pct)}"
            protection = f"；防蚊 {protection_pct:3d} {_stat_bar(protection_pct)}" if kind == "water reservoir" else ""
            return f"{base}；{water}{protection}"
        protection = f"; mosquito protection {protection_pct:3d} {_stat_bar(protection_pct)}" if kind == "water reservoir" else ""
        return f"{base}; {liquid_name} {liquid}/{capacity} {water_pct:3d} {_stat_bar(water_pct)}{protection}"
    if kind == "raft frame":
        data = obj.get("data", {})
        stage = int(data.get("stage", 0))
        stages = int(data.get("stages", len(RAFT_BUILD_STAGES)))
        progress = max(0, min(100, stage * 100 // max(1, stages)))
        if stage < len(RAFT_BUILD_STAGES):
            next_parts = raft_stage_component_text(RAFT_BUILD_STAGES[stage], lang)
            if lang == "zh":
                return f"{base}；阶段 {stage}/{stages} {progress:3d} {_stat_bar(progress)}；下一步：{next_parts}"
            return f"{base}; stage {stage}/{stages} {progress:3d} {_stat_bar(progress)}; next: {next_parts}"
        if lang == "zh":
            return f"{base}；阶段 {stage}/{stages} {progress:3d} {_stat_bar(progress)}"
        return f"{base}; stage {stage}/{stages} {progress:3d} {_stat_bar(progress)}"
    data = obj.get("data", {})
    if isinstance(data, dict) and "storage_capacity" in data:
        details = []
        if "durability" in data:
            details.append(durability_detail(data, lang))
        details.extend(storage_state_details(data, lang))
        return f"{base}; " + "; ".join(details) if lang == "en" else f"{base}；" + "；".join(details)
    return base


def location_card_description(card: str, lang: str = "en") -> str:
    description = str(LOCATION_CARD_DEFS.get(card, {}).get("description") or "present in this area")
    if lang == "zh":
        return f"{object_name(card, 'zh')}位置卡"
    return description


def stack_weight(stack: dict[str, Any]) -> int:
    item = str(stack.get("item", ""))
    qty = int(stack.get("qty", 1))
    data = stack.get("data") or {}
    weight = int(ITEM_WEIGHTS.get(item, DEFAULT_ITEM_WEIGHT)) * qty
    if isinstance(data, dict) and data.get("liquid"):
        weight += int(data.get("liquid", 0)) * qty
    return weight


def storage_contents(data: dict[str, Any]) -> list[dict[str, Any]]:
    contents = data.get("contents", [])
    return list(contents) if isinstance(contents, list) else []


def storage_used_weight(data: dict[str, Any]) -> int:
    return sum(stack_weight(stack) for stack in storage_contents(data))


def carried_stack_raw_weight(stack: dict[str, Any]) -> int:
    data = stack.get("data") or {}
    stored = storage_used_weight(data) if isinstance(data, dict) and "storage_capacity" in data else 0
    return stack_weight(stack) + stored


def carried_stack_effective_load(stack: dict[str, Any], *, worn_on_back: bool = False) -> tuple[int, int, int]:
    data = stack.get("data") or {}
    raw = carried_stack_raw_weight(stack)
    relief = 0
    if isinstance(data, dict) and "storage_capacity" in data:
        relief += min(storage_used_weight(data), int(data.get("weight_reduction", 0)))
        if worn_on_back:
            relief += min(stack_weight(stack), int(data.get("equipped_weight_reduction", 0)))
    return max(0, raw - relief), raw, relief


def stack_equipped_slot(stack: dict[str, Any]) -> str | None:
    data = stack.get("data") or {}
    if not isinstance(data, dict) or "storage_capacity" not in data:
        return None
    if data.get("equipped_slot"):
        return str(data["equipped_slot"])
    if stack.get("item") == "woven backpack" or data.get("equipped_weight_reduction"):
        return "back"
    return None


def worn_backpack_index(carried: list[dict[str, Any]]) -> int | None:
    candidates = [
        (
            int((stack.get("data") or {}).get("equipped_weight_reduction", 0)),
            int((stack.get("data") or {}).get("storage_capacity", 0)),
            -index,
            index,
        )
        for index, stack in enumerate(carried)
        if stack_equipped_slot(stack) == "back"
    ]
    if not candidates:
        return None
    return max(candidates)[3]


def stack_pickup_supported(stack: dict[str, Any], current_player: dict[str, Any]) -> bool:
    data = stack.get("data") or {}
    if not isinstance(data, dict) or "storage_capacity" not in data:
        return True
    return (
        stack.get("item") in HAND_CARRIED_STORAGE_KINDS
        or (
            stack_equipped_slot(stack) == "back"
            and worn_backpack_index(list(current_player.get("carried", []))) is None
        )
    )


def player_for_snapshot(snapshot: dict[str, Any], player_name: str | None = None) -> dict[str, Any]:
    players = snapshot.get("players", {})
    current_player = players.get(player_name) if player_name else None
    if current_player is not None:
        return current_player
    if not players:
        return {}
    return next((p for p in players.values() if p.get("connected")), next(iter(players.values()), {}))


def carried_display_entries(current_player: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    carried = list(current_player.get("carried", []))
    return [(display, index, carried[index]) for display, index in enumerate(range(len(carried) - 1, -1, -1), 1)]


def carried_entry_by_display_index(current_player: dict[str, Any], display_index: int) -> tuple[int, dict[str, Any]] | None:
    for display, index, stack in carried_display_entries(current_player):
        if display == display_index:
            return index, stack
    return None


def storage_content_display_entries(data: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    contents = storage_contents(data)
    return [(display, index, contents[index]) for display, index in enumerate(range(len(contents) - 1, -1, -1), 1)]


def placed_storage_display_entries(loc: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    placed = list(loc.get("placed", []))
    entries = []
    for index, obj in enumerate(placed):
        data = obj.get("data") or {}
        if obj.get("active", True) and isinstance(data, dict) and "storage_capacity" in data:
            entries.append((index + 1, index, obj))
    return entries


def scene_display_entries(loc: dict[str, Any]) -> list[tuple[int, str, int, dict[str, Any]]]:
    entries: list[tuple[int, str, int, dict[str, Any]]] = []
    for index, obj in enumerate(loc.get("placed", [])):
        entries.append((len(entries) + 1, "placed", index, obj))
    ground = list(loc.get("ground", []))
    for index in range(len(ground) - 1, -1, -1):
        entries.append((len(entries) + 1, "ground", index, ground[index]))
    return entries


def resource_display_entries(loc: dict[str, Any], action: str = "gather") -> list[tuple[int, str, dict[str, Any]]]:
    resources = [
        (str(item), resource)
        for item, resource in loc.get("resources", {}).items()
        if resource.get("action", action) == action and (resource.get("infinite") or int(resource.get("qty", 0)) > 0)
    ]
    return [(display, item, resource) for display, (item, resource) in enumerate(resources, 1)]


def scene_entry_pickup_supported(kind: str, entry: dict[str, Any], current_player: dict[str, Any]) -> bool:
    if kind == "ground":
        return bool(entry.get("item")) and stack_pickup_supported(entry, current_player)
    data = entry.get("data") or {}
    return (
        bool(entry.get("active", True))
        and entry.get("kind") in PICKABLE_STORAGE_KINDS
        and isinstance(data, dict)
        and "storage_capacity" in data
    )


def indexed_item_choice(action: str, display_index: int, item: str) -> str:
    return f"/{action} {display_index}({item}) 1"


def indexed_content_choice(action: str, container_display: int, content_display: int, item: str) -> str:
    return f"/{action} {container_display}.{content_display}({item}) 1"


def indexed_resource_choice(action: str, display_index: int, item: str) -> str:
    return f"/{action} {display_index}({item}) 1"


def indexed_destination_choice(display_index: int, destination: str) -> str:
    return f"/move {display_index}({destination})"


def quantity_from_index_suffix(suffix: str) -> int | None:
    text = suffix.strip()
    for pattern in (
        r"#?\d+(?:\.\d+)?(?:\(.+?\))?\s+(\d+)$",
        r".+?\s+#?\d+(?:\.\d+)?(?:[.)])?\s+(\d+)$",
    ):
        match = re.fullmatch(pattern, text)
        if match:
            return max(1, int(match.group(1)))
    return None


def parse_display_index_suffix(suffix: str) -> tuple[int, str] | None:
    text = suffix.strip()
    match = re.fullmatch(r"#?(\d+)(?:\((.+?)\))?(?:\s+\d+)?", text)
    if match:
        return int(match.group(1)), (match.group(2) or "").strip()
    match = re.fullmatch(r"#?(\d+)(?:[.)])?(?:\s+(.+))?", text)
    if not match:
        match = re.fullmatch(r"(.+?)\s+#?(\d+)(?:[.)])?", text)
        if not match:
            return None
        return int(match.group(2)), match.group(1).strip()
    return int(match.group(1)), (match.group(2) or "").strip()


def parse_content_index_suffix(suffix: str) -> tuple[int, int, str] | None:
    text = suffix.strip()
    match = re.fullmatch(r"#?(\d+)\.(\d+)(?:\((.+?)\))?(?:\s+\d+)?", text)
    if match:
        return int(match.group(1)), int(match.group(2)), (match.group(3) or "").strip()
    match = re.fullmatch(r"#?(\d+)\.(\d+)(?:\s+(.+))?", text)
    if not match:
        match = re.fullmatch(r"(.+?)\s+#?(\d+)\.(\d+)", text)
        if not match:
            return None
        return int(match.group(2)), int(match.group(3)), match.group(1).strip()
    return int(match.group(1)), int(match.group(2)), (match.group(3) or "").strip()


def indexed_carried_args(
    snapshot: dict[str, Any],
    player_name: str | None,
    suffix: str,
    *,
    storage: bool | None = None,
    item: str | None = None,
) -> dict[str, Any] | None:
    parsed = parse_display_index_suffix(suffix)
    if parsed is None:
        return None
    display_index, rest = parsed
    entry = carried_entry_by_display_index(player_for_snapshot(snapshot, player_name), display_index)
    if entry is None:
        return None
    carried_index, stack = entry
    stack_data = stack.get("data") or {}
    stack_is_storage = isinstance(stack_data, dict) and "storage_capacity" in stack_data
    if storage is True and not stack_is_storage:
        return None
    if storage is False and stack_is_storage:
        return None
    stack_item = str(stack.get("item") or "")
    if item is not None and stack_item != item:
        return None
    if rest and canonical_object_name(rest) != stack_item:
        return None
    args = {"carried_index": carried_index, "item": stack_item}
    qty = quantity_from_index_suffix(suffix)
    if qty is not None:
        args["qty"] = qty
    return args


def indexed_carried_content_args(snapshot: dict[str, Any], player_name: str | None, suffix: str) -> dict[str, Any] | None:
    parsed = parse_content_index_suffix(suffix)
    if parsed is None:
        return None
    container_display, content_display, rest = parsed
    entry = carried_entry_by_display_index(player_for_snapshot(snapshot, player_name), container_display)
    if entry is None:
        return None
    carried_index, container = entry
    data = container.get("data") or {}
    if not isinstance(data, dict) or "storage_capacity" not in data:
        return None
    for display, content_index, content in storage_content_display_entries(data):
        if display != content_display:
            continue
        item = str(content.get("item") or "")
        if rest and canonical_object_name(rest) != item:
            return None
        args = {"carried_index": carried_index, "content_index": content_index, "item": item}
        qty = quantity_from_index_suffix(suffix)
        if qty is not None:
            args["qty"] = qty
        return args
    return None


def indexed_placed_content_args(snapshot: dict[str, Any], player_name: str | None, suffix: str) -> dict[str, Any] | None:
    parsed = parse_content_index_suffix(suffix)
    if parsed is None:
        return None
    storage_display, content_display, rest = parsed
    current_location = current_location_for_snapshot(snapshot, player_name)
    loc = snapshot.get("locations", {}).get(current_location, {}) if current_location else {}
    for display, placed_index, obj in placed_storage_display_entries(loc):
        if display != storage_display:
            continue
        data = obj.get("data") or {}
        for content_entry_display, content_index, content in storage_content_display_entries(data):
            if content_entry_display != content_display:
                continue
            item = str(content.get("item") or "")
            if rest and canonical_object_name(rest) != item:
                return None
            args = {"placed_index": placed_index, "content_index": content_index, "item": item}
            qty = quantity_from_index_suffix(suffix)
            if qty is not None:
                args["qty"] = qty
            return args
    return None


def indexed_scene_args(snapshot: dict[str, Any], player_name: str | None, suffix: str) -> dict[str, Any] | None:
    parsed = parse_display_index_suffix(suffix)
    if parsed is None:
        return None
    display_index, rest = parsed
    current_player = player_for_snapshot(snapshot, player_name)
    current_location = str(current_player.get("location") or "")
    loc = snapshot.get("locations", {}).get(current_location, {}) if current_location else {}
    for display, kind, index, entry in scene_display_entries(loc):
        if display != display_index:
            continue
        item = str(entry.get("item") if kind == "ground" else entry.get("kind"))
        if not scene_entry_pickup_supported(kind, entry, current_player):
            return None
        if rest and canonical_object_name(rest) != item:
            return None
        key = "ground_index" if kind == "ground" else "placed_index"
        args = {key: index, "item": item}
        qty = quantity_from_index_suffix(suffix)
        if qty is not None and kind == "ground":
            args["qty"] = qty
        return args
    return None


def inventory_condition_bar(stack: dict[str, Any]) -> str:
    item = str(stack["item"])
    age = int(stack.get("age_minutes", 0))
    data = stack.get("data") or {}
    if isinstance(data, dict) and "durability" in data:
        durability = int(data.get("durability", 0))
        max_durability = max(1, int(data.get("max_durability", durability or 1)))
        return _stat_bar(max(0, min(100, durability * 100 // max_durability)))
    spoil_minutes = SPOIL_MINUTES.get(item)
    if spoil_minutes:
        if item in {"leaves", "fleshed skin"}:
            pct = max(0, min(100, age * 100 // spoil_minutes))
        else:
            pct = max(0, min(100, 100 - age * 100 // spoil_minutes))
        return _stat_bar(pct)
    if isinstance(data, dict) and "fuel" in data:
        fuel = int(data.get("fuel", 0))
        max_fuel = max(1, int(data.get("max_fuel", fuel or 1)))
        return _stat_bar(max(0, min(100, fuel * 100 // max_fuel)))
    if isinstance(data, dict) and "liquid_capacity" in data:
        capacity = int(data.get("liquid_capacity", 0))
        liquid = int(data.get("liquid", 0))
        return _stat_bar(max(0, min(100, liquid * 100 // max(1, capacity))))
    if isinstance(data, dict) and "storage_capacity" in data:
        capacity = int(data.get("storage_capacity", 0))
        used = storage_used_weight(data)
        return _stat_bar(max(0, min(100, used * 100 // max(1, capacity))))
    return ""


def inventory_row(display: str, qty: int, name: str, stack: dict[str, Any], *, worn_on_back: bool = False) -> str:
    item_text = f"{qty} {name}"
    bar = inventory_condition_bar(stack) or " " * 10
    load, raw, relief = carried_stack_effective_load(stack, worn_on_back=worn_on_back)
    load_text = str(load) if relief == 0 else f"{load}/{raw}"
    return f"  {display} {pad_display(item_text, 22)} {bar} {load_text}"


def item_description(stack: dict[str, Any], lang: str = "en", *, carried: bool = False) -> str:
    item = str(stack["item"])
    age = int(stack.get("age_minutes", 0))
    data = stack.get("data") or {}
    details = []
    if isinstance(data, dict) and "durability" in data:
        details.append(durability_detail(data, lang))
    if isinstance(data, dict) and "fuel" in data:
        fuel = int(data.get("fuel", 0))
        max_fuel = max(1, int(data.get("max_fuel", fuel or 1)))
        pct = max(0, min(100, fuel * 100 // max_fuel))
        if lang == "zh":
            details.append(f"燃料 {pct:3d} {_stat_bar(pct)}")
        else:
            details.append(f"fuel {pct:3d} {_stat_bar(pct)}")
    if isinstance(data, dict) and "liquid_capacity" in data:
        capacity = int(data.get("liquid_capacity", 0))
        sealed = bool(data.get("sealed"))
        liquid = int(data.get("liquid", 0))
        liquid_pct = max(0, min(100, liquid * 100 // max(1, capacity)))
        liquid_type = str(data.get("liquid_type", "empty"))
        if lang == "zh":
            details.append(f"容量 {capacity}")
            details.append("密封" if sealed else "开口")
            if liquid:
                details.append(f"{object_name(liquid_type, 'zh')} {liquid}/{capacity} {liquid_pct:3d} {_stat_bar(liquid_pct)}")
            else:
                details.append(f"空 {liquid_pct:3d} {_stat_bar(liquid_pct)}")
        else:
            details.append(f"capacity {capacity}")
            details.append("sealed" if sealed else "open")
            if liquid:
                details.append(f"{liquid_type} {liquid}/{capacity} {liquid_pct:3d} {_stat_bar(liquid_pct)}")
            else:
                details.append(f"empty {liquid_pct:3d} {_stat_bar(liquid_pct)}")
    if isinstance(data, dict) and "storage_capacity" in data:
        details.extend(storage_state_details(data, lang))
    spoil_minutes = SPOIL_MINUTES.get(item)
    if item == "lit tinder" and spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        remaining_pct = max(0, min(100, 100 - age * 100 // spoil_minutes))
        if lang == "zh":
            details.append(f"余火 {remaining_pct:3d} {_stat_bar(remaining_pct)}")
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；约 {hours_left} 小时后熄灭；" + "；".join(details)
        details.append(f"ember {remaining_pct:3d} {_stat_bar(remaining_pct)}")
        return f"{ITEM_DESCRIPTIONS['en'][item]}; burns out in about {hours_left}h; " + "; ".join(details)
    if item == "lit torch" and spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        remaining_pct = max(0, min(100, 100 - age * 100 // spoil_minutes))
        if lang == "zh":
            details.append(f"火焰 {remaining_pct:3d} {_stat_bar(remaining_pct)}")
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；约 {hours_left} 小时后熄灭；" + "；".join(details)
        details.append(f"flame {remaining_pct:3d} {_stat_bar(remaining_pct)}")
        return f"{ITEM_DESCRIPTIONS['en'][item]}; burns out in about {hours_left}h; " + "; ".join(details)
    if item == "leaves" and spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        drying_pct = max(0, min(100, age * 100 // spoil_minutes))
        if lang == "zh":
            details.append(f"干燥 {drying_pct:3d} {_stat_bar(drying_pct)}")
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；约 {hours_left} 小时后变成干叶；" + "；".join(details)
        details.append(f"drying {drying_pct:3d} {_stat_bar(drying_pct)}")
        return f"{ITEM_DESCRIPTIONS['en'][item]}; dries into dry leaves in about {hours_left}h; " + "; ".join(details)
    if item == "fleshed skin" and spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        curing_pct = max(0, min(100, age * 100 // spoil_minutes))
        if lang == "zh":
            details.append(f"风干 {curing_pct:3d} {_stat_bar(curing_pct)}")
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；约 {hours_left} 小时后变成皮革；" + "；".join(details)
        details.append(f"curing {curing_pct:3d} {_stat_bar(curing_pct)}")
        return f"{ITEM_DESCRIPTIONS['en'][item]}; cures into leather in about {hours_left}h; " + "; ".join(details)
    if item == "fresh skin" and spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        usable_pct = max(0, min(100, 100 - age * 100 // spoil_minutes))
        if lang == "zh":
            details.append(f"可用 {usable_pct:3d} {_stat_bar(usable_pct)}")
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；约 {hours_left} 小时后腐坏；" + "；".join(details)
        details.append(f"usable {usable_pct:3d} {_stat_bar(usable_pct)}")
        return f"{ITEM_DESCRIPTIONS['en'][item]}; rots in about {hours_left}h; " + "; ".join(details)
    if spoil_minutes:
        hours_left = max(0, (spoil_minutes - age + 59) // 60)
        ratio = age / spoil_minutes
        freshness_pct = max(0, min(100, 100 - int(ratio * 100)))
        if lang == "zh":
            freshness = "新鲜" if ratio < 1 / 3 else "半新鲜" if ratio < 2 / 3 else "快变质"
            details.append(f"新鲜度 {freshness_pct:3d} {_stat_bar(freshness_pct)}")
            return f"{freshness}；{hours_left} 小时后腐坏；" + "；".join(details)
        freshness = "fresh" if ratio < 1 / 3 else "half fresh" if ratio < 2 / 3 else "near spoiling"
        details.append(f"freshness {freshness_pct:3d} {_stat_bar(freshness_pct)}")
        return f"{freshness}; spoils in {hours_left}h; " + "; ".join(details)
    if item in {"clean water", "unsafe water", "salt water"} and stack.get("exposed", True) and not carried:
        hours_left = max(0, (360 - age + 59) // 60)
        remaining_pct = max(0, min(100, 100 - age * 100 // 360))
        if lang == "zh":
            details.append(f"剩余 {remaining_pct:3d} {_stat_bar(remaining_pct)}")
            return f"{ITEM_DESCRIPTIONS['zh'][item]}；暴露放置，约 {hours_left} 小时后蒸发；" + "；".join(details)
        details.append(f"remaining {remaining_pct:3d} {_stat_bar(remaining_pct)}")
        return f"{ITEM_DESCRIPTIONS['en'][item]}; exposed, evaporates in about {hours_left}h; " + "; ".join(details)
    base = ITEM_DESCRIPTIONS.get(lang, ITEM_DESCRIPTIONS["en"]).get(item, "ordinary object" if lang == "en" else "普通物品")
    if details:
        return f"{base}; " + "; ".join(details) if lang == "en" else f"{base}；" + "；".join(details)
    return base


def localize_event(event: str, lang: str = "en") -> str:
    if lang != "zh":
        return event
    if event == "manual save complete":
        return "手动保存完成。"
    if event == "save already in progress":
        return "保存正在进行中。"
    if event == "server disconnected":
        return "服务器已断开连接。"
    if event == "Day 1 dawns on the beach.":
        return "第 1 天在海滩破晓。"
    if event == "Tip: pick up a coconut and drink it for quick water; gather unsafe water and boil it for safer water.":
        return "提示：捡起椰子后可以饮用；也可以收集不安全的水并煮成净水。"
    if event == "world paused":
        return "世界已暂停。"
    if event == "world resumed":
        return "世界已恢复。"
    if match := re.fullmatch(r"(.+) paused the world\.", event):
        return f"{match[1]} 暂停了世界。"
    if match := re.fullmatch(r"(.+) resumed the world\.", event):
        return f"{match[1]} 恢复了世界。"
    if match := re.fullmatch(r"(.+) cancelled action\.", event):
        return f"{match[1]} 取消了当前行动。"
    if match := re.fullmatch(r"(.+) joined(?: the island)?\.?", event):
        return f"{match[1]} 加入了小岛。"
    if match := re.fullmatch(r"(.+) reconnected\.", event):
        return f"{match[1]} 重新连接了。"
    if match := re.fullmatch(r"(.+) disconnected(?:; their personal state is frozen)?\.?", event):
        return f"{match[1]} 已断开连接。"
    if match := re.fullmatch(r"Day (\d+) begins\.", event):
        return f"第 {match[1]} 天开始了。"
    if event == "Heavy rain starts over the island.":
        return "岛上下起了大雨。"
    if event == "A storm lashes the island.":
        return "风暴抽打着小岛。"
    if event == "The sky clears.":
        return "天空放晴了。"
    if match := re.fullmatch(r"Storm winds battered (.+) at (.+)\.", event):
        return f"风暴在{object_name(match[2], 'zh')}吹打着{match[1]}。"
    if match := re.fullmatch(r"Storm damaged (.+) at (.+)\.", event):
        return f"风暴损坏了{object_name(match[2], 'zh')}的{object_name(match[1], 'zh')}。"
    if match := re.fullmatch(r"A (.+) at (.+) was wrecked by the storm\.", event):
        return f"{object_name(match[2], 'zh')}的{object_name(match[1], 'zh')}被风暴毁坏了。"
    if match := re.fullmatch(r"(.+) started (.+)\.", event):
        return f"{match[1]} 开始{localized_action_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) completed (.+)\.", event):
        return f"{match[1]} 完成{localized_action_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) cancelled (.+)\.", event):
        return f"{match[1]} 取消了{localized_action_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) died from (.+)\.", event):
        return f"{match[1]}死于{localized_outcome_reason(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) was rescued by a ship\.", event):
        return f"{match[1]}被船只救起了。"
    if match := re.fullmatch(r"(.+) sailed the raft to distance (\d+)\.", event):
        return f"{match[1]}驾驶木筏航行到距离 {match[2]}。"
    if match := re.fullmatch(r"(.+) launched a raft at the beach\.", event):
        return f"{match[1]}在海滩放下了木筏。"
    if match := re.fullmatch(r"(.+) advanced the raft frame to stage (\d+)/(\d+)\.", event):
        return f"{match[1]}把木筏框架推进到阶段 {match[2]}/{match[3]}。"
    if match := re.fullmatch(r"(.+) signaled the passing ship \((\d+)/100\)\.", event):
        return f"{match[1]}向过往船只示意（{match[2]}/100）。"
    if event == "A passing ship appeared near the raft.":
        return "木筏附近出现了一艘过往船只。"
    if event == "The passing ship slipped beyond signaling range.":
        return "那艘船驶出了可示意范围。"
    if event == "A ship is coming straight toward the raft, horn sounding.":
        return "一艘船鸣着汽笛，正朝木筏驶来。"
    if match := re.fullmatch(r"(.+) discovered (.+)\.", event):
        return f"{match[1]} 发现了{object_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) found (.+) at (.+)\.", event):
        return f"{match[1]} 在{object_name(match[3], 'zh')}找到了{object_name(match[2], 'zh')}。"
    if match := re.fullmatch(r"(.+) found nothing while (diving|walking) (.+)\.", event):
        activity = {"diving": "潜水", "walking": "散步"}.get(match[2], match[2])
        return f"{match[1]} 在{activity}{object_name(match[3], 'zh')}时什么也没找到。"
    if match := re.fullmatch(r"(.+) caught nothing while (fishing|spear fishing) (.+)\.", event):
        activity = {"fishing": "钓鱼", "spear fishing": "叉鱼"}.get(match[2], match[2])
        return f"{match[1]} 在{object_name(match[3], 'zh')}{activity}时一无所获。"
    if match := re.fullmatch(r"(.+) found (?:(\d+) )?(.+) while (exploring|walking) (.+)\.", event):
        qty = f"{match[2]} " if match[2] else ""
        activity = {"exploring": "探索", "walking": "散步"}.get(match[4], match[4])
        return f"{match[1]} 在{activity}{object_name(match[5], 'zh')}时找到了{qty}{object_name(match[3], 'zh')}。"
    if match := re.fullmatch(r"(.+) had no free carry slot, so (\d+) (.+) was left at (.+)\.", event):
        return f"{match[1]}没有空余携带格，{match[2]}个{object_name(match[3], 'zh')}留在了{object_name(match[4], 'zh')}。"
    if match := re.fullmatch(r"Raw fish spoiled at (.+)\.", event):
        return f"生鱼在{object_name(match[1], 'zh')}腐坏了。"
    if match := re.fullmatch(r"Cooked fish spoiled at (.+)\.", event):
        return f"熟鱼在{object_name(match[1], 'zh')}腐坏了。"
    if match := re.fullmatch(r"Exposed (.+) evaporated at (.+)\.", event):
        return f"暴露的{object_name(match[1], 'zh')}在{object_name(match[2], 'zh')}蒸发了。"
    if match := re.fullmatch(r"Leaves dried at (.+)\.", event):
        return f"叶子在{object_name(match[1], 'zh')}变成干叶了。"
    if match := re.fullmatch(r"Fleshed skin cured at (.+)\.", event):
        return f"刮净兽皮在{object_name(match[1], 'zh')}变成皮革了。"
    if match := re.fullmatch(r"Lit tinder burned out at (.+)\.", event):
        return f"点燃的火绒在{object_name(match[1], 'zh')}熄灭了。"
    if match := re.fullmatch(r"Lit torch burned out at (.+)\.", event):
        return f"点燃的火把在{object_name(match[1], 'zh')}熄灭了。"
    if match := re.fullmatch(r"(.+) spoiled at (.+)\.", event):
        return f"{object_name(match[1].lower(), 'zh')}在{object_name(match[2], 'zh')}腐坏了。"
    if match := re.fullmatch(r"(.+) regrew at (.+)\.", event):
        return f"{object_name(match[1].lower(), 'zh')}在{object_name(match[2], 'zh')}重新长出来了。"
    if match := re.fullmatch(r"A (.+) at (.+) burned out\.", event):
        return f"{object_name(match[1], 'zh')}在{object_name(match[2], 'zh')}熄灭了。"
    if match := re.fullmatch(r"(.+)'s (.+) wore out\.", event):
        return f"{match[1]}的{object_name(match[2], 'zh')}用坏了。"
    if match := re.fullmatch(r"(.+) at (.+) produced (.+)\.", event):
        process = {
            "cooking": "烹饪",
            "boiling": "煮水",
            "drying": "晾晒",
            "filtering": "过滤",
            "curing": "腌制",
            "firing": "烧制",
        }.get(match[1], match[1])
        return f"{process}在{object_name(match[2], 'zh')}产出了{object_name(match[3], 'zh')}。"
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
    return f"{frame} {player_name} {action_label(name, lang)}… {remaining}m left"


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
            choices.extend(indexed_destination_choice(display, name) for display, name in enumerate(destinations, 1))
            choices.append("/move")
        elif action == "pick up":
            choices.extend(
                indexed_item_choice(
                    "pick up",
                    display,
                    str(entry.get("item") if kind == "ground" else entry.get("kind")),
                )
                for display, kind, _index, entry in scene_display_entries(loc)
                if scene_entry_pickup_supported(kind, entry, current_player)
            )
            choices.append("/pick up")
        elif action == "drop":
            choices.extend(
                indexed_item_choice(action, display, str(stack.get("item")))
                for display, _index, stack in carried_display_entries(current_player)
                if stack.get("item") and "storage_capacity" not in (stack.get("data") or {})
            )
            choices.append("/drop")
        elif action in {"pack", "store"}:
            choices.extend(
                indexed_item_choice(action, display, str(stack.get("item")))
                for display, _index, stack in carried_display_entries(current_player)
                if stack.get("item") and "storage_capacity" not in (stack.get("data") or {})
            )
            choices.append(f"/{action}")
        elif action == "unpack":
            choices.extend(
                indexed_content_choice("unpack", container_display, content_display, str(content.get("item")))
                for container_display, _container_index, container in carried_display_entries(current_player)
                for content_display, _content_index, content in storage_content_display_entries(container.get("data") or {})
                if content.get("item")
            )
            choices.append("/unpack")
        elif action == "retrieve":
            choices.extend(
                indexed_content_choice("retrieve", storage_display, content_display, str(content.get("item")))
                for storage_display, _placed_index, obj in placed_storage_display_entries(loc)
                for content_display, _content_index, content in storage_content_display_entries(obj.get("data") or {})
                if content.get("item")
            )
            choices.append("/retrieve")
        elif action == "place basket":
            choices.extend(
                indexed_item_choice(action, display, str(stack.get("item")))
                for display, _index, stack in carried_display_entries(current_player)
                if stack.get("item") == "basket"
            )
            choices.append("/place basket")
        elif action == "add rope to basket":
            choices.extend(
                indexed_item_choice(action, display, str(stack.get("item")))
                for display, _index, stack in carried_display_entries(current_player)
                if stack.get("item") == "basket"
            )
            choices.append("/add rope to basket")
        elif action in TINDER_LIGHTING_ACTIONS:
            choices.extend(
                indexed_item_choice(action, display, str(stack.get("item")))
                for display, _index, stack in carried_display_entries(current_player)
                if stack.get("item") in TINDER_ITEMS
            )
            choices.append(f"/{action}")
        elif action == "gather":
            choices.extend(
                indexed_resource_choice(action, display, item)
                for display, item, _resource in resource_display_entries(loc, action)
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
        self.matches = self._matches_for_query(query)
        self.index = min(self.index, max(0, len(self.matches) - 1))

    def _action_choice(self, choice: str) -> str:
        command = choice.removeprefix("/")
        known_actions = {c.removeprefix("/") for c in CLIENT_COMMANDS} | set(ACTION_DURATIONS)
        for action in sorted(known_actions, key=len, reverse=True):
            if command == action or command.startswith(f"{action} "):
                return f"/{action}"
        return choice

    def _action_choices(self) -> list[str]:
        actions = []
        seen = set()
        for choice in self.choices:
            action = self._action_choice(choice)
            if action not in seen:
                seen.add(action)
                actions.append(action)
        return actions

    def _matches_for_query(self, query: str) -> list[str]:
        if query.endswith(" "):
            return [choice for choice in self.choices if choice.startswith(query)]
        actions = self._action_choices()
        action_matches = [choice for choice in actions if choice.startswith(query)]
        return action_matches if action_matches else [choice for choice in self.choices if choice.startswith(query)]

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
        if any(choice.startswith(f"{selected} ") for choice in self.choices):
            return f"{selected} "
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
        elif command.startswith("pack "):
            command = "pack"
        elif command.startswith("unpack "):
            command = "unpack"
        elif command.startswith("store "):
            command = "store"
        elif command.startswith("retrieve "):
            command = "retrieve"
        elif command.startswith("light tinder with hand drill "):
            command = "light tinder with hand drill"
        elif command.startswith("light tinder with bow drill "):
            command = "light tinder with bow drill"
        elif command.startswith("light tinder from fire "):
            command = "light tinder from fire"
        elif command.startswith("light tinder with mirror "):
            command = "light tinder with mirror"
        return command_description(command, lang)

    def display_for(self, choice: str, lang: str = "en") -> str:
        if lang != "zh" or not choice.startswith("/"):
            return choice
        command = choice.removeprefix("/")
        action = command
        target = ""
        for prefix in (
            "light tinder with hand drill",
            "light tinder with bow drill",
            "light tinder from fire",
            "light tinder with mirror",
            "place basket",
            "add rope to basket",
            "move",
            "pick up",
            "drop",
            "pack",
            "unpack",
            "store",
            "retrieve",
        ):
            if command == prefix or command.startswith(f"{prefix} "):
                action = prefix
                target = command.removeprefix(prefix).strip()
                break
        if " <" in action:
            action = action.split(" <", 1)[0]
        action_name = localized_action_name(action, lang)
        if target and not target.startswith("<"):
            content_target = parse_content_index_suffix(target)
            indexed_target = parse_display_index_suffix(target)
            if content_target and content_target[2]:
                target_label = f"{object_name(canonical_object_name(content_target[2]), lang)} {content_target[0]}.{content_target[1]}"
            elif indexed_target:
                target_label = (
                    f"{object_name(canonical_object_name(indexed_target[1]), lang)} {indexed_target[0]}"
                    if indexed_target[1]
                    else str(indexed_target[0])
                )
            else:
                target_label = object_name(target, lang)
            label = f"{action_name} {target_label}"
        else:
            label = action_name
        return f"{choice} ({label})" if label != command else choice

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
            lines.append(f"{marker} {self.display_for(choice, lang)} — {self.description_for(choice, lang)}")
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
    if command in {"pause", "resume", "save"}:
        return {"type": command}
    if command == "move":
        return {"type": "start_action", "action": "move", "args": {}}
    if command.startswith("move "):
        suffix = command.removeprefix("move ").strip()
        neighbors = move_neighbors_for_snapshot(snapshot, player_name)
        destinations = move_destinations_for_snapshot(snapshot, player_name)
        parsed = parse_display_index_suffix(suffix)
        if parsed is not None:
            display_index, rest = parsed
            if display_index < 1 or display_index > len(destinations):
                return None
            destination = destinations[display_index - 1]
            if rest and canonical_object_name(rest) != destination:
                return None
        else:
            destination = canonical_object_name(suffix)
        if neighbors is not None and destination not in destinations:
            return None
        location = snapshot.get("locations", {}).get(destination)
        if location is not None and not location.get("discovered", True):
            return None
        return {"type": "start_action", "action": "move", "args": {"location": destination}}
    if command in {"pick up", "pickup"}:
        return {"type": "start_action", "action": "pick up", "args": {}}
    if command.startswith("pick up "):
        suffix = command.removeprefix("pick up ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_scene_args(snapshot, player_name, suffix)
            return {"type": "start_action", "action": "pick up", "args": args} if args else None
        return {"type": "start_action", "action": "pick up", "args": {"item": canonical_object_name(suffix)}}
    if command.startswith("pickup "):
        suffix = command.removeprefix("pickup ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_scene_args(snapshot, player_name, suffix)
            return {"type": "start_action", "action": "pick up", "args": args} if args else None
        return {"type": "start_action", "action": "pick up", "args": {"item": canonical_object_name(suffix)}}
    if command == "drop":
        return {"type": "start_action", "action": "drop", "args": {}}
    if command.startswith("drop "):
        suffix = command.removeprefix("drop ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_carried_args(snapshot, player_name, suffix, storage=False)
            return {"type": "start_action", "action": "drop", "args": args} if args else None
        return {"type": "start_action", "action": "drop", "args": {"item": canonical_object_name(suffix)}}
    if command == "pack":
        return {"type": "start_action", "action": "pack", "args": {}}
    if command.startswith("pack "):
        suffix = command.removeprefix("pack ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_carried_args(snapshot, player_name, suffix, storage=False)
            return {"type": "start_action", "action": "pack", "args": args} if args else None
        return {"type": "start_action", "action": "pack", "args": {"item": canonical_object_name(suffix)}}
    if command == "unpack":
        return {"type": "start_action", "action": "unpack", "args": {}}
    if command.startswith("unpack "):
        suffix = command.removeprefix("unpack ").strip()
        if parse_content_index_suffix(suffix) is not None:
            args = indexed_carried_content_args(snapshot, player_name, suffix)
            return {"type": "start_action", "action": "unpack", "args": args} if args else None
        return {"type": "start_action", "action": "unpack", "args": {"item": canonical_object_name(suffix)}}
    if command == "store":
        return {"type": "start_action", "action": "store", "args": {}}
    if command.startswith("store "):
        suffix = command.removeprefix("store ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_carried_args(snapshot, player_name, suffix, storage=False)
            return {"type": "start_action", "action": "store", "args": args} if args else None
        return {"type": "start_action", "action": "store", "args": {"item": canonical_object_name(suffix)}}
    if command == "retrieve":
        return {"type": "start_action", "action": "retrieve", "args": {}}
    if command.startswith("retrieve "):
        suffix = command.removeprefix("retrieve ").strip()
        if parse_content_index_suffix(suffix) is not None:
            args = indexed_placed_content_args(snapshot, player_name, suffix)
            return {"type": "start_action", "action": "retrieve", "args": args} if args else None
        return {"type": "start_action", "action": "retrieve", "args": {"item": canonical_object_name(suffix)}}
    if command == "place basket":
        return {"type": "start_action", "action": "place basket", "args": {}}
    if command.startswith("place basket "):
        suffix = command.removeprefix("place basket ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_carried_args(snapshot, player_name, suffix, item="basket", storage=True)
            return {"type": "start_action", "action": "place basket", "args": args} if args else None
    if command == "add rope to basket":
        return {"type": "start_action", "action": "add rope to basket", "args": {}}
    if command.startswith("add rope to basket "):
        suffix = command.removeprefix("add rope to basket ").strip()
        if parse_display_index_suffix(suffix) is not None:
            args = indexed_carried_args(snapshot, player_name, suffix, item="basket", storage=True)
            return {"type": "start_action", "action": "add rope to basket", "args": args} if args else None
    if command == "light tinder with hand drill":
        return {"type": "start_action", "action": "light tinder with hand drill", "args": {}}
    if command.startswith("light tinder with hand drill "):
        suffix = command.removeprefix("light tinder with hand drill ").strip()
        args = indexed_carried_args(snapshot, player_name, suffix) if parse_display_index_suffix(suffix) else None
        item = args["item"] if args else canonical_object_name(suffix)
        if item not in TINDER_ITEMS:
            return None
        return {
            "type": "start_action",
            "action": "light tinder with hand drill",
            "args": {"item": item},
        }
    if command == "light tinder with bow drill":
        return {"type": "start_action", "action": "light tinder with bow drill", "args": {}}
    if command.startswith("light tinder with bow drill "):
        suffix = command.removeprefix("light tinder with bow drill ").strip()
        args = indexed_carried_args(snapshot, player_name, suffix) if parse_display_index_suffix(suffix) else None
        item = args["item"] if args else canonical_object_name(suffix)
        if item not in TINDER_ITEMS:
            return None
        return {
            "type": "start_action",
            "action": "light tinder with bow drill",
            "args": {"item": item},
        }
    if command == "light tinder from fire":
        return {"type": "start_action", "action": "light tinder from fire", "args": {}}
    if command.startswith("light tinder from fire "):
        suffix = command.removeprefix("light tinder from fire ").strip()
        args = indexed_carried_args(snapshot, player_name, suffix) if parse_display_index_suffix(suffix) else None
        item = args["item"] if args else canonical_object_name(suffix)
        if item not in TINDER_ITEMS:
            return None
        return {
            "type": "start_action",
            "action": "light tinder from fire",
            "args": {"item": item},
        }
    if command == "light tinder with mirror":
        return {"type": "start_action", "action": "light tinder with mirror", "args": {}}
    if command.startswith("light tinder with mirror "):
        suffix = command.removeprefix("light tinder with mirror ").strip()
        args = indexed_carried_args(snapshot, player_name, suffix) if parse_display_index_suffix(suffix) else None
        item = args["item"] if args else canonical_object_name(suffix)
        if item not in TINDER_ITEMS:
            return None
        return {
            "type": "start_action",
            "action": "light tinder with mirror",
            "args": {"item": item},
        }
    if command.startswith("gather "):
        suffix = command.removeprefix("gather ").strip()
        current_location = current_location_for_snapshot(snapshot, player_name)
        loc = snapshot.get("locations", {}).get(current_location, {}) if current_location else {}
        parsed = parse_display_index_suffix(suffix)
        if parsed is not None:
            display_index, rest = parsed
            for display, item, _resource in resource_display_entries(loc, "gather"):
                if display != display_index:
                    continue
                if rest and canonical_object_name(rest) != item:
                    return None
                return {"type": "start_action", "action": "gather", "args": {"item": item}}
            return None
        return {"type": "start_action", "action": "gather", "args": {"item": canonical_object_name(suffix)}}
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


PLAYER_STAT_INDEX = {key: index for index, key in enumerate(PLAYER_STAT_KEYS)}


def stat_label(key: str, lang: str = "en") -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key.replace("_", " "))


def _stat_color(value: int) -> str:
    if value >= 50:
        return "green"
    if value >= 20:
        return "yellow"
    return "red"


def _stat_bar(value: int) -> str:
    filled = max(0, min(10, value // 10))
    return "█" * filled + "░" * (10 - filled)


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1 for ch in text)


def pad_display(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def _player_panel_stats(current_player: dict[str, Any]) -> list[tuple[str, int]]:
    stats = current_player.get("stats")
    if isinstance(stats, dict) and stats:
        known = [(key, int(stats[key])) for key in PLAYER_STAT_KEYS if key in stats]
        extras = sorted((str(key), int(value)) for key, value in stats.items() if key not in PLAYER_STAT_INDEX)
        return [(key, max(0, min(100, value))) for key, value in [*known, *extras]]
    needs = current_player.get("needs", {})
    conditions = current_player.get("conditions", {})
    fallback = [
        ("health", int(needs.get("health", 100))),
        ("hydration", 100 - int(needs.get("thirst", 0))),
        ("satiation", 100 - int(needs.get("hunger", 0))),
        ("stamina", 100 - int(needs.get("fatigue", 0))),
        ("morale", int(needs.get("morale", 50))),
        ("calm", 100 - int(needs.get("stress", 0))),
        ("comfort", 100 - int(conditions.get("pain", 0))),
        ("dryness", 100 - int(conditions.get("wetness", 0))),
        ("cleanliness", 100 - int(conditions.get("filth", 0))),
        ("wound_recovery", 100 - int(conditions.get("wounds", 0)) * 25),
    ]
    return [(key, max(0, min(100, value))) for key, value in fallback]


def format_players_panel(snapshot: dict[str, Any], player_name: str, lang: str = "en") -> str:
    current_player = snapshot["players"][player_name]
    name = str(current_player.get("name") or player_name or "Player")
    player_status = str(current_player.get("status") or "alive")
    if player_status == "alive":
        status = ui_text("online", lang) if current_player.get("connected") else ui_text("offline", lang)
    else:
        status = ui_text(f"status_{player_status}", lang)
    lines = [f"{name} ({status}) @ {object_name(str(current_player.get('location')), lang)}"]
    stats = sorted(
        _player_panel_stats(current_player),
        key=lambda item: (item[1], PLAYER_STAT_INDEX.get(item[0], len(PLAYER_STAT_INDEX)), item[0]),
    )
    width = max(display_width(stat_label(key, lang)) for key, _ in stats)
    for key, value in stats:
        color = _stat_color(value)
        label = pad_display(stat_label(key, lang), width)
        lines.append(f"  {label} [{color}]{value:3d} {_stat_bar(value)}[/{color}]")
    return "\n".join(lines)


def format_inventory_panel(snapshot: dict[str, Any], player_name: str, lang: str = "en") -> str:
    player = snapshot["players"][player_name]
    lines = [ui_text("inventory", lang)]
    carrying = player.get("carrying") or {}
    if carrying:
        effective = int(carrying.get("effective_weight", 0))
        capacity = int(carrying.get("capacity", 1))
        burden = max(0, min(100, int(carrying.get("burden", effective * 100 // max(1, capacity)))))
        relief = int(carrying.get("relief", 0))
        loose_slots = carrying.get("loose_slots")
        loose_slot_capacity = carrying.get("loose_slot_capacity")
        back_slots = carrying.get("back_slots")
        back_slot_capacity = carrying.get("back_slot_capacity")
        if lang == "zh":
            line = f"  负重 {effective}/{capacity} {burden:3d} {_stat_bar(burden)}"
            if relief:
                line += f"；减重 {relief}"
            lines.append(line)
            slot_parts = []
            if loose_slots is not None and loose_slot_capacity is not None:
                slot_parts.append(f"手持 {int(loose_slots)}/{int(loose_slot_capacity)}")
            if back_slots is not None and back_slot_capacity is not None:
                slot_parts.append(f"背部 {int(back_slots)}/{int(back_slot_capacity)}")
            if slot_parts:
                lines.append(f"  格位：{'；'.join(slot_parts)}")
        else:
            line = f"  Load {effective}/{capacity} {burden:3d} {_stat_bar(burden)}"
            if relief:
                line += f"; relief {relief}"
            lines.append(line)
            slot_parts = []
            if loose_slots is not None and loose_slot_capacity is not None:
                slot_parts.append(f"hands {int(loose_slots)}/{int(loose_slot_capacity)}")
            if back_slots is not None and back_slot_capacity is not None:
                slot_parts.append(f"back {int(back_slots)}/{int(back_slot_capacity)}")
            if slot_parts:
                lines.append(f"  Slots: {', '.join(slot_parts)}")
    carried = list(player.get("carried", []))
    if not carried:
        lines.append(f"  {ui_text('empty_inventory', lang)}")
        return "\n".join(lines)
    lines.append("  Index  Item                   Bar        Load" if lang == "en" else "  编号   物品                   状态        负重")
    worn_index = worn_backpack_index(carried)
    for display, index, stack in carried_display_entries(player):
        item = str(stack["item"])
        lines.append(inventory_row(f"[{display}]", int(stack["qty"]), object_name(item, lang), stack, worn_on_back=index == worn_index))
        data = stack.get("data") or {}
        if isinstance(data, dict):
            for content_display, _content_index, content in storage_content_display_entries(data):
                content_item = str(content["item"])
                lines.append(
                    inventory_row(f"[{display}.{content_display}]", int(content["qty"]), object_name(content_item, lang), content)
                )
    return "\n".join(lines)


def outcome_line(snapshot: dict[str, Any], lang: str = "en") -> str | None:
    outcome = snapshot.get("outcome")
    if not outcome:
        return None
    kind = str(outcome.get("kind") or "")
    player = str(outcome.get("player") or "")
    reason = localized_outcome_reason(outcome.get("reason"), lang)
    label = ui_text(kind, lang)
    if lang == "zh":
        detail = f"{player}：{reason}" if player and reason else player or reason
        return f"{ui_text('outcome', lang)}：{label} — {detail}" if detail else f"{ui_text('outcome', lang)}：{label}"
    detail = f"{player}: {reason}" if player and reason else player or reason
    return f"{ui_text('outcome', lang)}: {label} — {detail}" if detail else f"{ui_text('outcome', lang)}: {label}"


def raft_lines(snapshot: dict[str, Any], current_location: str, lang: str = "en") -> list[str]:
    raft = snapshot.get("raft")
    if not raft or (current_location != "raft" and raft.get("event") != RAFT_EVENT_PASSING_SHIP):
        return []
    distance = int(raft.get("distance", 0))
    rescue_distance = int(raft.get("rescue_distance", RAFT_RESCUE_DISTANCE))
    progress = max(0, min(100, distance * 100 // max(1, rescue_distance)))
    if lang == "zh":
        lines = [f"  {ui_text('raft_voyage', lang)}：{distance}/{rescue_distance} {progress:3d} {_stat_bar(progress)}"]
        if raft.get("event") == RAFT_EVENT_PASSING_SHIP:
            signal = int(raft.get("signal_progress", 0))
            remaining = int(raft.get("event_remaining_minutes", 0))
            lines.append(f"  {ui_text('passing_ship', lang)}：示意 {signal}/100，剩余 {remaining} 分钟")
        return lines
    lines = [f"  {ui_text('raft_voyage', lang)}: {distance}/{rescue_distance} {progress:3d} {_stat_bar(progress)}"]
    if raft.get("event") == RAFT_EVENT_PASSING_SHIP:
        remaining = int(raft.get("event_remaining_minutes", 0))
        signal = int(raft.get("signal_progress", 0))
        lines.append(f"  {ui_text('passing_ship', lang)}: signal {signal}/100, {remaining}m left")
    return lines


def name_list(names: list[str], lang: str = "en") -> str:
    if lang == "zh":
        return "、".join(names)
    return ", ".join(names)


def sleep_lines(snapshot: dict[str, Any], player_name: str, lang: str = "en") -> list[str]:
    sleep = snapshot.get("sleep") or {}
    resting = [str(name) for name in sleep.get("resting", [])]
    waiting_for = [str(name) for name in sleep.get("waiting_for", [])]
    player = snapshot.get("players", {}).get(player_name, {})
    action = player.get("current_action")
    player_resting = isinstance(action, dict) and action.get("name") == "rest"
    if snapshot.get("paused") and (resting or player_resting):
        return [
            "  休息：世界已暂停；恢复后才会快进"
            if lang == "zh"
            else "  Rest: world is paused; resume to allow time skip"
        ]
    if sleep.get("all_resting"):
        return [
            "  休息：所有玩家都在休息，时间会快进"
            if lang == "zh"
            else "  Rest: everyone is resting; time skips ahead"
        ]
    if player_resting and waiting_for:
        names = name_list(waiting_for, lang)
        if lang == "zh":
            return [f"  休息：等待 {names} 休息；时间保持正常速度"]
        return [f"  Rest: waiting for {names}; time stays normal"]
    other_resting = [name for name in resting if name != player_name]
    if other_resting:
        names = name_list(other_resting, lang)
        if lang == "zh":
            return [f"  休息：{names} 正在休息；你仍在活动时，时间保持正常速度"]
        return [f"  Rest: {names} resting; time stays normal while you are active"]
    return []


def blocker_text(blocker: dict[str, Any], lang: str = "en") -> str:
    kind = str(blocker.get("kind", ""))
    if kind == "item":
        qty = int(blocker.get("qty", 1))
        return f"{qty} {object_name(str(blocker.get('item', 'item')), lang)}"
    if kind == "tool":
        qty = int(blocker.get("qty", 1))
        item = object_name(str(blocker.get("item", "tool")), lang)
        return f"{qty} {item}" if qty > 1 else item
    if kind == "location":
        location = object_name(str(blocker.get("name", "location")), lang)
        return f"在{location}" if lang == "zh" else f"be at {location}"
    if kind == "fire":
        return "燃着的火" if lang == "zh" else "active fire"
    if kind == "light":
        return "可用光线" if lang == "zh" else "usable light"
    if kind in {"object", "resource", "complete"}:
        return object_name(str(blocker.get("name", "object")), lang)
    if kind == "busy":
        action = localized_action_name(str(blocker.get("action", "action")), lang)
        return f"等待{action}完成" if lang == "zh" else f"{action} to finish"
    if kind == "load":
        return "减轻负重" if lang == "zh" else "lighter load"
    return object_name(str(blocker.get("name", kind or "requirement")), lang)


RECIPE_ACTION_PREFIXES = (
    "build ",
    "craft ",
    "make ",
    "mix ",
    "shape ",
    "weave ",
    "cook ",
    "brew ",
    "dry ",
    "fire ",
    "smelt ",
    "cast ",
    "hammer ",
    "grind ",
    "prepare ",
    "extract ",
    "roast ",
    "salt ",
)


def recipe_like_action(action: str) -> bool:
    data = CONTENT_ACTION_DEFS.get(action, {})
    return bool(data.get("inputs")) or action.startswith(RECIPE_ACTION_PREFIXES)


def recipe_inputs_text(action: str, lang: str = "en") -> str:
    inputs = CONTENT_ACTION_DEFS.get(action, {}).get("inputs", {})
    if not inputs:
        return "无材料" if lang == "zh" else "no materials"
    return ", ".join(f"{qty} {object_name(str(item), lang)}" for item, qty in inputs.items())


def format_recipes_panel(snapshot: dict[str, Any], lang: str = "en") -> str:
    available = [str(action) for action in snapshot.get("available_actions", []) if recipe_like_action(str(action))]
    blocked = [
        hint
        for hint in snapshot.get("blocked_actions", [])
        if recipe_like_action(str(hint.get("action", "")))
    ]
    title = "配方" if lang == "zh" else "Recipes"
    lines = [title]
    if available:
        lines.append("  可用：" if lang == "zh" else "  Available:")
        for action in available[:12]:
            lines.append(f"    {localized_action_name(action, lang)} — {recipe_inputs_text(action, lang)}")
    if blocked:
        lines.append("  缺少材料：" if lang == "zh" else "  Missing:")
        for hint in blocked[:12]:
            action = str(hint.get("action", ""))
            missing = [
                blocker_text(blocker, lang)
                for blocker in hint.get("missing", [])
                if isinstance(blocker, dict)
            ]
            if missing:
                lines.append(f"    {localized_action_name(action, lang)} — {', '.join(missing)}")
    if len(lines) == 1:
        lines.append("  暂无可显示配方" if lang == "zh" else "  No visible recipes")
    return "\n".join(lines)


def scene_player_lines(snapshot: dict[str, Any], player_name: str, current_location: str, lang: str = "en") -> list[str]:
    lines = []
    for name, player in sorted(snapshot.get("players", {}).items()):
        if name == player_name or not player.get("connected") or player.get("location") != current_location:
            continue
        detail = ui_text("survivor_here", lang)
        action = player.get("current_action")
        if isinstance(action, dict) and action.get("name"):
            action_name = str(action["name"])
            remaining = int(action.get("remaining_minutes", 0))
            if lang == "zh":
                detail = f"{detail}，正在{action_label(action_name, lang)}，剩余 {remaining} 分钟"
            else:
                detail = f"{detail}, {action_label(action_name, lang)} ({remaining}m left)"
        lines.append(f"  {name} — {detail}")
    return lines


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
    scene_lines.extend(scene_player_lines(snapshot, player_name, current, lang))
    for feature in current_loc["features"]:
        feature = str(feature)
        resource_notes = scene_resource_notes(feature, current_loc["resources"], lang)
        scene_lines.append(f"  {object_name(feature, lang)} — {feature_description(feature, resource_notes, lang)}")
    feature_names = {str(feature) for feature in current_loc["features"]}
    for card in current_loc.get("location_cards", []):
        card = str(card)
        if card in feature_names:
            continue
        scene_lines.append(f"  {object_name(card, lang)} — {location_card_description(card, lang)}")
    scene_indexes = {(kind, index): display for display, kind, index, _entry in scene_display_entries(current_loc)}
    storage_indexes = {index: display for display, index, _obj in placed_storage_display_entries(current_loc)}
    for index, obj in enumerate(current_loc["placed"]):
        kind = str(obj["kind"])
        name = object_name(kind, lang)
        if kind == "fire":
            name = f"{name}(fuel {obj['fuel']})"
        scene_lines.append(f"  [{scene_indexes[('placed', index)]}] {name} — {placed_description(obj, lang)}")
        data = obj.get("data") or {}
        storage_display = storage_indexes.get(index)
        if storage_display is not None and isinstance(data, dict):
            for content_display, _content_index, content in storage_content_display_entries(data):
                content_item = str(content["item"])
                scene_lines.append(
                    f"    [{storage_display}.{content_display}] {content['qty']} {object_name(content_item, lang)} — {item_description(content, lang, carried=True)}"
                )
    ground = list(current_loc["ground"])
    for index in range(len(ground) - 1, -1, -1):
        stack = ground[index]
        item = str(stack["item"])
        scene_lines.append(f"  [{scene_indexes[('ground', index)]}] {stack['qty']} {object_name(item, lang)} — {item_description(stack, lang)}")
    for name, location in sorted(snapshot["locations"].items()):
        if name != current and location.get("discovered", True):
            path = f"通往 {object_name(name, lang)} 的路" if lang == "zh" else f"path to {name}"
            route_description = "已发现的路线" if lang == "zh" else "discovered route"
            scene_lines.append(f"  {path} — {route_description}")
    scene_lines.extend(raft_lines(snapshot, current, lang))
    if len(scene_lines) == 1:
        scene_lines.append(f"  {ui_text('none', lang)}")
    weather = str(snapshot.get("weather", "clear"))
    canonical_weather = canonical_weather_name(weather)
    weather_def = WEATHER_DEFS.get(canonical_weather, WEATHER_DEFS["clear"])
    rain_counter = int(snapshot.get("rain_counter", RAIN_COUNTER_START))
    rain_value = int(snapshot.get("rain_value", weather_def["rain_value"]))
    sun_strength = int(snapshot.get("sun_strength", weather_def["sun_strength"]))
    season = season_name(str(snapshot.get("season", "dry")), lang)
    tide = tide_name(str(snapshot.get("tide", "low")), lang)
    light = light_name(str(snapshot.get("lights", {}).get(current, snapshot.get("light", "daylight"))), lang)
    lines = [
        ui_text("global", lang),
        f"  {clock}",
        f"  {ui_text('weather', lang)}: {weather_name(weather, lang)}; {ui_text('light', lang)}: {light}; {ui_text('tide', lang)}: {tide}",
        f"  {ui_text('season', lang)}: {season}; {ui_text('rain_counter', lang)}: {rain_counter}/{RAIN_COUNTER_MAX}; {ui_text('rain_value', lang)}: {rain_value}/5; {ui_text('sun_strength', lang)}: {sun_strength}/6",
        f"  {ui_text('paused', lang)}: {snapshot['paused']}",
        *sleep_lines(snapshot, player_name, lang),
        "",
        *scene_lines,
    ]
    line = outcome_line(snapshot, lang)
    if line:
        lines.insert(3, f"  {line}")
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
                if text in {"/crafts", "/recipes"}:
                    self.record_event(format_recipes_panel(self.snapshot, self.lang))
                    return
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
