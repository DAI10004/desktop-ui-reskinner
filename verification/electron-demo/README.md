# Electron 靶场端到端验证记录

时间：2026-10-20（Asia/Shanghai）

## 环境

- 依赖装在 `.tools\electron-deps`（`electron@44.9.1` + `@electron/asar@4.3.1`，npmmirror）。
- 构建：`demo-targets\electron-demo\build.ps1`（幂等）：electron dist 整体复制为 `App/`，删除 `default_app.asar`，`asar pack app-src -> App/resources/app.asar`。
- 运行：`App\electron.exe`（窗口标题 `Reskinner Electron Demo`，800x600）。

## 命令序列与退出码

| 步骤 | 命令 | 退出码 | 结果 |
|---|---|---|---|
| build | `powershell -File demo-targets\electron-demo\build.ps1` | 0 | App/electron.exe 与 app.asar 产出 |
| detect | `reskin.py --json detect --target App` | 0 | framework=electron，**confidence=high**（app-asar 信号 0.95） |
| before 截图 | `shoot_win.py App\electron.exe before.png ...` | 0 | 进程可启动；PrintWindow 只截到窗口框架（标题栏+原生菜单），客户区空白 |
| plan 干跑 | `cd App; reskin.py --json plan --target . --skin <electron-dark>` | 2 | 列出 asar_replace，风险标签正常，未写入 |
| apply 不带 --confirm | `reskin.py --json apply --target . --skin ...` | 2 | 无 blocker（high confidence），未写入 |
| apply --confirm | `cd App; reskin.py --json apply --target . --skin <abs> --confirm` | 0 | asar_replace 成功，备份 `.reskin-backups\20261020-163304-electron-dark` |
| 归档级 after 断言 | `asar.extractFile(app.asar, "dist\styles\theme.css")` | 0 | 成员内容变为暗色（570 字节，`#0e1626` / `#d7e6ff`） |
| 运行时 after 截图 | `shoot_win.py` / `shoot_screen.py` | — | **未能取得有效客户区像素**（见下） |
| rollback | `cd App; reskin.py --json rollback --target .` | 0 | app.asar 还原，mismatches=[] |
| 归档级还原断言 | 重新提取成员 | 0 | 内容回到浅色（581 字节，`#f5f5f0`），asar mtime 回到构建时刻 16:27:45；成员集合不变（6 项） |

## 为什么是「降级」

- Electron 窗口**能正常启动**（标题栏、原生菜单 File/Edit/View/Window 都被 PrintWindow 抓到）。
- 但 Chromium 的 GPU 合成客户区无法被 `PrintWindow` 捕获（before/after 客户区都是空白白图）；改用整屏 BitBlt 截屏时，共享桌面环境下前台抢占导致截到其它窗口。
- 因此运行时像素断言在本环境不可得，按任务约定**降级为归档级验证**：asar 内成员内容、成员集合、rollback 字节还原均已用 `@electron/asar` 独立核实。

## 结论：DEGRADED-SUCCESS

- 运行时：窗口可启动，但客户区截图不可得（如实记录）。
- 工具箱流程：detect(high) → plan(exit2) → dry apply(exit2) → apply --confirm(0，成员替换为暗色) → rollback(0，字节还原，mismatches=[]) 全部通过。

## 证据文件

- `before.png` / `after.png`：PrintWindow 结果（仅窗口框架，客户区空白）
- `after_screen.png`：屏幕 BitBlt 尝试（受前台抢占污染，仅作过程留痕）
- `verify-report.json`：全部命令、退出码、成员内容断言
- 共享截图器：`..\shoot_win.py`（PrintWindow）、`..\shoot_screen.py`（BitBlt）
