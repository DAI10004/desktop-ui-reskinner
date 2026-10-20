# desktop-ui-reskinner Skill 接口规范（冻结 v1）

> 本文件是工程化阶段的硬约束：CLI 命令、换肤包 manifest 字段、安全策略以本文件为准；
> 实现层（Python 模块划分、检测规则细节）可在不破坏接口的前提下增补。
> 最后更新：2026-10-20

## 1. 仓库与 Skill 目录布局

```
项目根（= git 仓库根，= 用户工作目录）
├─ desktop-ui-reskinner/            # Skill 本体（唯一真源），安装时整目录复制到用户级 skills 目录
│  ├─ SKILL.md                      # Agent 入口：框架识别决策树 + 工作流 + 工具链 + 检查清单 + 回滚
│  ├─ scripts/
│  │  ├─ reskin.py                  # 唯一 CLI 入口（Python 3.9+，仅用标准库；可选依赖按需启用）
│  │  ├─ detectors/                 # 各框架检测规则（纯数据/纯函数）
│  │  ├─ ops/                       # 操作原语实现
│  │  └─ asar_pack.js               # Electron 路线的 asar 支持（调用本机 node + @electron/asar，见 §6）
│  ├─ templates/
│  │  ├─ skin.template.json         # 换肤包 manifest 模板
│  │  ├─ qt/                        # qss 换肤包样例骨架
│  │  ├─ electron/                  # asar/CSS 换肤包样例骨架
│  │  └─ win32/                     # 资源段换肤包样例骨架
│  ├─ docs/                         # 框架工作流速查（detect → apply 图文）
│  └─ references/                   # 调研案例库摘要（由 research/ 提炼）
├─ demo-targets/                    # 自建最小靶场（qt-pyside6 / electron / wpf）
├─ examples/skin-packs/             # 可直接使用的示例换肤包（对应靶场）
├─ verification/                    # 端到端验证记录 + before/after 截图
├─ research/                        # 阶段①完整案例库
├─ design/                          # 本规范与技术设计文档
└─ docs/                            # 面向读者的技术文章（GitHub 站内）
```

## 2. CLI 统一约定

入口：`python scripts/reskin.py <command> [options]`（Windows 上 python 已验证 3.13 可用；脚本需兼容 3.9+）。

- 所有命令支持 `--json`：输出单个 JSON 对象到 stdout（日志走 stderr），供 Agent 程序化消费。
- 退出码：`0` 成功；`2` 为安全约定的「需要 --confirm / 存在阻断项，未执行写入」；其余非 0 为错误。
- 路径规则：`--target` 指向应用根目录或主 exe（检测器自行定位根目录）；所有写入路径必须经 containment 校验落在 target 根目录或显式备份目录之内，越界一律拒绝。
- 无状态：脚本不依赖全局状态；每次 apply 都在目标目录生成/更新 `.reskin-backups/`。

命令集（v1 必须全部实现；标记 ◐ 的在依赖缺失时返回结构化 `unsupported` 结果，不算崩溃）：

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `detect` | 只读识别框架、置信度、UI 层入口、完整性/签名状态 | `--target PATH` |
| `backup` | 备份待改文件并写清单（SHA-256 + 原始属性） | `--target --out DIR?` |
| `plan` | 干跑：解析换肤包，列出每个操作、影响文件、风险标签、备份需求 | `--target --skin DIR` |
| `apply` | 默认即 dry-run（等同 plan）；**必须显式 `--confirm` 才写入**；写入前强制先备份 | `--target --skin --confirm? --backup-dir? --force?` |
| `rollback` | 按备份清单原样还原（字节级校验 hash） | `--target --backup-dir DIR?`（缺省取最近一次） |
| `verify` | 换肤后校验：文件 hash 变化点 vs 计划一致性；可选窗口截图 ◐ | `--target --skin? --screenshot? --window-title? --out DIR?` |

## 3. detect 输出契约（JSON）

```json
{
  "ok": true,
  "target_root": "C:\\...\\DemoApp",
  "framework": "qt",
  "confidence": "high",
  "signals": [
    {"name": "qt6core-dll", "found": "PySide6\\Qt6Core.dll", "weight": 0.9},
    {"name": "qwindows-plugin", "found": "PySide6\\plugins\\platforms\\qwindows.dll"}
  ],
  "ui_entry_points": [
    {"kind": "external-qss", "path": "skins\\current.qss", "note": "应用启动时 -stylesheet/load 加载"},
    {"kind": "qt-resource", "path": null, "note": "未发现外部 .rcc/.qrc 编译产物注册"}
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

框架枚举：`qt | electron | cef | wpf | winforms | win32 | unknown`。置信度 `high/medium/low`，`unknown` 或 `low` 时 apply 必须 `--force` 且 Agent 必须先人工确认。

## 4. 换肤包 manifest（skin.json，manifest_version=1）

```json
{
  "manifest_version": 1,
  "name": "demo-dark-blue",
  "framework": "qt",
  "version": "1.0.0",
  "author": "",
  "description": "深蓝暗色主题，替换 qss 与两处图标",
  "target_match": {
    "signals_all": ["qt6core-dll"],
    "files_any": ["DemoApp.exe", "main.py"]
  },
  "ops": [
    {
      "op": "replace_file",
      "src": "assets/style.qss",
      "dst": "skins/style.qss",
      "backup": true
    },
    {
      "op": "patch_text",
      "file": "config.ini",
      "find": "theme=light",
      "replace": "theme=dark",
      "must_match": 1,
      "encoding": "utf-8",
      "backup": true
    },
    {
      "op": "asar_replace",
      "archive": "resources/app.asar",
      "member": "dist/styles/theme.css",
      "src": "assets/theme.css",
      "backup": true
    },
    {
      "op": "pe_resource",
      "image": "DemoApp.exe",
      "restype": "RCDATA",
      "resname": "QSS",
      "lang": 0,
      "src": "assets/style.qss",
      "backup": true
    }
  ]
}
```

操作原语 v1：
- `replace_file`：整文件替换（皮肤自带新样式/图片资源）。
- `patch_text`：唯一精确串替换；`must_match` 次数不符即中止；编码显式声明（默认 utf-8，禁止写 BOM 除非显式 `utf-8-sig`）。
- `asar_replace`：成员级替换进 app.asar（实现见 §6）；要求先检测 asar integrity/fuses 守卫并在 plan 中标红。
- `pe_resource`：经 Resource Hacker CLI 执行；检测不到 ResourceHacker.exe 时返回 `unsupported` 与安装指引，禁止静默跳过。
- 所有 `backup: true`（默认即 true）的目标，apply 前必须存在于备份清单；不存在则拒绝执行。

禁止原语（v1 不提供，SKILL.md 明确声明工具箱不做）：进程注入、DLL 写入、注册表启动项、可执行文件的补丁式字节改写（破解特征）、任何形式的授权校验修改。

## 5. 安全策略（apply 硬规则）

1. 默认 dry-run：不带 `--confirm` 绝不写盘；plan/dry-run 输出「操作清单 + 风险标签 + 备份位置」。
2. 先备份后写入：备份清单（backup-manifest.json）记录路径、大小、SHA-256、mtime、ACL；备份目录默认 `目标根\.reskin-backups\<时间戳>\`。
3. 写入前置检查（任一不过即阻断，退出码 2）：
   - 框架置信度非 high/medium（需 `--force`）；
   - 目标进程正在运行（提示先关闭，或 Agent 自行结束自有靶场进程）；
   - 目标位于 Program Files / 系统目录且无写权限；
   - 检测到 Authenticode 签名 / asar integrity / 强命名（继续则会破坏签名，必须警告并要求 `--confirm` 与显式确认标记）；
   - 目标文件 hash 与上次备份基线不一致（防止覆盖用户/更新后的文件）。
4. 原子性：先写临时文件再 `os.replace`；任一 op 失败，已完成操作自动按本次备份回滚并报告。
5. rollback 仅接受工具箱自己写的备份清单；还原后做 hash 校验。
6. Agent 调用约定：SKILL.md 必须写明——在真实用户软件上，plan 通过后须由 Agent 向用户展示计划并取得明确同意，方可带 `--confirm` 执行；自有靶场演示同样要在验证记录中体现确认步骤。

## 6. Electron asar 实现约定

- 不重新发明 asar 格式：通过 `node scripts/asar_pack.js` 调用本机 Node；首次使用时在项目缓存目录（`%LOCALAPPDATA%\desktop-ui-reskinner` 或项目内 `.tools/`）执行 `npm install @electron/asar`（npm 镜像源参数由 SKILL.md 给出：`--registry=https://registry.npmmirror.com`）。
- 依赖未安装时 detect 仍正常工作；asar_replace 在依赖缺失时返回 `unsupported` 与「一键准备」命令，不自动联网安装（安装动作须 Agent 明确执行并告知用户）。

## 7. 截图验证约定（◐ 可选依赖）

- 首选纯 Python：PySide6（靶场路线本就安装）的 `QWidget.grab()` / `QScreen.grabWindow()`；
- 通用 Win32 路线：pywin32 PrintWindow（可选依赖，缺失则 `unsupported`）；
- 截图统一落 `verification/<target>-<timestamp>/before.png|after.png` + `verify-report.json`。

## 8. SKILL.md 必须包含的章节（验收清单）

1. 这是什么 / 不做什么（合规声明前置）；
2. 框架识别决策树（目录/文件/DLL 信号 → 框架 → UI 层入口）；
3. 标准工作流：detect → 告知用户风险与计划 → backup → plan → apply --confirm → verify →（必要时）rollback；
4. 各框架工具链表与「准备命令」（Qt/PySide6、Node+@electron/asar、Resource Hacker、可选 .NET SDK）；
5. 危险动作确认检查清单（签名/系统目录/进程占用/闭源软件）；
6. 回滚方案与失败恢复；
7. 合规红线与免责声明（个人学习研究、UI 美化、不破解、闭源软件仅限方法论）。
