# -*- coding: utf-8 -*-
"""设置页（独立的 Toplevel 窗口）。

布局（需求 4）：
    左上角：[保存] [应用] [取消]                右上角：[配置数据库]
    参数区（除特别说明外全部左对齐）：
        抽取模式 / 降重百分比 / 降重下限 / 随机数种子生成周期 /
        SpStatus / SpNum / SpMode（SpMode=0 时同行右侧显示 [抽取统计]）/
        Spvalue / Spvalue2
    下方正中央：[重置参数]

按钮职责：
* 保存：写 conf/conf.txt 并关闭窗口（没有修改时依然可用、照常写盘）；
* 应用：写 conf/conf.txt 并保持窗口打开；
* 取消：丢弃本次修改并关闭（窗口右上角 X 与 Esc 等同于取消，不写盘）；
* 重置参数：把除 Special 外的参数恢复默认值，Sp* 参数保持不变。

编辑策略：在设置对象的副本上编辑，只有“保存/应用”才回写到主窗口与磁盘，
因此“取消”能真正撤销本次全部改动。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import appconfig
import theme


class SettingsWindow(tk.Toplevel):
    """设置页窗口。"""

    def __init__(self, master, settings, on_apply=None,
                 on_open_database=None, on_show_statistics=None):
        super().__init__(master)
        self.title("设置 - 姓名抽取器2.0")
        self.transient(master)
        self.resizable(False, False)

        self._settings = settings
        self.work = settings.clone()          # 在工作副本上编辑，取消即丢弃
        self._on_apply = on_apply
        self._on_open_database = on_open_database
        self._on_show_statistics = on_show_statistics
        self._hint_job = None

        self._create_vars()
        self._build_widgets()
        self._load_into_form(self.work)
        self._sync_stats_button()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda _event: self._on_cancel())
        self.update_idletasks()
        self._center_on(master)

    # ------------------------------------------------------------------
    # 变量与校验
    # ------------------------------------------------------------------
    def _create_vars(self):
        """表单变量：模式用单选变量，其余用文本变量。"""
        self.var_mode = tk.StringVar(value=appconfig.MODE_NORMAL)
        self.var_percent = tk.StringVar()
        self.var_floor = tk.StringVar()
        self.var_period = tk.StringVar()
        self.var_sp_status = tk.StringVar()
        self.var_sp_num = tk.StringVar()
        self.var_sp_mode = tk.StringVar()
        self.var_sp_value = tk.StringVar()
        self.var_sp_value2 = tk.StringVar()

        # 只允许数字输入（需求 4：降重百分比等仅允许数字）
        self._vcmd_digits = (self.register(self._validate_digits), "%P")
        # SpNum 允许数字与空格（支持多个序号）
        self._vcmd_index_list = (self.register(self._validate_index_list), "%P")
        # SpMode 变化时同步“抽取统计”按钮的显示/隐藏
        self.var_sp_mode.trace_add("write", lambda *args: self._sync_stats_button())

    @staticmethod
    def _validate_digits(proposed):
        return proposed == "" or (proposed.isdigit() and len(proposed) <= 6)

    @staticmethod
    def _validate_index_list(proposed):
        if len(proposed) > 120:
            return False
        return all(char.isdigit() or char == " " for char in proposed)

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------
    def _build_widgets(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        # —— 顶部：左上三按钮 / 右上配置数据库 ——
        top = ttk.Frame(outer)
        top.pack(fill=tk.X)
        ttk.Button(top, text="保存", command=self._on_save).pack(side=tk.LEFT)
        ttk.Button(top, text="应用", command=self._on_apply_clicked).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top, text="取消", command=self._on_cancel).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top, text="配置数据库", command=self._on_open_database).pack(side=tk.RIGHT)

        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 8))

        # —— 参数区：网格 + 左对齐 ——
        form = ttk.Frame(outer)
        form.pack(fill=tk.X, anchor="w")
        form.columnconfigure(1, weight=0)

        row = 0
        # 1) 抽取模式
        ttk.Label(form, text="抽取模式:").grid(row=row, column=0, sticky="w", pady=3)
        mode_box = ttk.Frame(form)
        mode_box.grid(row=row, column=1, sticky="w", pady=3)
        for value, label in appconfig.MODE_LABELS:
            ttk.Radiobutton(mode_box, text=label, value=value,
                            variable=self.var_mode).pack(side=tk.LEFT, padx=(0, 12))
        row += 1

        # 2) 降重百分比（输入框后补百分号）
        row = self._add_entry_row(form, row, "降重百分比:", self.var_percent,
                                  suffix="%", width=8, validate="digits")
        # 3) 降重下限
        row = self._add_entry_row(form, row, "降重下限:", self.var_floor,
                                  suffix="%", width=8, validate="digits")
        # 4) 随机数种子生成周期
        row = self._add_entry_row(form, row, "随机数种子生成周期:", self.var_period,
                                  suffix="秒", width=8, validate="digits")
        # 5) SpStatus
        row = self._add_entry_row(form, row, "SpStatus:", self.var_sp_status,
                                  width=8, validate="digits")
        # 6) SpNum
        row = self._add_entry_row(form, row, "SpNum:", self.var_sp_num,
                                  width=26, validate="index_list")
        # 7) SpMode（同行右侧挂“抽取统计”按钮，仅 SpMode=0 时显示）
        ttk.Label(form, text="SpMode:").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.var_sp_mode, width=8,
                  validate="key", validatecommand=self._vcmd_digits).grid(
            row=row, column=1, sticky="w", pady=3)
        self.button_stats = ttk.Button(form, text="抽取统计", command=self._on_show_statistics)
        self.button_stats.grid(row=row, column=2, sticky="w", padx=(12, 0), pady=3)
        row += 1
        # 8) Spvalue
        row = self._add_entry_row(form, row, "Spvalue:", self.var_sp_value,
                                  width=8, validate="digits")
        # 9) Spvalue2
        row = self._add_entry_row(form, row, "Spvalue2:", self.var_sp_value2,
                                  width=8, validate="digits")

        # 提示行（左对齐）：应用/重置后的反馈文字
        self.label_hint = ttk.Label(outer, text="", style="Hint.TLabel")
        self.label_hint.pack(anchor="w", pady=(8, 0))

        # —— 底部正中央：重置参数 ——
        bottom = ttk.Frame(outer)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))
        ttk.Button(bottom, text="重置参数", command=self._on_reset_params).pack(anchor="center")

    def _add_entry_row(self, parent, row, label, variable, suffix="", width=8,
                       validate="digits"):
        """新增一行“标签 + 输入框 (+ 单位)”，全部左对齐。"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        command = self._vcmd_digits if validate == "digits" else self._vcmd_index_list
        ttk.Entry(parent, textvariable=variable, width=width,
                  validate="key", validatecommand=command).grid(
            row=row, column=1, sticky="w", pady=3)
        if suffix:
            ttk.Label(parent, text=suffix).grid(row=row, column=2, sticky="w", padx=(6, 0), pady=3)
        return row + 1

    def _center_on(self, master):
        """把设置窗口摆到主窗口中央附近，符合 Windows 对话框习惯。"""
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
            self.geometry("+%d+%d" % (max(0, x), max(0, y)))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # 表单读写
    # ------------------------------------------------------------------
    def _load_into_form(self, settings):
        self.var_mode.set(settings.mode)
        self.var_percent.set(str(settings.weight_percent))
        self.var_floor.set(str(settings.weight_floor))
        self.var_period.set(str(settings.seed_period))
        self.var_sp_status.set(str(settings.sp_status))
        self.var_sp_num.set(settings.sp_num)
        self.var_sp_mode.set(str(settings.sp_mode))
        self.var_sp_value.set(str(settings.sp_value))
        self.var_sp_value2.set(str(settings.sp_value2))

    def _collect_form(self):
        """把表单内容写回工作副本（越界值由 Settings.normalize 收敛）。"""
        self.work.update(
            mode=self.var_mode.get(),
            weight_percent=self.var_percent.get(),
            weight_floor=self.var_floor.get(),
            seed_period=self.var_period.get(),
            sp_status=self.var_sp_status.get(),
            sp_num=self.var_sp_num.get(),
            sp_mode=self.var_sp_mode.get(),
            sp_value=self.var_sp_value.get(),
            sp_value2=self.var_sp_value2.get(),
        )
        return self.work

    def _current_sp_mode(self):
        """当前表单里的 SpMode 值；非法/空值按 0 处理（决定统计按钮是否显示）。"""
        text = self.var_sp_mode.get().strip()
        return int(text) if text.isdigit() else 0

    def _sync_stats_button(self):
        """SpMode=0 时显示“抽取统计”，其他模式隐藏（需求 4.10）。"""
        if self._current_sp_mode() == 0:
            self.button_stats.grid()
        else:
            self.button_stats.grid_remove()

    # ------------------------------------------------------------------
    # 按钮事件
    # ------------------------------------------------------------------
    def _commit(self):
        """把表单写盘并通知主窗口应用新设置。"""
        settings = self._collect_form()
        try:
            settings.save()
        except OSError as exc:
            self._show_hint("写入 conf/conf.txt 失败：%s" % exc)
            return False
        self._load_into_form(settings)     # 回显收敛后的合法值
        self._sync_stats_button()
        if self._on_apply is not None:
            self._on_apply(settings.clone())
        return True

    def _on_save(self):
        """保存：写盘 + 应用 + 关闭（无修改时同样可用）。"""
        if self._commit():
            self.destroy()

    def _on_apply_clicked(self):
        """应用：写盘 + 应用，窗口保持打开。"""
        if self._commit():
            self._show_hint("已应用到 conf/conf.txt")

    def _on_cancel(self):
        """取消：丢弃本次修改并关闭，不写盘。"""
        self.destroy()

    def _on_reset_params(self):
        """重置参数：恢复除 Special 外的全部参数（Sp* 保持不变）。"""
        self.work.reset_params()
        self._load_into_form(self.work)
        self._sync_stats_button()
        self._show_hint("已重置普通参数（Special 参数保持不变），点击“保存/应用”后生效")

    def _on_open_database(self):
        """打开“配置数据库”（口令校验、写库与名单重载由主窗口统一处理）。"""
        if self._on_open_database is not None:
            self._on_open_database()

    def _on_show_statistics(self):
        if self._on_show_statistics is not None:
            self._on_show_statistics()

    def _show_hint(self, text, timeout=4000):
        """在提示行显示一段临时文字（不阻塞界面）。"""
        self.label_hint.config(text=text)
        if self._hint_job is not None:
            try:
                self.after_cancel(self._hint_job)
            except tk.TclError:
                pass
        self._hint_job = self.after(timeout, lambda: self.label_hint.config(text=""))
