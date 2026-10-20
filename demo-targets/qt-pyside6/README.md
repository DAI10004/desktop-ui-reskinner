# Qt (PySide6) 演示靶场

最小化的 PySide6 桌面程序，作为 desktop-ui-reskinner 的主验证路径。

## 运行环境

- 项目根已创建 `.venv`，并安装了 `PySide6`、`Pillow`。
- 直接用项目虚拟环境解释器运行：

```powershell
# 项目根目录下
.\.venv\Scripts\python.exe demo-targets\qt-pyside6\main.py
```

## 行为

- 窗口标题：`Reskinner Qt Demo`。
- 包含菜单栏 / 工具栏 / QListWidget（4 个条目）/ QTextEdit / QPushButton / 状态栏。
- 启动时读取 `skins/style.qss` 并 `QApplication.setStyleSheet`；该文件不存在时使用内置浅色兜底。
- 读取 `config.ini` 的 `[ui] theme=` 项并显示在状态栏。

## 当前主题

- `skins/style.qss`：浅色（白底 / 深灰字）。
- `config.ini`：`theme=light`。

配套换肤包：`examples/skin-packs/qt-dark-blue/`（深蓝暗色）。
