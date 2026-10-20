# -*- coding: utf-8 -*-
"""Reskinner Qt Demo —— 端到端换肤验证用最小 PySide6 靶场。

行为：
1. 启动时读取同目录 skins/style.qss，存在则 QApplication.setStyleSheet；
   不存在则使用内置浅色默认样式。
2. 读取同目录 config.ini 中 [ui] theme= 项，显示在状态栏。
"""
import configparser
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QTextEdit, QPushButton,
    QVBoxLayout, QWidget, QMenuBar, QToolBar, QStatusBar, QListWidgetItem,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QSS_PATH = os.path.join(BASE_DIR, "skins", "style.qss")
INI_PATH = os.path.join(BASE_DIR, "config.ini")

# 内置浅色默认样式（skins/style.qss 缺失时使用）
BUILTIN_LIGHT_QSS = """
QMainWindow { background: #f5f5f5; }
QListWidget, QTextEdit { background: #ffffff; color: #222222; }
QPushButton { background: #e0e0e0; color: #222222; padding: 4px 12px; }
"""


def load_theme():
    """返回 (theme_name, qss_text)。"""
    cfg = configparser.ConfigParser()
    theme = "unknown"
    if os.path.exists(INI_PATH):
        cfg.read(INI_PATH, encoding="utf-8")
        if cfg.has_option("ui", "theme"):
            theme = cfg.get("ui", "theme").strip()
    if os.path.exists(QSS_PATH):
        with open(QSS_PATH, "r", encoding="utf-8") as f:
            qss = f.read()
    else:
        qss = BUILTIN_LIGHT_QSS
    return theme, qss


class MainWindow(QMainWindow):
    def __init__(self, theme_name):
        super().__init__()
        self.setWindowTitle("Reskinner Qt Demo")
        self.resize(640, 420)

        # 菜单栏
        mb = QMenuBar(self)
        mb.addMenu("&File")
        mb.addMenu("&Edit")
        mb.addMenu("&Help")
        self.setMenuBar(mb)

        # 工具栏
        tb = QToolBar("Main Toolbar", self)
        tb.addAction("Open")
        tb.addAction("Save")
        tb.addAction("About")
        self.addToolBar(tb)

        # 中心部件
        central = QWidget()
        layout = QVBoxLayout(central)

        self.list = QListWidget()
        for name in ["Alpha", "Beta", "Gamma", "Delta"]:
            QListWidgetItem(name, self.list)
        layout.addWidget(self.list)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("text area ...")
        layout.addWidget(self.editor)

        self.btn = QPushButton("Click Me")
        self.btn.clicked.connect(self._on_click)
        layout.addWidget(self.btn)

        self.setCentralWidget(central)

        # 状态栏：显示当前 theme
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(f"theme = {theme_name}")
        self._theme_name = theme_name

    def _on_click(self):
        self.status.showMessage(f"clicked; theme = {self._theme_name}")


def main():
    theme, qss = load_theme()
    app = QApplication(sys.argv)
    app.setStyleSheet(qss)
    win = MainWindow(theme)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
