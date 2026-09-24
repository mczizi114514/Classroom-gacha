# -*- coding: utf-8 -*-
"""界面冒烟测试：真实创建 Tk 窗口，逐项检查布局与按钮行为，最后销毁。

运行：venv\Scripts\python.exe guitest.py
测试在系统临时目录中进行（appdata.set_data_root），不会改动真实 db/ 与 conf/。
窗口以隐藏方式创建，测试过程不进入 mainloop，不会阻塞。
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import tkinter as tk

import appdata
import appconfig
import theme
from main import NameDrawerApp
from ui_dialogs import (ChangePasswordDialog, DatabaseDialog, PasswordPromptDialog,
                        StatisticsDialog, ask_password)

TIME_PATTERN = re.compile(r"\[\d{2}:\d{2}:\d{2}\]")


class Checker(object):
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


def find_widgets(parent, class_name):
    """递归收集指定 Tk 类名的子控件。"""
    found = []
    for child in parent.winfo_children():
        if child.winfo_class() == class_name:
            found.append(child)
        found.extend(find_widgets(child, class_name))
    return found


def button_texts(parent):
    return [widget.cget("text") for widget in find_widgets(parent, "TButton")]


def run():
    checker = Checker()
    c = checker
    temp_root = tempfile.mkdtemp(prefix="namepicker_guitest_")
    appdata.set_data_root(temp_root)
    os.makedirs(appdata.db_dir(), exist_ok=True)

    # 测试用内置示例名单：不读取工程内任何真实数据，保证测试自包含、可重复
    sample_names = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]
    appdata.save_names(sample_names)

    root = tk.Tk()
    root.withdraw()
    app = NameDrawerApp(root)
    root.update_idletasks()
    try:
        # —— 输入框尺寸 ×2 ——
        c.check("输入框宽度为 40（原 20 的两倍）",
                int(app.entry_count.cget("width")) == 40, app.entry_count.cget("width"))
        c.check("输入框字号为 18（原 9 的两倍，Tk 中即高度翻倍）",
                str(app.entry_count.cget("font")).find("18") >= 0,
                app.entry_count.cget("font"))

        # —— 项目名称 ——
        c.check("窗口标题为 姓名抽取器2.0", root.title() == "姓名抽取器2.0", root.title())

        # —— 主窗口按钮 ——
        texts = button_texts(root)
        c.check("主窗口按钮顺序为 开始抽取→降重重置→设置",
                texts == ["开始抽取", "降重重置", "设置"], texts)
        c.check("不再存在“重新抽取”按钮",
                not any("重新抽取" in text for text in texts), texts)
        c.check("正常模式下“降重重置”为灰色不可用",
                str(app.button_reset_decay.cget("state")) == "disabled",
                app.button_reset_decay.cget("state"))

        app.settings.mode = appconfig.MODE_WEIGHT
        app._refresh_controls()
        c.check("降重模式下“降重重置”可用",
                str(app.button_reset_decay.cget("state")) == "normal",
                app.button_reset_decay.cget("state"))
        app.settings.mode = appconfig.MODE_NORMAL
        app._refresh_controls()

        # —— 输出：最新在最上方 + 时间戳 + 历史保留 ——
        app.push_output("第一条输出")
        app.push_output("第二条输出")
        content = app.text_output.get("1.0", tk.END)
        c.check("输出保留历史内容",
                "第一条输出" in content and "第二条输出" in content, content.strip())
        c.check("最新结果排在最上方",
                content.index("第二条输出") < content.index("第一条输出"),
                content.splitlines()[:4])
        output_lines = [line for line in content.splitlines() if line.strip()]
        c.check("每条输出行都以 [hh:mm:ss] 时间戳开头",
                bool(output_lines) and all(TIME_PATTERN.match(line) for line in output_lines),
                output_lines[:3])

        # —— 抽取 + count.db ——
        app.entry_count.insert(0, "3")
        app.on_draw()
        content = app.text_output.get("1.0", tk.END)
        c.check("点击开始抽取后有结果输出", "抽取完成" in content, content.splitlines()[:3])
        c.check("抽取后生成 db/count.db", os.path.exists(appdata.count_path()))
        c.check("count.db 累计 3 人次", app.engine.total_draws() == 3, app.engine.total_draws())
        c.check("状态栏不显示累计抽取人次", "累计" not in app.label_status.cget("text"),
                app.label_status.cget("text"))

        # —— 设置页 ——
        app.on_open_settings()
        root.update_idletasks()
        win = app._settings_window
        c.check("设置页已创建", win is not None and win.winfo_exists() == 1)
        settings_texts = button_texts(win)
        for label in ("保存", "应用", "取消", "配置数据库", "重置参数", "抽取统计"):
            c.check("设置页包含“%s”按钮" % label, label in settings_texts, settings_texts)

        win.var_sp_mode.set("0")
        win._sync_stats_button()
        root.update_idletasks()
        c.check("SpMode=0 时显示“抽取统计”按钮",
                bool(win.button_stats.winfo_manager()), win.button_stats.winfo_manager())
        win.var_sp_mode.set("2")
        win._sync_stats_button()
        root.update_idletasks()
        c.check("SpMode!=0 时隐藏“抽取统计”按钮",
                not win.button_stats.winfo_manager(), win.button_stats.winfo_manager())
        win.var_sp_mode.set("0")
        win._sync_stats_button()

        win.var_mode.set(appconfig.MODE_WEIGHT)
        win.var_percent.set("33")
        win.var_sp_status.set("1")
        win.var_sp_value.set("66")
        win._collect_form()
        win._on_reset_params()
        c.check("重置参数恢复普通参数",
                win.var_mode.get() == appconfig.MODE_NORMAL and win.var_percent.get() == "80",
                (win.var_mode.get(), win.var_percent.get()))
        c.check("重置参数保留 Special 参数",
                win.var_sp_status.get() == "1" and win.var_sp_value.get() == "66",
                (win.var_sp_status.get(), win.var_sp_value.get()))

        win.var_mode.set(appconfig.MODE_WEIGHT)
        win.var_percent.set("45")
        win.var_period.set("6")
        win._on_save()
        root.update_idletasks()
        saved = appconfig.Settings().load()
        c.check("保存后 conf/conf.txt 内容生效",
                saved.mode == appconfig.MODE_WEIGHT and saved.weight_percent == 45
                and saved.seed_period == 6, saved.as_dict())
        c.check("保存后设置页关闭", not win.winfo_exists())
        c.check("主窗口已应用新设置（降重重置变为可用）",
                app.settings.is_weight_mode
                and str(app.button_reset_decay.cget("state")) == "normal",
                app.settings.mode)

        # —— 抽取统计弹窗：列表 + 重置 ——
        stats = StatisticsDialog(root, app.engine.statistics(),
                                 source=appdata.count_path(), on_reset=app._reset_statistics)
        root.update_idletasks()
        body = stats.text.get("1.0", tk.END)
        c.check("统计弹窗列出姓名与次数",
                "次数" in body and app.engine.names[0] in body, body.splitlines()[:3])
        c.check("统计弹窗不显示累计抽取人数",
                "累计" not in stats.label_summary.cget("text"),
                stats.label_summary.cget("text"))
        c.check("统计弹窗含“重置统计”按钮",
                stats.button_reset.cget("text") == "重置统计")
        before = app.engine.total_draws()
        stats.reset_now()
        c.check("统计页重置后计数清零",
                before > 0 and app.engine.total_draws() == 0,
                (before, app.engine.total_draws()))
        c.check("统计页重置后列表刷新为 0",
                all(not line.strip().endswith(("1", "2", "3"))
                    for line in stats.text.get("1.0", tk.END).splitlines()[2:] if line.strip()),
                stats.text.get("1.0", tk.END).splitlines()[:4])
        c.check("重置结果已落盘", appdata.load_counts() == {}, appdata.load_counts())
        stats.destroy()

        # —— 配置数据库弹窗 ——
        new_names = ["甲", "乙", "丙"]
        dialog = DatabaseDialog(root, new_names)
        root.update_idletasks()
        c.check("配置页含“修改密码”按钮",
                dialog.button_password.cget("text") == "修改密码")
        dialog.text.delete("1.0", tk.END)
        dialog.text.insert("1.0", "甲\n乙\n丙\n")
        dialog._configure()
        root.update_idletasks()
        raw = appdata.read_text(appdata.db_path()) or ""
        c.check("配置数据库：文件名为无后缀 db",
                os.path.basename(appdata.db_path()) == "db", appdata.db_path())
        c.check("配置数据库：db 被覆盖为 3 行 Base64",
                len([line for line in raw.splitlines() if line.strip()]) == 3
                and all(appdata.encode_name(name) in raw for name in new_names), raw)
        c.check("配置数据库：解码顺序保持",
                appdata.load_names() == new_names, appdata.load_names())

        # —— 没有数据库文件时应能直接打开配置页（默认无口令）——
        appdata.clear_password()
        c.check("默认无口令时口令闸门直接放行", ask_password(root) is True)
        appdata.atomic_write_text(appdata.db_path(), "")
        c.check("数据库为空时 has_database 为 False", appdata.has_database() is False)
        app.open_database_config()
        root.update_idletasks()
        opened = [w for w in root.winfo_children() if isinstance(w, DatabaseDialog)]
        c.check("无数据库文件时可直接弹出配置页", len(opened) == 1, len(opened))
        for item in opened:
            item.destroy()

        # —— 口令：修改（两步验证 + 加密选择）与校验 ——
        change = ChangePasswordDialog(root)
        root.update_idletasks()
        change.var_new.set("12")
        change.var_confirm.set("12")
        c.check("新口令必须是 4 位数字", change.validate() is not None, change.validate())
        change.var_new.set("1234")
        change.var_confirm.set("1235")
        c.check("两步验证能发现两次输入不一致", change.validate() is not None, change.validate())
        change.var_confirm.set("1234")
        c.check("两次输入一致时校验通过", change.validate() is None, change.validate())
        c.check("提交成功（默认加密存放）", change.submit() is None)
        change.destroy()
        c.check("口令已写入 conf/pwd",
                os.path.basename(appdata.password_path()) == "pwd"
                and appdata.verify_password("1234"), appdata.password_path())
        raw_pwd = appdata.read_text(appdata.password_path()) or ""
        c.check("加密存放不落明文口令", "1234" not in raw_pwd, raw_pwd)

        change2 = ChangePasswordDialog(root)
        root.update_idletasks()
        change2.var_old.set("0000")
        change2.var_new.set("5678")
        change2.var_confirm.set("5678")
        c.check("修改口令需要旧口令验证",
                change2.validate() == "旧口令不正确。", change2.validate())
        change2.var_old.set("1234")
        c.check("旧口令正确后校验通过", change2.validate() is None, change2.validate())
        c.check("提交新口令成功", change2.submit() is None)
        change2.destroy()
        c.check("新口令生效、旧口令失效",
                appdata.verify_password("5678") and not appdata.verify_password("1234"))

        prompt = PasswordPromptDialog(root)
        root.update_idletasks()
        prompt.var_password.set("5678")
        prompt._confirm()
        c.check("口令弹窗校验通过后置位 verified", prompt.verified is True)

        # —— 输出页不出现 Special 相关提示 ——
        all_text = app.text_output.get("1.0", tk.END)
        c.check("输出页不出现 Special 相关提示",
                all(("Special" not in all_text, "保底" not in all_text,
                     "SpMode" not in all_text, "Spvalue" not in all_text)),
                [line for line in all_text.splitlines()
                 if any(k in line for k in ("Special", "保底", "SpMode", "Spvalue"))])

        # —— 降重重置 ——
        app.engine.draw(2)
        app.on_reset_decay()
        c.check("降重重置清空降重状态", app.engine.decay_snapshot() == {},
                app.engine.decay_snapshot())
    finally:
        try:
            if app._status_job is not None:
                root.after_cancel(app._status_job)
        except tk.TclError:
            pass
        root.destroy()
        appdata.set_data_root(None)
        shutil.rmtree(temp_root, ignore_errors=True)

    print("-" * 58)
    if checker.failures:
        print("界面冒烟测试失败 %d 项：%s" % (len(checker.failures), "、".join(checker.failures)))
        return 1
    print("界面冒烟测试全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(run())
