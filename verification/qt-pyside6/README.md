# Qt/PySide6 靶场端到端验证记录

时间：2026-10-20（Asia/Shanghai）

## 环境

- Windows 11；Python 3.13 虚拟环境 `项目根\.venv`（PySide6 6.12.0 + Pillow 13.0.0）。
- 离屏渲染：`QT_QPA_PLATFORM=offscreen`，截图用 `QWidget.grab()`。
- CLI：`desktop-ui-reskinner\scripts\reskin.py`。

## 命令序列与退出码

| 步骤 | 命令（相对项目根） | 退出码 | 实际结果 |
|---|---|---|---|
| 1 before 截图 | `.venv\Scripts\python.exe verification\qt-pyside6\shoot.py verification\qt-pyside6\before.png demo-targets\qt-pyside6` | 0 | 输出 before.png，状态栏 theme=light |
| 2 plan 干跑 | `reskin.py --json plan --target demo-targets\qt-pyside6 --skin examples\skin-packs\qt-dark-blue` | **2** | 列出 2 个 op（replace_file / patch_text must_match=1），未写入 |
| 3 apply 不带 --confirm | `reskin.py --json apply --target … --skin …` | **2** | dry-run + blockers，未写入（config.ini 仍 theme=light） |
| 4 apply 确认写入 | `cd demo-targets\qt-pyside6; reskin.py --json apply --target . --skin <abs路径> --confirm --force` | 0 | replace_file 写入 847 字节暗色 QSS；patch_text 命中 1 次，theme=dark；备份到 `.reskin-backups\20261020-162936-qt-dark-blue` |
| 5 after 截图 | `shoot.py after.png` | 0 | after.png，theme=dark |
| 6 rollback | `cd demo-targets\qt-pyside6; reskin.py --json rollback --target .` | 0 | 还原 skins/style.qss 与 config.ini，hash 校验无 mismatch |
| 7 restored 截图 | `shoot.py restored.png` | 0 | restored.png，theme=light |

## 像素断言（详见 verify-report.json）

- before 平均亮度 **246.26**（近白浅色）；after **34.99**（深暗）；after/before = 0.14，远低于 0.7 阈值。
- after 通道均值 R=22.4 / G=36.1 / **B=62.18**，蓝色显著占优 → 确实换成深蓝主题。
- restored 与 before **逐像素 0 差异**（640×420），回滚字节级还原成功。

## 结论：SUCCESS（主验证路径全通）

## 已知问题 / workaround（已记入 bug 清单）

1. **containment 相对路径解析 bug**：manifest 中 `dst: skins/style.qss`、`file: config.ini` 这类相对路径，reskin.py 按进程 CWD 拼接而非按 `--target` 根拼接，CWD 不在 target 根时一律报「操作目标越出 target 根」blocked（exit 2）。临时规避：执行 apply / rollback 前 `cd` 到 target 根。
2. detect 对源码形态靶场只识别为 `confidence=low`（无 Qt6Core.dll 信号），apply 需 `--force`。

## 证据文件

- `before.png` / `after.png` / `restored.png`（真实离屏截图）
- `verify-report.json`（命令、退出码、断言数值）
- `shoot.py` / `pixstats.py` / `make_report.py`（可复跑脚本）
