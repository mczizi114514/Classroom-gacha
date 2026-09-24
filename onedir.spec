# -*- mode: python ; coding: utf-8 -*-
# 文件夹版（onedir）打包配置 —— 推荐分发方式。
# 与单文件版相比：不需要在 %TEMP% 下解包，因此不会出现
# “Could not create temporary directory!” 这类引导器错误，启动也更快。
# datas 里带上 db/db，首次运行时程序会把它释放到数据目录（桌面场景为 用户目录\NC2）。


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('db/db', 'db')],
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
    [],
    exclude_binaries=True,
    name='姓名抽取器2.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='姓名抽取器2.0',
)
