# PyInstaller build definition for the standalone AgentSmith CLI.
from pathlib import Path

root = Path(SPECPATH)
datas = [
    (str(root / 'core'), 'core'),
    (str(root / 'profiles'), 'profiles'),
    (str(root / 'config'), 'config'),
    (str(root / 'templates'), 'templates'),
    (str(root / 'skills'), 'skills'),
    (str(root / 'scripts' / 'autonomous-run.py'), 'scripts'),
]

a = Analysis(
    ['agentsmith.py'],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=['work_graph'],
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
    name='agentsmith',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
