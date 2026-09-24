# -*- coding: utf-8 -*-
"""界面风格：统一 ttk 主题、字体与间距，贴近 Windows 8.1 / Windows 10 原生观感。

做法（全部为轻量设置，不引入任何第三方依赖，保证启动速度）：
* 优先使用 ttk 的 vista 主题（Win7 起系统自带，是最接近资源管理器按钮的样式）；
* 中文字体用 Microsoft YaHei UI（Win8.1/10 简体中文系统的默认界面字体）；
* 统一按钮内边距、标签间距与输出框描边，避免默认样式那种“灰块”按钮。
"""
from __future__ import annotations

from tkinter import ttk

# Windows 8.1/10 简体中文界面的默认字体；缺失时 Tk 会自动回退
UI_FAMILY = "Microsoft YaHei UI"
UI_FONT_SIZE = 9

# 首选主题顺序：vista（Win7+） -> winnative -> xpnative -> clam（兜底）
_THEME_ORDER = ("vista", "winnative", "xpnative", "clam")

# 输出框配色（贴近 Windows 10 的浅色文本域）
OUTPUT_BG = "#FFFFFF"
OUTPUT_FG = "#1F1F1F"
OUTPUT_BORDER = "#A0A0A0"


def apply_theme(root):
    """把主题应用到根窗口；重复调用安全。"""
    style = ttk.Style(root)
    try:
        available = set(style.theme_names())
    except Exception:
        available = set()
    for candidate in _THEME_ORDER:
        if candidate in available:
            try:
                style.theme_use(candidate)
            except Exception:
                continue
            break

    style.configure(".", font=(UI_FAMILY, UI_FONT_SIZE))
    style.configure("TButton", padding=(12, 5))
    style.configure("TLabel", padding=(0, 2))
    style.configure("Status.TLabel", padding=(8, 3), foreground="#4A4A4A")
    style.configure("Hint.TLabel", foreground="#6A6A6A")
    style.configure("Section.TLabel", font=(UI_FAMILY, UI_FONT_SIZE, "bold"))

    # tk 控件（Entry / Text / ScrolledText）不归 ttk 主题管，用 option 数据库统一字体
    root.option_add("*Font", (UI_FAMILY, UI_FONT_SIZE))
    root.option_add("*Text.Font", (UI_FAMILY, UI_FONT_SIZE))
    root.option_add("*Entry.Font", (UI_FAMILY, UI_FONT_SIZE))
    return style


def ui_font(size=None, weight=None):
    """返回统一字体元组（设置页输入框等需要显式指定字体时使用）。"""
    if size is None:
        size = UI_FONT_SIZE
    if weight:
        return (UI_FAMILY, size, weight)
    return (UI_FAMILY, size)
