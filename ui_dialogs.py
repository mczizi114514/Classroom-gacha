# -*- coding: utf-8 -*-
"""弹窗集合：数据库配置（含口令）、口令修改、抽取统计（含重置）。

口令规则（conf/pwd，无后缀文件）：
* 默认没有口令 -> 数据库配置页可直接进入；
* 已设置口令 -> 进入配置页前先校验 4 位数字口令；
* 修改口令时：无口令可直接输入新口令，有口令必须先通过旧口令验证；
* 新口令必须两步输入一致（防止输错），并可选择“加密存放”（落盘 SHA-256 哈希）。
"""
from __future__ import annotations

import tkinter as tk
import unicodedata
from tkinter import messagebox, scrolledtext, ttk

import appdata
import theme

PASSWORD_LENGTH = 4          # 口令固定为 4 位数字
_PASSWORD_HINT = "请输入 4 位数字口令"


def display_width(text):
    """按显示宽度计算字符串长度（中日韩全角字符算 2 列），用于统计表对齐。"""
    width = 0
    for char in str(text):
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def pad_to(text, width):
    """把文本右侧补空格到指定显示宽度。"""
    return str(text) + " " * max(0, width - display_width(text))


def is_valid_password(text):
    """口令必须是 4 位数字。"""
    return len(str(text)) == PASSWORD_LENGTH and str(text).isdigit()


def _digit_entry(parent, variable, width=10, show=None):
    """只允许 4 位数字输入的输入框。"""
    def validate(proposed):
        return len(proposed) <= PASSWORD_LENGTH and (proposed == "" or proposed.isdigit())

    entry = ttk.Entry(parent, textvariable=variable, width=width,
                      validate="key", validatecommand=(parent.register(validate), "%P"))
    if show:
        entry.config(show=show)
    return entry


class PasswordPromptDialog(tk.Toplevel):
    """进入数据库配置页前的口令校验（仅在已设置口令时使用）。"""

    def __init__(self, master):
        super().__init__(master)
        self.title("数据库配置口令")
        self.transient(master)
        self.resizable(False, False)
        self.verified = False

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="进入数据库配置页需要口令：").pack(anchor="w")
        self.var_password = tk.StringVar()
        entry = _digit_entry(frame, self.var_password, width=12, show="●")
        entry.pack(anchor="w", pady=(6, 10))
        entry.focus_set()

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w")
        ttk.Button(buttons, text="确定", command=self._confirm).pack(side=tk.LEFT)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

        self.bind("<Return>", lambda _event: self._confirm())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        _center_on(self, master)

    def _confirm(self):
        if appdata.verify_password(self.var_password.get()):
            self.verified = True
            self.destroy()
            return
        messagebox.showerror("口令错误", "口令不正确，请重新输入。", parent=self)
        self.var_password.set("")


class ChangePasswordDialog(tk.Toplevel):
    """修改数据库配置页口令。

    * 原本无口令：直接输入新口令（两步确认）；
    * 原本有口令：先验证旧口令，再输入新口令（两步确认）；
    * 可选择存放方式：加密（SHA-256 哈希）或明文。
    """

    def __init__(self, master, on_changed=None):
        super().__init__(master)
        self.title("修改数据库配置口令")
        self.transient(master)
        self.resizable(False, False)
        self._on_changed = on_changed
        self._has_password = appdata.has_password()

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        self.var_old = tk.StringVar()
        self.var_new = tk.StringVar()
        self.var_confirm = tk.StringVar()
        self.var_encrypted = tk.BooleanVar(value=True)

        row = 0
        if self._has_password:
            ttk.Label(frame, text="旧口令:").grid(row=row, column=0, sticky="w", pady=4)
            _digit_entry(frame, self.var_old, show="●").grid(row=row, column=1, sticky="w", pady=4)
            row += 1
        else:
            ttk.Label(frame, text="当前未设置口令，可直接输入新口令。",
                      style="Hint.TLabel").grid(row=row, column=0, columnspan=2,
                                                sticky="w", pady=(0, 6))
            row += 1

        ttk.Label(frame, text="新口令:").grid(row=row, column=0, sticky="w", pady=4)
        _digit_entry(frame, self.var_new, show="●").grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Label(frame, text="确认新口令:").grid(row=row, column=0, sticky="w", pady=4)
        _digit_entry(frame, self.var_confirm, show="●").grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frame, text="存放方式:").grid(row=row, column=0, sticky="w", pady=(6, 4))
        mode_box = ttk.Frame(frame)
        mode_box.grid(row=row, column=1, sticky="w", pady=(6, 4))
        ttk.Radiobutton(mode_box, text="加密存放（哈希）", value=True,
                        variable=self.var_encrypted).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(mode_box, text="明文存放", value=False,
                        variable=self.var_encrypted).pack(side=tk.LEFT)
        row += 1

        ttk.Label(frame, text="口令固定为 %d 位数字。" % PASSWORD_LENGTH,
                  style="Hint.TLabel").grid(row=row, column=0, columnspan=2,
                                            sticky="w", pady=(6, 8))
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(buttons, text="确定", command=self._confirm).pack(side=tk.LEFT)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

        self.bind("<Return>", lambda _event: self._confirm())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        _center_on(self, master)

    def validate(self):
        """校验表单，返回错误提示文本；返回 None 表示可以提交。

        与消息框解耦，便于自动化测试直接驱动校验逻辑。
        """
        # 1) 旧口令验证（仅在已设置口令时）
        if self._has_password and not appdata.verify_password(self.var_old.get()):
            return "旧口令不正确。"
        # 2) 新口令格式
        new_password = self.var_new.get()
        if not is_valid_password(new_password):
            return _PASSWORD_HINT
        # 3) 两步验证，防止输错
        if new_password != self.var_confirm.get():
            return "两次输入的新口令不一致，请重新输入。"
        return None

    def submit(self):
        """执行保存：成功返回 None，失败返回错误提示文本。"""
        error = self.validate()
        if error is not None:
            return error
        try:
            appdata.save_password(self.var_new.get(),
                                  encrypted=bool(self.var_encrypted.get()))
        except OSError as exc:
            return "写入 conf/pwd 失败：%s" % exc
        if self._on_changed is not None:
            self._on_changed()
        return None

    def _confirm(self):
        error = self.submit()
        if error is not None:
            messagebox.showwarning("修改口令", error, parent=self)
            self.var_confirm.set("")
            return
        messagebox.showinfo("修改成功", "数据库配置页口令已更新。", parent=self)
        self.destroy()


class DatabaseDialog(tk.Toplevel):
    """配置数据库：用户输入姓名（换行分隔），点击“配置”后覆盖数据库文件 db/db。

    写入规则：
        逐个姓名 -> UTF-8 字节 -> Base64 -> 按原顺序每行一个 -> 整体覆盖 db/db。
    打开时会把当前数据库解码后回填文本框，方便增量编辑；
    右上角“修改密码”用于设置/修改进入本页所需的 4 位数字口令（conf/pwd）。
    """

    def __init__(self, master, names, on_configured=None):
        super().__init__(master)
        self.title("配置数据库")
        self.transient(master)
        self.minsize(400, 360)
        self._on_configured = on_configured

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="请输入姓名，每个姓名用换行分隔：").pack(anchor="w")
        self.text = scrolledtext.ScrolledText(
            frame, width=34, height=14, wrap=tk.NONE,
            font=theme.ui_font(), relief="solid", borderwidth=1,
            highlightthickness=0, background=theme.OUTPUT_BG, foreground=theme.OUTPUT_FG)
        self.text.pack(fill=tk.BOTH, expand=True, pady=(6, 8))

        # 底部按钮：左侧“配置/取消”，右上角“修改密码”
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="配置", command=self._configure).pack(side=tk.LEFT)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))
        self.button_password = ttk.Button(buttons, text="修改密码",
                                          command=self._change_password)
        self.button_password.pack(side=tk.RIGHT)

        if names:
            self.text.insert("1.0", "\n".join(names))
        self.text.focus_set()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        _center_on(self, master)

    def _change_password(self):
        """修改进入数据库配置页的口令（无口令时直接输入新口令）。"""
        ChangePasswordDialog(self)

    def _configure(self):
        """读取文本框内容并按 Base64 逐行覆盖数据库文件。"""
        raw = self.text.get("1.0", tk.END)
        names = [line.strip() for line in raw.splitlines() if line.strip()]
        if not names:
            messagebox.showwarning("配置数据库", "至少需要输入一个姓名。", parent=self)
            return
        try:
            appdata.save_names(names)
        except OSError as exc:
            messagebox.showerror("配置数据库", "写入数据库文件失败：%s" % exc, parent=self)
            return
        if self._on_configured is not None:
            self._on_configured(names)
        self.destroy()


class StatisticsDialog(tk.Toplevel):
    """抽取统计：显示每个姓名被抽中过的次数（数据源 db/count.db），并可整体重置。"""

    def __init__(self, master, rows, source="", on_reset=None):
        super().__init__(master)
        self.title("抽取统计")
        self.transient(master)
        self.minsize(320, 380)
        self._on_reset = on_reset

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        self.label_summary = ttk.Label(frame, text="")
        self.label_summary.pack(anchor="w")
        if source:
            ttk.Label(frame, text="数据文件：%s" % source,
                      style="Hint.TLabel").pack(anchor="w")

        self.text = scrolledtext.ScrolledText(
            frame, width=34, height=16, wrap=tk.NONE, state=tk.NORMAL,
            font=theme.ui_font(), relief="solid", borderwidth=1,
            highlightthickness=0, background=theme.OUTPUT_BG, foreground=theme.OUTPUT_FG)
        self.text.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="关闭", command=self.destroy).pack(side=tk.LEFT)
        self.button_reset = ttk.Button(buttons, text="重置统计", command=self._reset)
        self.button_reset.pack(side=tk.RIGHT)

        self.render(rows)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        _center_on(self, master)

    def render(self, rows):
        """按给定数据重绘统计表（重置统计后也会调用）。"""
        # 不展示累计抽取人次，只展示每个姓名各自的次数
        self.label_summary.config(text="共记录 %d 个姓名。" % len(rows))
        name_width = max([display_width(name) for name, _ in rows] + [display_width("姓名")])
        count_width = max([len(str(count)) for _, count in rows] + [len("次数")])
        lines = ["%s  %s" % (pad_to("姓名", name_width), "次数".rjust(count_width))]
        lines.append("-" * (name_width + count_width + 2))
        for name, count in rows:
            lines.append("%s  %s" % (pad_to(name, name_width), str(count).rjust(count_width)))
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", "\n".join(lines))
        self.text.config(state=tk.DISABLED)

    def reset_now(self):
        """立即清空抽取统计并刷新本页（供按钮与自动化测试调用）。"""
        if self._on_reset is None:
            return []
        rows = self._on_reset() or []
        self.render(rows)
        return rows

    def _reset(self):
        """重置抽取统计：确认后清空全部计数，并刷新本页显示。"""
        if self._on_reset is None:
            return
        if not messagebox.askyesno("重置统计",
                                   "确定要清空所有姓名的抽取次数吗？该操作不可撤销。",
                                   parent=self):
            return
        self.reset_now()


def _center_on(window, master):
    """把弹窗摆到主窗口中央附近，符合 Windows 对话框习惯。"""
    try:
        x = master.winfo_rootx() + (master.winfo_width() - window.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - window.winfo_height()) // 2
        window.geometry("+%d+%d" % (max(0, x), max(0, y)))
    except tk.TclError:
        pass


def ask_password(master):
    """进入数据库配置页前的口令闸门。

    默认无口令时直接放行（返回 True）；已设置口令时弹窗校验，
    返回是否通过（取消或关闭窗口均视为未通过）。
    """
    if not appdata.has_password():
        return True
    dialog = PasswordPromptDialog(master)
    master.wait_window(dialog)
    return dialog.verified
