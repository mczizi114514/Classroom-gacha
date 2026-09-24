# -*- coding: utf-8 -*-
"""抽取引擎：随机数种子、降重概率、Special 功能与抽取统计。

与旧实现（直接调用全局 random.sample）的区别：
* 随机来源改为“由时间戳派生的随机数种子”控制的私有 Random 实例；
* 每次抽中后按设置降低该姓名的权重（降重），权重带缓存；
* Special 支持“排除 / 概率调整 / 保底抽中”三种模式；
* 抽取次数与保底次数分别落盘到 db/count.db 与 db/times.txt。

状态生命周期：
* 降重状态 _decay 与权重缓存：仅存活于本次运行，启动时重置，“降重重置”可清空；
* 保底计数 _miss：只对 SpNum 选中的姓名维护，SpMode=2 时跨启动继承（db/times.txt）；
* 抽取统计 _counts：来自 db/count.db，跨启动累计。

随机数种子规则：
    当前时间戳 -> SHA-256 哈希 -> 转十进制整数 -> 取前 10 位 -> 作为 Random 种子
按“随机数种子生成周期”（默认 10 秒）刷新：把时间戳按周期分桶，桶号变化时用桶
起始时间戳重新派生种子并重新播种。种子刷新只影响后续随机流，绝不清空降重概率缓存。

关于“同一周期内是否重复”的取舍：本实现不重建 Random 对象，而是在周期边界重新播种，
继续使用同一条随机流。若每次都按同一个种子新建 Random，10 秒内连点两次“开始抽取”
会得到完全相同的名单，属于可用性退化，因此按“抽取序列由种子决定”的方式实现，
并在变更说明中注明。
"""
from __future__ import annotations

import hashlib
import random
import time

import appconfig

def derive_seed(timestamp):
    """时间戳 -> 随机数种子：SHA-256 哈希 -> 十进制值 -> 取前 10 位。

    int(hashlib.sha256(...).hexdigest(), 16) 的十进制表示固定为 77~78 位，
    因此小端截取前 10 位总是得到 10 位十进制整数（不会出现前导 0 被吞的情况）。
    """
    digest = hashlib.sha256(str(int(timestamp)).encode("utf-8")).hexdigest()
    decimal = int(digest, 16)
    return int(str(decimal)[:10])


class DrawEngine(object):
    """姓名抽取引擎。UI 只负责取值与展示，全部规则集中在类内，便于自测。"""

    def __init__(self, names=None, settings=None):
        self._names = list(names or [])
        self._settings = settings if settings is not None else appconfig.Settings()
        self._decay = {}          # 姓名 -> 本次运行内被抽中次数（降重依据，不落盘）
        self._miss = {}           # 姓名 -> 连续未抽中次数（保底依据，跨启动继承）
        self._counts = {}         # 姓名 -> 累计被抽中次数（db/count.db）
        self._special_names = set()
        self._weight_cache = None
        self._seed = None
        self._seed_bucket = None
        self._rng = random.Random()
        self._rebuild()

    # ------------------------------------------------------------------
    # 绑定与缓存
    # ------------------------------------------------------------------
    def _rebuild(self):
        """名单或设置变化后重建派生数据：Special 姓名集合 + 权重缓存失效。"""
        self._special_names = self._settings.special_names(self._names)
        self._weight_cache = None

    def bind(self, names=None, settings=None):
        """重新绑定名单/设置（名单或参数变化时调用）。"""
        if names is not None:
            self._names = list(names)
        if settings is not None:
            self._settings = settings
        self._rebuild()
        return self

    @property
    def names(self):
        return list(self._names)

    @property
    def settings(self):
        return self._settings

    @property
    def special_names(self):
        return set(self._special_names)

    @property
    def counts(self):
        return dict(self._counts)

    @property
    def misses(self):
        return dict(self._miss)

    # ------------------------------------------------------------------
    # 持久化状态
    # ------------------------------------------------------------------
    def load_state(self, counts=None, misses=None):
        """载入持久化状态：count.db 的累计抽取次数与 times.txt 的保底计数。"""
        self._counts = dict(counts or {})
        self._miss = dict(misses or {})
        return self

    def reset_decay(self):
        """重置降重概率状态（“降重重置”按钮）。不影响统计与保底计数。"""
        self._decay.clear()
        self._weight_cache = None

    def decay_snapshot(self):
        """调试/自测用：当前降重计数快照。"""
        return dict(self._decay)

    # ------------------------------------------------------------------
    # 随机数种子
    # ------------------------------------------------------------------
    def refresh_seed(self, force=False):
        """到期则刷新随机数种子，返回是否刷新。

        种子只与“当前时间戳所在周期的起始时间”有关，因此同一周期内重复调用不会
        改变种子，也绝不会触碰降重概率缓存（需求 5）。
        """
        period = max(1, int(self._settings.seed_period))
        bucket = int(time.time()) // period
        if not force and bucket == self._seed_bucket:
            return False
        self._seed_bucket = bucket
        self._seed = derive_seed(bucket * period)
        self._rng.seed(self._seed)
        return True

    @property
    def seed(self):
        self.refresh_seed()
        return self._seed

    def seconds_to_next_seed(self):
        """距离下一次种子刷新还有多少秒（状态栏展示用）。"""
        period = max(1, int(self._settings.seed_period))
        return period - int(time.time()) % period

    # ------------------------------------------------------------------
    # 权重（降重 + Special）
    # ------------------------------------------------------------------
    def _special_base(self, name):
        """Special 对基础概率的影响：SpMode=1/2 时被选中姓名是正常概率的百分之多少。"""
        settings = self._settings
        if settings.special_on and settings.sp_mode in (1, 2) and name in self._special_names:
            return max(0, int(settings.sp_value)) / 100.0
        return 1.0

    def _decay_factor(self, name):
        """降重系数：每被抽中一次乘以“降重百分比”，但不低于“降重下限”。

        正常模式下恒为 1.0（不启动降重功能）；降重模式下为
        max(下限比例, 百分比比例 ** 被抽中次数)。
        """
        settings = self._settings
        if not settings.is_weight_mode:
            return 1.0
        ratio = max(1, min(100, int(settings.weight_percent))) / 100.0
        floor = max(0, min(100, int(settings.weight_floor))) / 100.0
        return max(floor, ratio ** self._decay.get(name, 0))

    def weights(self):
        """返回 {姓名: 权重}，带缓存。

        缓存只在“名单 / 设置 / 降重状态”变化时失效；随机数种子刷新不会让它失效，
        避免每次抽取都重复计算整表权重（性能要求）。
        """
        if self._weight_cache is None:
            self._weight_cache = dict(
                (name, self._special_base(name) * self._decay_factor(name))
                for name in self._names
            )
        return self._weight_cache

    # ------------------------------------------------------------------
    # 抽取池与 Special
    # ------------------------------------------------------------------
    def excluded_names(self):
        """当前被 Special 排除、不参与抽取的姓名（SpMode=0）。"""
        if self._settings.special_on and self._settings.sp_mode == 0:
            return set(self._special_names)
        return set()

    def eligible_names(self):
        """当前可抽取池：完整名单扣除 Special SpMode=0 排除的姓名。

        旧版“抽取人数 <= 20 时排除名单最后一人”的隐藏规则已删除：现在任何抽取人数
        都从完整名单中抽取。需要排除某个姓名时，请用 SpNum + SpMode=0 显式指定。
        """
        excluded = self.excluded_names()
        return [name for name in self._names if name not in excluded]

    def forced_names(self, pool, limit):
        """SpMode=2 的保底命中名单。

        规则：累计未抽中次数达到 SpValue2 的姓名必定被抽中一次；生效一次后计数清零。
        未达到设置次数时该强制抽取不生效。
        """
        settings = self._settings
        if not (settings.special_on and settings.sp_mode == 2):
            return []
        threshold = int(settings.sp_value2)
        if threshold <= 0:
            return []
        candidates = [name for name in pool
                      if name in self._special_names and self._miss.get(name, 0) >= threshold]
        candidates.sort(key=lambda item: self._miss.get(item, 0), reverse=True)
        return candidates[:max(0, limit)]

    def miss_tracking_enabled(self):
        """是否需要维护并落盘保底计数（Special 开启、SpMode=2 且保底次数大于 0）。"""
        settings = self._settings
        return bool(settings.special_on and settings.sp_mode == 2
                    and int(settings.sp_value2) > 0)

    def _tracked_miss_names(self):
        """保底计数的作用对象：SpNum 选中、且仍在当前名单中的姓名（按名单顺序）。

        保底机制只为 SpNum 选中的姓名服务，因此计数与落盘都只覆盖这批姓名，
        其余姓名既不计数、也不会出现在 db/times.txt 中。
        """
        return [name for name in self._names if name in self._special_names]

    def miss_counters(self):
        """需要写入 db/times.txt 的保底计数（只含 SpNum 所选姓名）。

        misses 是内存里的原始快照，可能残留历史姓名或非 SpNum 姓名；
        写文件时统一用它过滤，保证 times.txt 的语义与需求一致。
        """
        if not self.miss_tracking_enabled():
            return {}
        return dict((name, int(self._miss.get(name, 0)))
                    for name in self._tracked_miss_names())

    # ------------------------------------------------------------------
    # 抽样
    # ------------------------------------------------------------------
    def _weighted_sample(self, pool, need):
        """按权重不放回抽样，保持旧版“同一轮内不重复”的语义。

        权重全为 0 时（例如 Spvalue=0）退化为等概率，保证功能仍可用不崩溃。
        """
        weights = self.weights()
        entries = [(name, max(0.0, float(weights.get(name, 1.0)))) for name in pool]
        picked = []
        for _ in range(need):
            if not entries:
                break
            total = sum(weight for _, weight in entries)
            if total <= 0:
                index = self._rng.randrange(len(entries))
            else:
                target = self._rng.random() * total
                accumulated = 0.0
                index = len(entries) - 1
                for position, (_, weight) in enumerate(entries):
                    accumulated += weight
                    if target <= accumulated:
                        index = position
                        break
            picked.append(entries.pop(index)[0])
        return picked

    def draw(self, count):
        """执行一次抽取，返回被抽中的姓名列表（按抽中顺序）。"""
        if count <= 0:
            raise ValueError("抽取数量必须大于 0")
        self.refresh_seed()
        pool = self.eligible_names()
        if not pool:
            raise ValueError("没有可抽取的姓名")
        if count > len(pool):
            raise ValueError("抽取数量 (%d) 超出了可抽取范围 (%d)" % (count, len(pool)))

        forced = self.forced_names(pool, count)
        picked = list(forced)
        if len(picked) < count:
            forced_set = set(forced)
            remaining = [name for name in pool if name not in forced_set]
            picked.extend(self._weighted_sample(remaining, count - len(picked)))
        self._apply_result(picked)
        return picked

    def _apply_result(self, picked):
        """抽取后更新内存状态：降重计数、保底计数、抽取统计。"""
        picked_set = set(picked)
        if self._settings.is_weight_mode:
            # 仅在降重模式下累计降重计数（正常模式不启动降重功能）
            for name in picked:
                self._decay[name] = self._decay.get(name, 0) + 1
            self._weight_cache = None       # 权重变化，缓存失效
        for name in picked:
            self._counts[name] = self._counts.get(name, 0) + 1
        if self.miss_tracking_enabled():
            # 保底计数只统计 SpNum 选中的姓名：只有它们才有“必定抽中一次”的保底，
            # 非 SpNum 姓名完全不参与计数，也不会被写进 db/times.txt。
            for name in self._tracked_miss_names():
                if name in picked_set:
                    self._miss[name] = 0    # 抽中（含保底强制抽中）即清零
                else:
                    self._miss[name] = self._miss.get(name, 0) + 1

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def reset_counts(self):
        """清空抽取统计（“抽取统计”页的重置功能）；不影响降重与保底状态。"""
        self._counts.clear()

    def statistics(self):
        """按名单顺序返回 [(姓名, 被抽中次数), ...]，未被抽中过显示 0。"""
        return [(name, int(self._counts.get(name, 0))) for name in self._names]

    def total_draws(self):
        """累计抽取人次（含已从名单中移除的历史姓名）。"""
        return sum(int(value) for value in self._counts.values())
