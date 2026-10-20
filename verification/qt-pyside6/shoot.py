# -*- coding: utf-8 -*-
"""Qt 靶场离屏截图脚本：python shoot.py <out.png> [target_dir]
每次进程内重新加载 main.py（它启动时才读取 skins/style.qss 与 config.ini），
show -> processEvents -> grab 存 PNG。
"""
import importlib.util
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer


def main():
    out_path = sys.argv[1]
    target_dir = sys.argv[2] if len(sys.argv) > 2 else r"E:\逆向桌面级软件自定义UI\demo-targets\qt-pyside6"
    os.chdir(target_dir)

    spec = importlib.util.spec_from_file_location("qt_main", os.path.join(target_dir, "main.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    theme, qss = mod.load_theme()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(qss)
    win = mod.MainWindow(theme)
    win.resize(640, 420)
    win.show()
    # 给布局/样式计算留出事件循环时间
    for _ in range(8):
        app.processEvents()
    pix = win.grab()
    pix.save(out_path)
    print(f"saved {out_path} theme={theme} size={pix.width()}x{pix.height()}")
    app.quit()


if __name__ == "__main__":
    main()
