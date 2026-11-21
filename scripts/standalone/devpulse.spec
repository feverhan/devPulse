# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：GUI exe 与命令行 exe。"""

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

datas = [(os.path.join(ROOT, 'frontend', 'dist'), 'static')]
binaries = []
hiddenimports = []

for pkg in (
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.protocols',
    'pydantic',
    'pydantic_settings',
    'anyio',
    'sqlalchemy',
    'apscheduler',
    'httpx',
    'cryptography',
    'multipart',
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

hiddenimports += [
    'app.main',
    'app.config',
    'app.database',
    'app.models',
    'app.migrations',
    'app.security',
    'app.timeutil',
    'app.routers.auth',
    'app.routers.commits',
    'app.routers.dashboard',
    'app.routers.monitors',
    'app.routers.projects',
    'app.routers.reports',
    'app.routers.repos',
    'app.routers.reviews',
    'app.routers.settings',
    'app.routers.setup',
    'app.routers.works',
    'app.services.config_store',
    'app.services.gitplatform',
    'app.services.llm',
    'app.services.migrate',
    'app.services.monitor',
    'app.services.report',
    'app.services.review',
    'app.services.scheduler',
    'app.services.sync',
    'app.services.task_queue',
]

common_kwargs = dict(
    pathex=[os.path.join(ROOT, 'backend')],
    binaries=binaries,
    datas=datas,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pytest', 'IPython', 'notebook'],
    noarchive=False,
    optimize=0,
)

cli_a = Analysis(
    [os.path.join(ROOT, 'backend', 'standalone.py')],
    hiddenimports=hiddenimports,
    **common_kwargs,
)
gui_a = Analysis(
    [os.path.join(ROOT, 'backend', 'standalone_gui.py')],
    hiddenimports=hiddenimports + ['tkinter', 'standalone'],
    **common_kwargs,
)

cli_pyz = PYZ(cli_a.pure)
gui_pyz = PYZ(gui_a.pure)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    cli_a.binaries,
    cli_a.datas,
    [],
    name='devpulse-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    gui_a.binaries,
    gui_a.datas,
    [],
    name='devpulse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
