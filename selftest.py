# -*- coding: utf-8 -*-
"""无界面自测：覆盖设置读写、随机数种子、降重、Special 三种模式与数据落盘。

运行方式：
    venv\Scripts\python.exe selftest.py     # 源码运行
    main.exe --selftest                     # 打包后运行，退出码 0 表示全部通过

全部用例都在系统临时目录中执行（appdata.set_data_root），不会读写真实的 db/ 与 conf/。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

import appconfig
import appdata
import drawengine

NAMES = ["张三", "李四", "王五", "赵六", "钱七"]


class Checker(object):
    """极简断言收集器：打印每条用例结果，最后汇总失败项。"""

    def __init__(self):
        self.failures = []

    def check(self, name, condition, detail=""):
        if condition:
            print("[PASS] " + name)
        else:
            message = "[FAIL] " + name
            if detail != "":
                message += "  -> " + str(detail)
            print(message)
            self.failures.append(name)


def make_engine(names, **settings):
    """构造一个使用指定设置的引擎。"""
    return drawengine.DrawEngine(list(names), appconfig.Settings(**settings))


# ----------------------------------------------------------------------
# 数据文件
# ----------------------------------------------------------------------
def test_database_file(c):
    appdata.save_names(NAMES)
    raw = appdata.read_text(appdata.db_path()) or ""
    lines = [line for line in raw.splitlines() if line.strip()]
    c.check("数据库文件名为无后缀的 db",
            os.path.basename(appdata.db_path()) == "db", appdata.db_path())
    c.check("db 行数与名单一致", len(lines) == len(NAMES), len(lines))
    c.check("db 每行都是 Base64（不出现明文姓名）",
            all(name not in raw for name in NAMES)
            and lines[0] == appdata.encode_name(NAMES[0]), lines[:1])
    c.check("db 解码顺序与写入一致", appdata.load_names() == NAMES, appdata.load_names())

    # 数据兼容：旧文件名 db/db.txt 自动迁移为 db/db
    os.remove(appdata.db_path())
    appdata.atomic_write_text(appdata.legacy_db_path(), appdata.encode_names(NAMES))
    migrated = appdata.load_names()
    c.check("旧版 db/db.txt 自动迁移为 db/db",
            migrated == NAMES and not os.path.exists(appdata.legacy_db_path()),
            (migrated, os.path.exists(appdata.legacy_db_path())))


def test_password(c):
    """数据库配置页口令：默认无口令、明文/哈希两种存放、校验规则。"""
    appdata.clear_password()
    c.check("默认无口令", appdata.has_password() is False)
    c.check("无口令时直接放行", appdata.verify_password("") is True
            and appdata.verify_password("1234") is True)

    appdata.save_password("1234", encrypted=True)
    raw = appdata.read_text(appdata.password_path()) or ""
    c.check("口令文件名为 conf/pwd（无后缀）",
            os.path.basename(appdata.password_path()) == "pwd", appdata.password_path())
    c.check("加密存放时磁盘上不出现明文口令",
            "1234" not in raw and "hash" in raw, raw)
    c.check("哈希口令：正确口令通过", appdata.verify_password("1234") is True)
    c.check("哈希口令：错误口令被拒", appdata.verify_password("1235") is False)

    appdata.save_password("4321", encrypted=False)
    raw = appdata.read_text(appdata.password_path()) or ""
    c.check("明文存放时按明文保存", "4321" in raw and "plain" in raw, raw)
    c.check("明文口令校验正确", appdata.verify_password("4321") is True)

    appdata.clear_password()
    c.check("清除口令后恢复免口令", appdata.has_password() is False)


def test_environment(c):
    """运行环境自检与首次启动初始化（管理员路径调用的 bootstrap）。"""
    c.check("环境齐备时没有缺失项", appdata.environment_missing() == [],
            appdata.environment_missing())
    shutil.rmtree(appdata.conf_dir(), ignore_errors=True)
    c.check("缺少 conf 目录时能报出缺失", appdata.environment_missing() != [],
            appdata.environment_missing())
    c.check("environment_ready 与缺失项一致",
            appdata.environment_ready() == (not appdata.environment_missing()))
    created = appdata.bootstrap()
    c.check("bootstrap 重建目录后环境恢复",
            appdata.environment_ready() and appdata.conf_dir() in created, created)
    c.check("bootstrap 不影响已有数据库", appdata.load_names() == NAMES, appdata.load_names())


def test_settings_file(c):
    settings = appconfig.Settings()
    settings.update(mode="weight", weight_percent="65", weight_floor="12",
                    seed_period="7", sp_status="1", sp_num="2 4", sp_mode="2",
                    sp_value="50", sp_value2="3")
    settings.save()
    loaded = appconfig.Settings().load()
    c.check("conf.txt 保存/加载往返一致",
            (loaded.mode, loaded.weight_percent, loaded.weight_floor, loaded.seed_period,
             loaded.sp_status, loaded.sp_num, loaded.sp_mode, loaded.sp_value,
             loaded.sp_value2) == ("weight", 65, 12, 7, 1, "2 4", 2, 50, 3),
            loaded.as_dict())

    dirty = appconfig.Settings()
    dirty.update(weight_percent="999", weight_floor="-5", seed_period="abc",
                 sp_mode="9", sp_value="x", mode="unknown")
    c.check("越界/非法输入自动收敛到合法值",
            dirty.weight_percent == 100 and dirty.weight_floor == 0
            and dirty.seed_period == 10 and dirty.sp_mode == 2
            and dirty.sp_value == 100 and dirty.mode == "normal", dirty.as_dict())

    keep = appconfig.Settings()
    keep.update(mode="weight", weight_percent="40", weight_floor="5", seed_period="3",
                sp_status="1", sp_num="1 2", sp_mode="1", sp_value="30", sp_value2="9")
    keep.reset_params()
    c.check("重置参数恢复普通参数",
            (keep.mode, keep.weight_percent, keep.weight_floor, keep.seed_period)
            == ("normal", 80, 10, 10), keep.as_dict())
    c.check("重置参数保留 Special 参数",
            (keep.sp_status, keep.sp_num, keep.sp_mode, keep.sp_value, keep.sp_value2)
            == (1, "1 2", 1, 30, 9), keep.as_dict())
    c.check("SpNum 序号解析（空格分隔/去重/排序）",
            appconfig.parse_index_list("3 1  2 2") == [1, 2, 3],
            appconfig.parse_index_list("3 1  2 2"))


# ----------------------------------------------------------------------
# 随机数种子
# ----------------------------------------------------------------------
def test_seed(c):
    seed_a = drawengine.derive_seed(1700000000)
    seed_b = drawengine.derive_seed(1700000000)
    seed_c = drawengine.derive_seed(1700000001)
    c.check("种子为 10 位十进制数", 10 ** 9 <= seed_a <= 10 ** 10 - 1, seed_a)
    c.check("同一时间戳种子稳定", seed_a == seed_b, (seed_a, seed_b))
    c.check("不同时间戳种子不同", seed_a != seed_c, (seed_a, seed_c))

    engine = make_engine(NAMES, seed_period=10)
    first = engine.seed
    c.check("周期内重复调用不更换种子",
            engine.refresh_seed() is False and engine.seed == first, first)
    expected = drawengine.derive_seed((int(time.time()) // 10) * 10)
    c.check("种子与“时间戳所在周期”一致",
            engine.refresh_seed(force=True) is True and engine.seed == expected,
            (engine.seed, expected))
    c.check("刷新倒计时在 1..周期 之间", 1 <= engine.seconds_to_next_seed() <= 10,
            engine.seconds_to_next_seed())


def test_seed_keeps_weights(c):
    """需求 5：随机数种子更新不影响已缓存的降重概率情况。"""
    engine = make_engine(NAMES, mode="weight", weight_percent=50, weight_floor=10)
    pool = engine.eligible_names()
    engine.draw(len(pool))
    before = engine.weights()
    engine.refresh_seed(force=True)
    after = engine.weights()
    c.check("种子刷新不清空降重概率缓存（同一个缓存对象）", before is after,
            (id(before), id(after)))
    c.check("种子刷新后降重数值保持不变",
            all(abs(after[name] - 0.5) < 1e-9 for name in pool), after)


# ----------------------------------------------------------------------
# 抽取池与降重
# ----------------------------------------------------------------------
def test_pool(c):
    """旧版“count<=20 时排除名单最后一人”的隐藏规则已删除。"""
    engine = make_engine(NAMES)
    c.check("可抽取池等于完整名单", engine.eligible_names() == NAMES, engine.eligible_names())
    c.check("旧版阈值常量已从引擎移除",
            not hasattr(drawengine, "LEGACY_EXCLUDE_LAST_UPTO"))
    small = make_engine(NAMES[:3])
    c.check("小名单也能抽满（旧规则下会因池只剩 2 人而报错）",
            sorted(small.draw(3)) == sorted(NAMES[:3]), small.draw(3))


def test_decay(c):
    names = NAMES[:4]
    engine = make_engine(names, mode="weight", weight_percent=50, weight_floor=10)
    pool = engine.eligible_names()
    c.check("降重模式下抽取池为完整名单", pool == names, pool)

    picked = engine.draw(4)
    c.check("同一轮内不重复且抽满", sorted(picked) == sorted(names), picked)
    weights = engine.weights()
    c.check("被抽中一次后概率降为原来的 50%",
            all(abs(weights[name] - 0.5) < 1e-9 for name in pool), weights)

    for _ in range(10):
        engine.draw(4)
    weights = engine.weights()
    c.check("降重到底后不低于降重下限（10%）",
            all(abs(weights[name] - 0.1) < 1e-9 for name in pool), weights)

    engine.reset_decay()
    c.check("降重重置后权重恢复为 1.0",
            all(abs(value - 1.0) < 1e-9 for value in engine.weights().values()),
            engine.weights())

    normal = make_engine(names, mode="normal", weight_percent=10, weight_floor=1)
    for _ in range(5):
        normal.draw(4)
    c.check("正常模式不启动降重功能",
            all(abs(value - 1.0) < 1e-9 for value in normal.weights().values()),
            normal.weights())


# ----------------------------------------------------------------------
# Special 三种模式
# ----------------------------------------------------------------------
def test_special_exclude(c):
    engine = make_engine(NAMES, sp_status=1, sp_num="2", sp_mode=0)
    c.check("SpMode=0：SpNum 指定姓名被排除",
            engine.excluded_names() == {NAMES[1]}
            and NAMES[1] not in engine.eligible_names(), engine.eligible_names())
    picked = []
    for _ in range(6):
        picked.extend(engine.draw(2))
    c.check("SpMode=0：被排除姓名永不出现", NAMES[1] not in picked, picked)


def test_special_probability(c):
    engine = make_engine(NAMES, sp_status=1, sp_num="2", sp_mode=1, sp_value=25)
    weights = engine.weights()
    c.check("SpMode=1：被选中姓名的概率为正常概率的 Spvalue%",
            abs(weights[NAMES[1]] - 0.25) < 1e-9, weights)
    c.check("SpMode=1：其他姓名概率不受影响",
            all(abs(weights[name] - 1.0) < 1e-9 for name in NAMES if name != NAMES[1]),
            weights)

    off = make_engine(NAMES, sp_status=0, sp_num="2", sp_mode=1, sp_value=25)
    c.check("SpStatus=0 时 Special 完全失效",
            all(abs(value - 1.0) < 1e-9 for value in off.weights().values()), off.weights())


def test_special_guarantee(c):
    engine = make_engine(NAMES, sp_status=1, sp_num="2", sp_mode=2,
                         sp_value=100, sp_value2=2)
    engine.load_state({}, {NAMES[1]: 2})
    picked = engine.draw(1)
    c.check("SpMode=2：达到保底次数必定抽中", picked == [NAMES[1]], picked)
    c.check("SpMode=2：保底生效后计数清零", engine.misses.get(NAMES[1]) == 0, engine.misses)

    engine.load_state({}, {NAMES[1]: 1})
    forced = engine.forced_names(engine.eligible_names(), 1)
    c.check("SpMode=2：未达保底次数不强制抽取", forced == [], forced)

    engine.load_state({}, {NAMES[1]: 2, NAMES[0]: 1})
    appdata.save_times(engine.miss_counters())
    c.check("db/times.txt 已生成", os.path.exists(appdata.times_path()))
    c.check("times.txt 只写入 SpNum 所选姓名（非 SpNum 的历史计数被过滤）",
            appdata.load_times() == {NAMES[1]: 2}, appdata.load_times())
    restored = make_engine(NAMES, sp_status=1, sp_num="2", sp_mode=2,
                           sp_value=100, sp_value2=2)
    restored.load_state(appdata.load_counts(), appdata.load_times())
    c.check("SpMode=2：保底次数重启后可继承",
            restored.misses.get(NAMES[1]) == 2, restored.misses)

    plain = make_engine(NAMES, sp_status=0, sp_num="2", sp_mode=2,
                        sp_value=100, sp_value2=2)
    plain.draw(2)
    c.check("SpStatus=0 时不维护保底计数",
            plain.misses == {} and plain.miss_tracking_enabled() is False, plain.misses)


def test_miss_tracking_scope(c):
    """保底计数机制只作用于 SpNum 所选姓名。"""
    engine = make_engine(NAMES, sp_status=1, sp_num="2 4", sp_mode=2,
                         sp_value=100, sp_value2=3)
    engine.draw(1)
    tracked = engine.miss_counters()
    c.check("保底计数只包含 SpNum 姓名",
            set(tracked) == {NAMES[1], NAMES[3]}, tracked)
    c.check("非 SpNum 姓名不进入内存计数",
            all(name not in engine.misses for name in NAMES
                if name not in (NAMES[1], NAMES[3])), engine.misses)

    off = make_engine(NAMES, sp_status=0, sp_num="2", sp_mode=2,
                      sp_value=100, sp_value2=3)
    off.draw(1)
    c.check("SpStatus=0 时不维护保底计数", off.miss_counters() == {}, off.misses)

    prob = make_engine(NAMES, sp_status=1, sp_num="2", sp_mode=1, sp_value=50)
    prob.draw(1)
    c.check("SpMode=1 时不维护保底计数", prob.miss_counters() == {}, prob.misses)


# ----------------------------------------------------------------------
# 抽取统计
# ----------------------------------------------------------------------
def test_statistics(c):
    engine = make_engine(NAMES)
    engine.load_state(appdata.load_counts(), {})
    before = engine.total_draws()
    picked = engine.draw(2)
    c.check("统计随抽取累加", engine.total_draws() == before + 2, engine.total_draws())

    appdata.save_counts(engine.counts)
    c.check("db/count.db 已生成", os.path.exists(appdata.count_path()))
    c.check("db/count.db 落盘与内存一致", appdata.load_counts() == engine.counts,
            (appdata.load_counts(), engine.counts))

    rows = engine.statistics()
    table = dict(rows)
    c.check("统计覆盖全部姓名（未被抽中显示 0）",
            len(rows) == len(NAMES) and table[picked[0]] >= 1 and table[picked[1]] >= 1, rows)

    # 统计页的“重置统计”
    engine.reset_counts()
    c.check("重置统计后内存计数清零",
            engine.total_draws() == 0
            and all(count == 0 for _, count in engine.statistics()), engine.statistics())
    appdata.save_counts(engine.counts)
    c.check("重置结果已落盘", appdata.load_counts() == {}, appdata.load_counts())


# ----------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------
def run():
    checker = Checker()
    temp_root = tempfile.mkdtemp(prefix="namepicker_selftest_")
    appdata.set_data_root(temp_root)
    print("自测数据目录：%s" % temp_root)
    try:
        test_database_file(checker)
        test_settings_file(checker)
        test_password(checker)
        test_environment(checker)
        test_seed(checker)
        test_seed_keeps_weights(checker)
        test_pool(checker)
        test_decay(checker)
        test_special_exclude(checker)
        test_special_probability(checker)
        test_special_guarantee(checker)
        test_miss_tracking_scope(checker)
        test_statistics(checker)
    finally:
        appdata.set_data_root(None)
        shutil.rmtree(temp_root, ignore_errors=True)

    print("-" * 58)
    if checker.failures:
        print("自测失败 %d 项：%s" % (len(checker.failures), "、".join(checker.failures)))
        return 1
    print("全部自测通过。")
    return 0


if __name__ == "__main__":
    sys.exit(run())
