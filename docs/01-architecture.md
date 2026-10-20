# 01 · 技术架构深潜

desktop-ui-reskinner 是一个无状态、单一入口的 CLI 工具箱。本文说明 Agent 与工具箱之间的全部契约，内容对应 [`../design/skill-interface-spec.md`](../design/skill-interface-spec.md)（冻结规范）与 [`../desktop-ui-reskinner/SKILL.md`](../desktop-ui-reskinner/SKILL.md)（调用手册）。

## 1. 分层结构

```
┌─────────────────────────────────────────────────────────────┐
│ Agent 层：读 SKILL.md 决策树 → 展示 plan → 取得用户同意 → 调用 │
└──────────────────────────────┬──────────────────────────────┘
                               │ 子进程 + JSON（stdout）/ 日志（stderr）
┌──────────────────────────────▼──────────────────────────────┐
│ CLI 层  scripts/reskin.py                                    │
│  detect / backup / plan / apply / rollback / verify          │
├───────────────┬───────────────┬───────────────┬──────────────┤
│ 检测层         │ 计划/守卫层    │ 操作原语层      │ 备份/回滚层   │
│ 信号+权重      │ dry-run/阻断   │ 4 种 op        │ SHA-256 清单 │
│ 置信度模型     │ 风险标签       │ containment    │ 原子写/事务  │
└───────────────┴───────┬───────┴───────────────┴──────────────┘
                        │ 仅 Electron 路线
              ┌─────────▼──────────┐
              │ scripts/asar_pack.js│  本机 Node + @electron/asar
              └────────────────────┘
```

- **无状态**：不写全局配置；每次操作的状态只有目标目录下的 `.reskin-backups/`。
- **零强制依赖**：reskin.py 仅用 Python 3.9+ 标准库。Node/@electron/asar、PySide6、pywin32、Resource Hacker 均为可选，缺失时返回结构化 `unsupported` 而非崩溃。

## 2. 通用调用契约

```powershell
python scripts/reskin.py [--json] <command> --target <应用根目录或主 exe> [options]
```

| 子命令 | 作用 | 关键参数 |
|---|---|---|
| `detect` | 只读识别框架、置信度、UI 入口、守卫 | `--target` |
| `backup` | 备份目标文件并写清单 | `--skin` 或 `--files` |
| `plan` | 干跑：操作清单 + 风险标签 + 备份需求 | `--skin` |
| `apply` | 默认 dry-run；`--confirm` 才写入 | `--skin` `--confirm` `--force` `--backup-dir` |
| `rollback` | 按清单还原并逐文件 hash 校验 | `--backup-dir`（缺省取最近一次） |
| `verify` | 变更点比对，可选窗口截图 | `--skin` `--screenshot` `--window-title` `--out` |

- `--json`：stdout 只输出**一个** JSON 对象（人类可读日志走 stderr）。
- 退出码：`0` 成功；`2` 干跑/需确认/存在阻断项（**未写入**）；其余非 0 为错误。
- 所有换肤包内相对路径一律相对 `--target` 根解析，与执行命令时的 CWD 无关（这是验证阶段实测发现并修复的缺陷，见[案例复盘](02-case-studies.md)）。

## 3. detect：信号与置信度模型

检测器对目标目录做只读扫描，每个命中的信号带权重，按框架加权排序后给出 `high / medium / low`，无任何信号为 `unknown`。

代表性信号：

| 框架 | 信号（节选） |
|---|---|
| qt | `Qt6Core.dll` / `Qt5Core.dll`、`plugins\platforms\qwindows.dll`、PySide6/PySide2/PyQt5/PyQt6 目录、`*.py` 源码中 `from/import PySide6|PySide2|PyQt5|PyQt6`（权重 0.6）、`requirements.txt` 命中、外部 `*.qss`/`*.rcc` |
| electron | `resources\app.asar`（0.95）、`app.asar.unpacked`、`resources\app`、`ffmpeg.dll`、`chrome_*.pak`、`locales\*.pak`、`v8_context_snapshot.bin` |
| cef | `libcef.dll`、`cef.pak`、`icudtl.dat` |
| wpf | 旁置 `PresentationFramework.dll`/`PresentationCore.dll`、`*.exe.config`；exe/dll 原始字节中 ASCII 命中 `PresentationFramework`（0.8，覆盖 GAC/单文件形态）、`PresentationCore`（0.4） |
| winforms | 字节命中 `System.Windows.Forms`（0.7） |
| win32 | 其余 PE（exe/dll）兜底，low |

输出示例（Qt 源码形态靶场的真实结果）：

```json
{
  "ok": true,
  "target_root": "E:\\...\\demo-targets\\qt-pyside6",
  "framework": "qt",
  "confidence": "medium",
  "signals": [
    {"name": "py-qt-import", "found": "main.py", "weight": 0.6},
    {"name": "external-qss", "found": "skins\\style.qss", "weight": 0.3}
  ],
  "ui_entry_points": [
    {"kind": "external-qss", "path": "skins\\style.qss", "note": "应用启动时加载的外部 QSS"}
  ],
  "guards": {
    "authenticode_signed": false,
    "asar_integrity": null,
    "strong_named": null,
    "writable": true,
    "in_program_files": false,
    "process_running": false
  },
  "warnings": []
}
```

`confidence=low/unknown` 时 apply 必须显式 `--force`，且 Agent 必须先取得用户人工确认。

## 4. 守卫（guards）

写盘前逐项检查，任一硬守卫不过即返回 `mode=blocked`（退出码 2）：

- **进程占用**：目标 exe 正在运行（tasklist 判定）→ 要求先关闭；
- **系统目录**：位于 Program Files / 系统目录且不可写；
- **Authenticode 签名**：经 PowerShell `Get-AuthenticodeSignature` 子进程判定，修改会使签名失效 → 警告并要求显式确认；
- **Electron asar integrity / Fuses**：检测 electron-builder 注入的 integrity 配置与 fuse 魔数 → **直接拒写**，工具箱不提供翻转/重算；
- **.NET 强名称**：启发式检测 → 警告；
- **基线 hash**：目标文件与上次备份清单中的 SHA-256 不一致 → 阻断，防止覆盖用户手动改动或自动更新后的文件。

## 5. 换肤包 manifest（manifest_version = 1）

```json
{
  "manifest_version": 1,
  "name": "demo-dark-blue",
  "framework": "qt",
  "version": "1.0.0",
  "description": "深蓝暗色主题",
  "target_match": {
    "signals_all": ["py-qt-import"],
    "files_any": ["main.py"]
  },
  "ops": [
    {"op": "replace_file", "src": "assets/style.qss", "dst": "skins/style.qss", "backup": true},
    {"op": "patch_text", "file": "config.ini",
     "find": "theme=light", "replace": "theme=dark",
     "must_match": 1, "encoding": "utf-8", "backup": true}
  ]
}
```

字段说明：

- `target_match`：apply 前与 detect 结果交叉校验框架与目标身份；`signals_all` 中信号必须全部命中。
- `ops[].backup`：默认 `true`；为 true 的目标必须先进入备份清单，否则拒绝执行。

### 四种操作原语

| op | 语义 | 失败/降级行为 |
|---|---|---|
| `replace_file` | 用包内 `src` 整文件替换目标 `dst` | containment 失败即阻断 |
| `patch_text` | 文件内唯一精确串替换；`must_match` 为期望命中次数（通常 1），实际不符即中止 | 已完成 op 自动回滚 |
| `asar_replace` | 对 `resources/app.asar` 做**成员级**替换（解包→换单成员→重打包→原子替换），其余成员不变 | Node 或 @electron/asar 缺失 → `unsupported` + 安装命令 |
| `pe_resource` | 经 Resource Hacker CLI 替换 PE 资源段（图标/位图/自定义 RCDATA） | 找不到 ResourceHacker.exe → `unsupported` + winget/官网指引，**绝不静默成功** |

`encoding` 默认 `utf-8`；仅当显式写 `utf-8-sig` 时才写 BOM。

## 6. 备份清单与回滚

备份目录：`<target>\.reskin-backups\<时间戳>-<换肤包名>\`，其中 `backup-manifest.json` 记录每个文件的相对路径、大小、mtime、SHA-256，并保存原始字节副本。

回滚规则：

1. 只接受工具箱自己写出的清单（结构/字段校验不过直接拒绝）；
2. 逐文件还原后重算 SHA-256，与清单比对，输出 `mismatches`（空数组才算成功）；
3. 还原同样使用临时文件 + `os.replace` 原子替换。

## 7. 事务与原子性

apply 把一次 manifest 的全部 ops 当作一个事务：

- 写前统一做守卫与 containment 校验，统一备份；
- 每个写入先落临时文件再 `os.replace`；
- 任一 op 失败（如 `patch_text` 次数不符），对本次已完成的操作立即按本次备份回滚，返回 `mode=rolled-back` 与错误详情。

## 8. Electron 路线的实现细节

- asar 支持在独立 Node 脚本 `scripts/asar_pack.js`（ESM）中实现，动作：`list` / `extract-member` / `replace`，以 JSON 行协议与 reskin.py 通信。
- `@electron/asar` 查找顺序：环境变量 `RESKINNER_ASAR_DIR` → 项目根 `.tools\asar\node_modules` → 全局 node_modules。
- 工具箱**不**自动联网安装依赖；缺失时返回 `unsupported` 与准备命令，由 Agent 显式执行并告知用户。
- 已记录行为（非缺陷）：@electron/asar v4 在 Windows 下成员键以反斜杠存储，全新 pack 亦如此，Electron 运行时正常加载。

## 9. 截图验证

- 首选 PySide6 的 `QScreen.grabWindow()` / `QWidget.grab()`（靶场 Qt 离屏验证使用）；
- 通用 Win32 路径用 ctypes 调 `PrintWindow(PW_RENDERFULLCONTENT=2)`（零第三方依赖，WPF 靶场验证使用）；
- 两者均不可用时 `screenshot_status=unsupported`，不阻塞归档级校验。
- 已知边界：Chromium（Electron）GPU 合成的客户区无法被 PrintWindow 捕获，只能截到原生窗口框架；此类目标降级为归档级验证（成员内容 + 成员集合 + rollback hash）。
