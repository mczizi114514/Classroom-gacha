# -*- coding: utf-8 -*-
"""设置项模型：conf/conf.txt 的读写、默认值与参数重置。

文件格式（UTF-8，每行一条，便于用户手工编辑）：
    键=值
    # 开头为注释行

兼容策略：未知键忽略、缺失键取默认值，因此旧配置文件、被手工删行的配置文件
都能正常加载；数值越界自动收敛到合法区间，避免脏配置导致抽取异常。

参数归属：
* 普通参数：mode / weight_percent / weight_floor / seed_period —— “重置参数”会恢复默认；
* Special 参数：sp_status / sp_num / sp_mode / sp_value / sp_value2 ——
  “重置参数”刻意不动它们（需求明确要求重置时排除 Special 功能）。
"""
from __future__ import annotations

import appdata

MODE_NORMAL = "normal"
MODE_WEIGHT = "weight"
MODE_LABELS = ((MODE_NORMAL, "正常模式"), (MODE_WEIGHT, "降重模式"))
MODE_ORDER = (MODE_NORMAL, MODE_WEIGHT)

# 默认参数（“重置参数”恢复到这里；Special 参数除外）
DEFAULTS = {
    "mode": MODE_NORMAL,
    "weight_percent": 80,
    "weight_floor": 10,
    "seed_period": 10,
    "sp_status": 0,
    "sp_num": "",
    "sp_mode": 0,
    "sp_value": 100,
    "sp_value2": 5,
}

# Special 功能相关键：重置参数时保留
SPECIAL_KEYS = ("sp_status", "sp_num", "sp_mode", "sp_value", "sp_value2")

# 参数取值范围：(最小值, 最大值)
RANGES = {
    "weight_percent": (1, 100),
    "weight_floor": (0, 100),
    "seed_period": (1, 3600),
    "sp_status": (0, 1),
    "sp_mode": (0, 2),
    "sp_value": (0, 1000),
    "sp_value2": (0, 9999),
}

# 写文件时的字段顺序与行内注释（顺序即 conf.txt 中的呈现顺序）
FIELD_COMMENTS = (
    ("mode", "抽取模式：normal=正常模式（不降重），weight=降重模式"),
    ("weight_percent", "降重百分比：被抽中一次后，该姓名概率变为原来的百分之多少（1-100）"),
    ("weight_floor", "降重下限：降重后概率最低不低于原概率的百分之多少（0-100）"),
    ("seed_period", "随机数种子生成周期：单位秒，默认 10 秒刷新一次种子"),
    ("sp_status", "Special 开关：0=关闭，1=开启（正常模式与降重模式都受它影响）"),
    ("sp_num", "Special 作用对象：db 中第几个姓名（从 1 开始），多个用空格分隔"),
    ("sp_mode", "Special 模式：0=不被抽取，1=概率受 Spvalue 影响，2=在 1 基础上增加保底"),
    ("sp_value", "SpMode=1/2 时，被选中姓名的概率为正常概率的百分之多少"),
    ("sp_value2", "SpMode=2 时的保底次数：累计这么多次没抽中后必定抽中一次"),
)

FILE_HEADER = (
    "# 姓名抽取器 配置文件（UTF-8，每行一条 “键=值”，可直接编辑）\n"
    "# 在设置页点击“保存”或“应用”后写回本文件；删除某行则该参数回到默认值。\n"
)


def _to_int(value, key, default=None):
    """把任意输入转成整数并按 RANGES 收敛；无法解析时返回默认值。"""
    fallback = DEFAULTS[key] if default is None else default
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    low, high = RANGES[key]
    return max(low, min(high, number))


def parse_index_list(text):
    """解析 SpNum 文本（如 “1 3 5”）为 1 起始的序号列表。

    规则：空格分隔、忽略非数字项、去重、保持升序，非法序号在取姓名时再过滤。
    """
    result = []
    for token in str(text or "").replace(",", " ").replace("，", " ").split():
        if token.isdigit():
            index = int(token)
            if index > 0 and index not in result:
                result.append(index)
    result.sort()
    return result


class Settings(object):
    """内存中的设置项；属性名与 conf.txt 的键一一对应。"""

    def __init__(self, **kwargs):
        self.mode = MODE_NORMAL
        self.weight_percent = DEFAULTS["weight_percent"]
        self.weight_floor = DEFAULTS["weight_floor"]
        self.seed_period = DEFAULTS["seed_period"]
        self.sp_status = DEFAULTS["sp_status"]
        self.sp_num = DEFAULTS["sp_num"]
        self.sp_mode = DEFAULTS["sp_mode"]
        self.sp_value = DEFAULTS["sp_value"]
        self.sp_value2 = DEFAULTS["sp_value2"]
        if kwargs:
            self.update(**kwargs)

    # -- 基本操作 ---------------------------------------------------------
    def clone(self):
        """复制一份（设置页在副本上编辑，取消即丢弃）。"""
        return Settings(**self.as_dict())

    def as_dict(self):
        return {
            "mode": self.mode,
            "weight_percent": self.weight_percent,
            "weight_floor": self.weight_floor,
            "seed_period": self.seed_period,
            "sp_status": self.sp_status,
            "sp_num": self.sp_num,
            "sp_mode": self.sp_mode,
            "sp_value": self.sp_value,
            "sp_value2": self.sp_value2,
        }

    def update(self, **kwargs):
        """批量赋值并统一做一次合法性收敛。"""
        for key, value in kwargs.items():
            if key in DEFAULTS:
                setattr(self, key, value)
        self.normalize()
        return self

    def normalize(self):
        """把全部字段收敛到合法范围（脏配置、手工改文件都不会破坏运行）。"""
        if self.mode not in MODE_ORDER:
            self.mode = MODE_NORMAL
        for key in ("weight_percent", "weight_floor", "seed_period",
                    "sp_status", "sp_mode", "sp_value", "sp_value2"):
            setattr(self, key, _to_int(getattr(self, key), key))
        self.sp_num = " ".join(str(i) for i in parse_index_list(self.sp_num))
        return self

    def reset_params(self):
        """重置除 Special 功能外的所有可设置参数（需求 4 的“重置参数”）。"""
        for key, value in DEFAULTS.items():
            if key in SPECIAL_KEYS:
                continue
            setattr(self, key, value)
        return self.normalize()

    # -- 派生信息 ---------------------------------------------------------
    @property
    def special_on(self):
        return bool(self.sp_status)

    @property
    def is_weight_mode(self):
        return self.mode == MODE_WEIGHT

    @property
    def mode_label(self):
        return dict(MODE_LABELS).get(self.mode, "正常模式")

    def special_indexes(self):
        return parse_index_list(self.sp_num)

    def special_names(self, names):
        """SpNum 序号 -> 姓名集合（1 起始；越界序号直接忽略）。"""
        result = set()
        for index in self.special_indexes():
            if 1 <= index <= len(names):
                result.add(names[index - 1])
        return result

    # -- 持久化 -----------------------------------------------------------
    def to_text(self):
        """序列化成 conf.txt 文本（含行内注释，便于手工维护）。"""
        lines = [FILE_HEADER]
        for key, comment in FIELD_COMMENTS:
            lines.append("# %s\n" % comment)
            lines.append("%s=%s\n" % (key, getattr(self, key)))
        return "".join(lines)

    def save(self):
        """写回 conf/conf.txt（原子替换）。"""
        appdata.save_conf_text(self.to_text())

    def load(self):
        """从 conf/conf.txt 加载；文件不存在或损坏时保持默认值。"""
        text = appdata.load_conf_text()
        data = parse_conf_text(text)
        for key in DEFAULTS:
            if key in data:
                setattr(self, key, data[key])
        return self.normalize()


def parse_conf_text(text):
    """解析 “键=值” 文本，返回原始字符串字典（类型转换交给 normalize）。"""
    data = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in DEFAULTS:
            data[key] = value.strip()
    return data


def load_settings():
    """便捷入口：加载设置（供 main.py 使用）。"""
    return Settings().load()
