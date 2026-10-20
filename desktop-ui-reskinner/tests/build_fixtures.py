# -*- coding: utf-8 -*-
"""构建 tests/fixtures 下的合成假应用与测试皮肤包。可重复运行。"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(ROOT, "fixtures")
PROJECT_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))


def w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(content, bytes):
        with open(path, "wb") as f:
            f.write(content)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)


def reset():
    if os.path.isdir(FX):
        shutil.rmtree(FX)
    os.makedirs(FX)


def build_qt():
    app = os.path.join(FX, "fake-qt")
    w(os.path.join(app, "FakeQtApp.exe"), b"MZ\x90\x00 fake exe")
    w(os.path.join(app, "Qt6Core.dll"), b"fake dll")
    w(os.path.join(app, "plugins", "platforms", "qwindows.dll"), b"fake")
    w(os.path.join(app, "skins", "style.qss"),
      "QWidget { background: #ffffff; color: #222222; }\n"
      "QPushButton { background: #eeeeee; }\n")
    w(os.path.join(app, "config.ini"), "theme=light\nlang=zh\n")


def build_electron():
    app = os.path.join(FX, "fake-electron")
    w(os.path.join(app, "FakeElectron.exe"), b"MZ\x90\x00 fake")
    w(os.path.join(app, "ffmpeg.dll"), b"fake")
    w(os.path.join(app, "locales", "en-US.pak"), b"fake pak")
    # 用 @electron/asar 真实打包 resources/app.asar
    stage = os.path.join(FX, "_electron_stage")
    w(os.path.join(stage, "package.json"), json.dumps({
        "name": "fake-app", "version": "1.0.0", "main": "main.js"
    }, indent=2))
    w(os.path.join(stage, "main.js"), "console.log('hello')\n")
    w(os.path.join(stage, "dist", "styles", "theme.css"),
      "body { background: #ffffff; color: #111; }\n")
    w(os.path.join(stage, "dist", "index.html"), "<html><link rel=stylesheet href=styles/theme.css></html>\n")
    asar_out = os.path.join(app, "resources", "app.asar")
    os.makedirs(os.path.dirname(asar_out), exist_ok=True)
    js = os.path.join(PROJECT_ROOT, "desktop-ui-reskinner", "scripts", "asar_pack.js")
    # asar_pack.js 没有打包动作, 直接用 node 调 @electron/asar
    loader = os.path.join(FX, "_pack_asar.mjs")
    with open(loader, "w", encoding="utf-8") as f:
        f.write(
            "import { pathToFileURL } from 'node:url';\n"
            "const asarDir = process.argv[2];\n"
            "const asar = await import(pathToFileURL(asarDir + '/@electron/asar/lib/asar.js').href);\n"
            "await asar.createPackage(process.argv[3], process.argv[4]);\n"
        )
    env = dict(os.environ)
    asar_dir = os.path.join(PROJECT_ROOT, ".tools", "asar", "node_modules")
    r = subprocess.run(["node", loader, asar_dir, stage, asar_out], capture_output=True,
                       text=True, env=env)
    if r.returncode != 0:
        print(r.stderr)
        raise SystemExit("asar 打包失败")
    shutil.rmtree(stage, ignore_errors=True)
    try:
        os.remove(loader)
    except OSError:
        pass


def build_wpf():
    app = os.path.join(FX, "fake-wpf")
    w(os.path.join(app, "FakeWpfApp.exe"), b"MZ\x90\x00 fake")
    w(os.path.join(app, "PresentationFramework.dll"), b"fake")
    w(os.path.join(app, "PresentationCore.dll"), b"fake")
    w(os.path.join(app, "FakeWpfApp.exe.config"),
      '<?xml version="1.0"?><configuration><startup>'
      '<supportedRuntime sku=".NETFramework,v=v4.8"/></startup></configuration>\n')


def build_skins():
    # Qt 深色皮肤
    qt_skin = os.path.join(FX, "skins", "qt-dark")
    w(os.path.join(qt_skin, "assets", "style.qss"),
      "QWidget { background: #1e1e1e; color: #dddddd; }\n"
      "QPushButton { background: #2d2d30; color: #ffffff; }\n")
    w(os.path.join(qt_skin, "skin.json"), json.dumps({
        "manifest_version": 1,
        "name": "qt-dark-synth",
        "framework": "qt",
        "version": "1.0.0",
        "author": "test",
        "description": "合成 Qt 深色皮肤(自测)",
        "target_match": {
            "signals_all": ["qt6core-dll"],
            "files_any": ["FakeQtApp.exe"]
        },
        "ops": [
            {"op": "replace_file", "src": "assets/style.qss",
             "dst": "skins/style.qss", "backup": True},
            {"op": "patch_text", "file": "config.ini", "find": "theme=light",
             "replace": "theme=dark", "must_match": 1, "encoding": "utf-8",
             "backup": True}
        ]
    }, indent=2, ensure_ascii=False))

    # asar 皮肤
    el_skin = os.path.join(FX, "skins", "electron-dark")
    w(os.path.join(el_skin, "assets", "theme.css"),
      "body { background: #111111; color: #eeeeee; }\n")
    w(os.path.join(el_skin, "skin.json"), json.dumps({
        "manifest_version": 1,
        "name": "electron-dark-synth",
        "framework": "electron",
        "version": "1.0.0",
        "author": "test",
        "description": "合成 Electron asar 换肤(自测)",
        "target_match": {
            "signals_all": ["app-asar"],
            "files_any": ["FakeElectron.exe"]
        },
        "ops": [
            {"op": "asar_replace", "archive": "resources/app.asar",
             "member": "dist/styles/theme.css", "src": "assets/theme.css",
             "backup": True}
        ]
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    reset()
    build_qt()
    build_electron()
    build_wpf()
    build_skins()
    print("fixtures built at", FX)
