# -*- mode: python ; coding: utf-8 -*-
# 通用版（单文件、不内置数据库）打包配置。
# 与 main.spec 的唯一区别：datas 为空 —— exe 内部不携带任何姓名数据，
# 首次运行由“配置数据库”页面录入名单，适合分发给他人使用。
# 说明：缺少 db 时程序会走“启动即弹出数据库配置页”的分支；
#       运行数据仍然按桌面/非桌面规则放到 %USERPROFILE%\NC2 或 exe 同目录。


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='姓名抽取器2.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
