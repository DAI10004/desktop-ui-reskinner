# Qt 路线速查

## 识别
- 信号：`Qt6Core.dll`/`Qt5Core.dll`、`plugins/platforms/qwindows.dll`、`PySide6/PyQt6/PyQt5/PySide2` 目录、外部 `*.qss`、`*.rcc`。
- 标杆案例：OBS Studio（`obs64.exe`，官方主题在 `data/obs-studio/themes/*.qss`，用户主题放 `%APPDATA%\obs-studio\themes\`）。

## UI 层入口
- 外部 `.qss` 样式表（CSS2 子集）——**唯一推荐换肤入口**，用 `replace_file`。
- 外部 `.rcc` 资源包——`QResource::registerResource` 注册，可替换磁盘文件。
- 内嵌 `qrc:/` 资源——在 exe 里，本工具箱**不改**。

## 命令示例
```bash
python scripts/reskin.py --json detect --target "C:\Program Files\obs-studio"
python scripts/reskin.py --json plan    --target ... --skin templates/qt
# 给用户看 plan、拿到同意后：
python scripts/reskin.py --json apply   --target ... --skin templates/qt --confirm
python scripts/reskin.py --json rollback --target ...
```

## 坑
- QSS 写了控件不变色：代码里硬编码了 `setStyleSheet`/palette，子级覆盖全局。
- 改图标发白：图标来自内嵌 qrc，仅换色不够。
- PyInstaller 打包的程序：主题资源没打进 bundle，应走 `%APPDATA%` 用户目录而非 bundle。
- 外部 .rcc 改了不生效：说明 exe 内嵌了副本，改磁盘 .rcc 不等于改 exe。

## 合规
- 只对自有/开源/官方开放主题机制的软件操作（OBS 是 GPLv2，用户目录放主题完全合规）。
- 不反编译商业软件内嵌 QSS 重打包分发；PyQt-Fluent-Widgets 商用需商业授权。
