# -*- coding: utf-8 -*-
"""姓名抽取器2.0 —— 主窗口。

界面结构：
    请输入要抽取的人数:   [输入框：原宽 20 字符 ×2 = 40，字体 9pt ×2 = 18pt]
    [开始抽取] [降重重置] [设置]        <- 顺序固定，左对齐
    [输出框：最新结果插入到最上方，历史内容保留，每行带 [hh:mm:ss] 时间戳]
    [状态栏：模式 / 当前随机种子 / 下次刷新倒计时 / 可抽取人数]

按钮职责：
* 开始抽取：按当前设置执行一次抽取，结束后写 db/count.db；
* 降重重置：清空降重概率状态，仅降重模式可用（正常模式灰色禁用）；
* 设置：打开设置页（参数存 conf/conf.txt，其中“配置数据库”入口会先做口令校验）。

启动流程：
1) 运行环境自检：缺少 db/、conf/ 目录时提示“需要使用管理员身份运行”，确定后关闭进程；
   以管理员身份启动则由 appdata.bootstrap() 自动创建（桌面场景数据落在 用户目录\\NC2）；
2) 加载 conf/conf.txt、db/db、db/count.db、db/times.txt；
3) 数据库文件为空（或不存在）时，直接弹出数据库配置页供录入姓名。

输出页约定：只展示抽取结果、设置变更与加载状态，不出现任何 Special 功能相关提示。
"""
from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import appconfig
import appdata
import theme
import ui_dialogs
from drawengine import DrawEngine
from ui_dialogs import DatabaseDialog, StatisticsDialog, ask_password
from ui_settings import SettingsWindow

APP_TITLE = "姓名抽取器2.0"


class NameDrawerApp(object):
    """主窗口控制器：持有设置、引擎与全部界面回调。"""

    WINDOW_TITLE = APP_TITLE
    WINDOW_GEOMETRY = "640x560"
    STATUS_INTERVAL_MS = 1000

    # 旧版 tk.Entry 默认宽 20 字符、字体 9pt，按“长宽各两倍”调整。
    ENTRY_WIDTH_CHARS = 40
    ENTRY_FONT_SIZE = theme.UI_FONT_SIZE * 2

    def __init__(self, root):
        self.root = root
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry(self.WINDOW_GEOMETRY)
        self.root.minsize(520, 420)

        theme.apply_theme(self.root)

        # 设置与数据：设置来自 conf/conf.txt，名单来自数据库文件 db/db
        self.settings = appconfig.load_settings()
        self.engine = DrawEngine(appdata.load_names(), self.settings)
        # 统计与保底计数跨启动继承（降重状态刻意不继承，每次启动重置）
        self.engine.load_state(appdata.load_counts(), appdata.load_times())

        self._settings_window = None
        self._status_job = None

        self._build_ui()
        self._refresh_controls()
        self.push_output("初始化完成！总共加载了 %d 个姓名。" % len(self.engine.names))
        self._schedule_status()

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        # —— 顶部输入区（左对齐）——
        top = ttk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(top, text="请输入要抽取的人数:").pack(anchor="w")
        self.entry_count = ttk.Entry(top, width=self.ENTRY_WIDTH_CHARS,
                                     font=theme.ui_font(self.ENTRY_FONT_SIZE))
        self.entry_count.pack(anchor="w", pady=(4, 0))
        self.entry_count.bind("<Return>", lambda _event: self.on_draw())

        # —— 按钮区：顺序为 开始抽取 -> 降重重置 -> 设置 ——
        actions = ttk.Frame(self.root)
        actions.pack(side=tk.TOP, fill=tk.X, padx=12)
        self.button_draw = ttk.Button(actions, text="开始抽取", command=self.on_draw)
        self.button_draw.pack(side=tk.LEFT)
        self.button_reset_decay = ttk.Button(actions, text="降重重置",
                                             command=self.on_reset_decay)
        self.button_reset_decay.pack(side=tk.LEFT, padx=(8, 0))
        self.button_settings = ttk.Button(actions, text="设置", command=self.on_open_settings)
        self.button_settings.pack(side=tk.LEFT, padx=(8, 0))

        # —— 状态栏（先占住底部，再放可伸缩的输出区）——
        self.label_status = ttk.Label(self.root, anchor="w", style="Status.TLabel")
        self.label_status.pack(side=tk.BOTTOM, fill=tk.X)

        # —— 输出区：最新结果在最上方，历史内容保留 ——
        output_box = ttk.Frame(self.root)
        output_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(10, 6))
        self.text_output = scrolledtext.ScrolledText(
            output_box, wrap=tk.WORD, state=tk.DISABLED, height=10,
            font=theme.ui_font(), relief="solid", borderwidth=1, highlightthickness=0,
            background=theme.OUTPUT_BG, foreground=theme.OUTPUT_FG)
        self.text_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 时间戳单独着色，贴近 Windows 日志观感
        self.text_output.tag_config("time", foreground="#0A66C2")

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------
    def push_output(self, message):
        """把新输出插入到输出框最上方（最新结果在最上面一排），历史内容保留。

        每条（每行）输出前都加 [hh:mm:ss] 时间戳，并把时间戳单独着色。
        """
        stamp = time.strftime("[%H:%M:%S]") + " "
        lines = [line for line in str(message).split("\n") if line != ""]
        if not lines:
            return
        payload = "".join(stamp + line + "\n" for line in lines)
        self.text_output.config(state=tk.NORMAL)
        self.text_output.insert("1.0", payload)
        for offset in range(len(lines)):
            line_index = "%d.0" % (offset + 1)
            self.text_output.tag_add("time", line_index,
                                     "%s+%dc" % (line_index, len(stamp)))
        self.text_output.see("1.0")
        self.text_output.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # 抽取
    # ------------------------------------------------------------------
    def on_draw(self):
        """“开始抽取”：校验输入 -> 抽取 -> 落盘 -> 输出结果。"""
        raw = self.entry_count.get().strip()
        if not raw:
            self.push_output("请输入一个数字！")
            return
        if not raw.isdigit():
            self.push_output("请输入一个有效的数字！")
            return
        count = int(raw)
        if count <= 0:
            self.push_output("请输入一个大于0的数字！")
            return

        total = len(self.engine.names)
        pool = self.engine.eligible_names()
        if count > total:
            self.push_output("抽取数量 (%d) 不能超过总人数 (%d)！" % (count, total))
            return
        if count > len(pool):
            self.push_output("抽取数量 (%d) 超出了有效范围 (总数 %d, 可抽取 %d)！"
                             % (count, total, len(pool)))
            return

        try:
            picked = self.engine.draw(count)
        except Exception as exc:                      # 兜底：任何异常都只提示不崩溃
            self.push_output("抽取过程中发生错误: %s" % exc)
            return

        self._persist_after_draw()
        lines = ["抽取完成！抽中的 %d 个姓名是：" % count]
        lines.extend(picked)
        self.push_output("\n".join(lines))
        self._update_status()

    def _persist_after_draw(self):
        """抽取后的落盘：统计必写，保底计数在需要时写。

        只在这两处写盘，避免无谓 I/O；写入均为原子替换，防止半截文件。
        提示文案不出现 Special 相关字眼（输出页约定）。
        """
        try:
            appdata.save_counts(self.engine.counts)
        except OSError as exc:
            self.push_output("数据保存失败：%s" % exc)
        if self.engine.miss_tracking_enabled():
            try:
                appdata.save_times(self.engine.miss_counters())
            except OSError as exc:
                self.push_output("数据保存失败：%s" % exc)

    def on_reset_decay(self):
        """“降重重置”：清空降重概率状态。"""
        if not self.settings.is_weight_mode:
            self.push_output("正常模式下不启用降重功能。")
            return
        self.engine.reset_decay()
        self.push_output("已重置降重概率状态。")
        self._update_status()

    # ------------------------------------------------------------------
    # 设置与数据库
    # ------------------------------------------------------------------
    def on_open_settings(self):
        """打开设置页；已打开时前置而不是重复创建。"""
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.deiconify()
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        self._settings_window = SettingsWindow(
            self.root, self.settings,
            on_apply=self._on_settings_applied,
            on_open_database=self._open_database_from_settings,
            on_show_statistics=self._show_statistics)

    def _on_settings_applied(self, settings):
        """设置页“保存/应用”后回调：换用新设置并刷新与模式相关的界面状态。"""
        self.settings = settings
        self.engine.bind(names=self.engine.names, settings=self.settings)
        self._refresh_controls()
        self._update_status()
        self.push_output("设置已更新：模式=%s，降重百分比=%d%%，降重下限=%d%%，种子周期=%d 秒。"
                         % (self.settings.mode_label, self.settings.weight_percent,
                            self.settings.weight_floor, self.settings.seed_period))

    def open_database_config(self, master=None):
        """打开数据库配置页：设置了口令时先校验 4 位数字口令。"""
        parent = master if master is not None else self.root
        if not ask_password(parent):
            return
        DatabaseDialog(parent, appdata.load_names(),
                       on_configured=self._on_database_configured)

    def _open_database_from_settings(self):
        """设置页里的“配置数据库”入口：以设置页为父窗口。"""
        parent = self._settings_window
        if parent is None or not parent.winfo_exists():
            parent = self.root
        self.open_database_config(parent)

    def _on_database_configured(self, names):
        """配置数据库完成后重新加载名单。

        抽取统计与保底计数按姓名保留，因此重建名单不会丢失历史数据。
        """
        self.engine.bind(names=list(names))
        self.push_output("数据库已更新，共 %d 个姓名。" % len(names))
        self._update_status()

    # ------------------------------------------------------------------
    # 抽取统计
    # ------------------------------------------------------------------
    def _show_statistics(self):
        """“抽取统计”：展示每个姓名的被抽中次数，并支持重置。"""
        parent = self._settings_window
        if parent is None or not parent.winfo_exists():
            parent = self.root
        StatisticsDialog(parent, self.engine.statistics(),
                         source=appdata.count_path(), on_reset=self._reset_statistics)

    def _reset_statistics(self):
        """重置抽取统计（清空 db/count.db 并落盘），返回重置后的统计行。"""
        self.engine.reset_counts()
        try:
            appdata.save_counts(self.engine.counts)
        except OSError as exc:
            self.push_output("数据保存失败：%s" % exc)
        self.push_output("已重置抽取统计。")
        return self.engine.statistics()

    # ------------------------------------------------------------------
    # 状态与模式联动
    # ------------------------------------------------------------------
    def _refresh_controls(self):
        """正常模式下“降重重置”灰色不可用。"""
        state = tk.NORMAL if self.settings.is_weight_mode else tk.DISABLED
        self.button_reset_decay.config(state=state)

    def _schedule_status(self):
        """状态栏每秒刷新一次（轻量，仅更新一段文本，不影响界面流畅度）。"""
        self._update_status()
        self._status_job = self.root.after(self.STATUS_INTERVAL_MS, self._schedule_status)

    def _update_status(self):
        """状态栏文本：模式、随机种子与刷新倒计时、可抽取人数（不展示累计抽取人次）。"""
        self.engine.refresh_seed()     # 到期自动更换种子；不会清空降重概率缓存
        self.label_status.config(
            text="模式：%s ｜ 随机种子：%s（%d 秒后刷新）｜ 可抽取：%d 人"
            % (self.settings.mode_label, self.engine.seed,
               self.engine.seconds_to_next_seed(),
               len(self.engine.eligible_names())))


def _warn_need_admin(missing):
    """缺少运行环境且非管理员时提示，并在确定后关闭进程。"""
    root = tk.Tk()
    root.withdraw()
    messagebox.showwarning(
        APP_TITLE,
        "检测到运行环境不完整，缺少以下目录：\n\n    %s\n\n"
        "请关闭本程序后，右键选择“以管理员身份运行”重新启动；\n"
        "程序会自动创建所需的文件与目录，之后即可正常使用。"
        % "\n    ".join(missing))
    root.destroy()


def prepare_environment():
    """首次启动环境自检。

    返回 True 表示可以继续启动；返回 False 表示需要用户以管理员身份重新运行。
    桌面场景下数据目录为 用户目录\\NC2，其他场景与程序同目录。
    """
    missing = appdata.environment_missing()
    if missing:
        if not appdata.is_admin():
            _warn_need_admin(missing)
            return False
        appdata.bootstrap()
    if not os.path.exists(appdata.conf_path()):
        appconfig.Settings().save()
    return True


def main(argv=None):
    """程序入口；支持 --selftest（无界面自测，供构建后验证）。"""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in arguments:
        import selftest
        return selftest.run()

    if not prepare_environment():
        return 1

    root = tk.Tk()
    app = NameDrawerApp(root)
    if not appdata.has_database():
        # 启动时没有数据库文件：直接弹出数据库配置页供录入
        root.after(200, app.open_database_config)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
