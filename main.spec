# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：单文件、无控制台窗口。
# datas 里带上 db/db.txt，使 exe 独立可用：首次运行时 appdata 会把它复制到
# exe 同级的 db/ 目录，之后数据一律读写 exe 所在目录，不再依赖 os.getcwd()。


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
    a.binaries,
    a.datas,
    [],
    name='main',
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
