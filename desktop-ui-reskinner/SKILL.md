# desktop-ui-reskinner —— 桌面软件通用换肤工具箱

> 供 AI 智能体一键调用：输入任意桌面软件目录 → 识别 UI 框架 → 定位 UI 层 → 备份 → 生成/应用换肤包 → 验证/回滚。
> 唯一 CLI：`python scripts/reskin.py <detect|backup|plan|apply|rollback|verify> ...`，全部支持 `--json`。

## 0. 这是什么 / 不做什么（先读）

**是**：对**自有软件、开源软件、官方明确支持主题机制的软件**做 UI 美化（主题色、QSS/CSS、图标、位图资源）的安全工具链；所有写入先备份、原子写、可逐文件 hash 回滚。

**不做**（本工具箱明确不提供、且 Skill 被调用时也不得变通实现）：

- ❌ 破解、授权绕过、付费解锁、去水印、去试用提示；
- ❌ 翻转 Electron Fuses、重算 asarIntegrity、伪造/重签名 Authenticode；
- ❌ DLL 注入、API Hook、进程内存修改、注册表启动项、可执行文件的补丁式字节改写；
- ❌ 对闭源商业客户端（微信/QQ/Discord/Spotify/钉钉等）的改包——detect 命中后只提示风险，不提供写路径；
- ❌ 脱壳、改 `.pak`/`.msstyles`/uxtheme patch。

闭源商业软件仅做**方法论分析**（告诉用户该应用的官方主题入口在哪里），不生成改包产物。

## 1. 框架识别决策树

```
目标目录 --? 有 resources\app.asar 或 ffmpeg.dll/chrome_elf.dll/locales\*.pak ?
           ├─ 是 ──▶ electron   (UI 层 = asar 内 renderer HTML/CSS/JS)
           └─ 否
                --? 根目录有 libcef.dll / cef.pak ?
                   ├─ 是 ──▶ cef   (只识别不主动改包; UI 是宿主加载的 HTML/远程 URL)
                   └─ 否
                        --? 有 Qt6Core.dll/Qt5Core.dll/PySide6/PyQt6/
                        plugins\platforms\qwindows.dll/外部 *.qss ?
                           ├─ 是 ──▶ qt   (UI 层 = 外部 .qss / 外部 .rcc)
                           └─ 否
                                --? 有 PresentationFramework.dll/PresentationCore.dll
                                / *.exe.config/g.resources ?
                                   ├─ 是 ──▶ wpf  (不回编 BAML; 走外挂 ResourceDictionary/
                                   │              官方主题库/设置文件)
                                   └─ 否
                                        --? 有 System.Windows.Forms.dll ?
                                           ├─ 是 ──▶ winforms (换图片/颜色资源)
                                           └─ 否 ──▶ win32 (兜底, low 置信度;
                                                       只走 PE 资源段/配置文件层)
```

**detect 速查表**（信号 → UI 入口 → 可用原语）：

| 框架 | 关键信号 | UI 层入口 | 可用原语 | 备注 |
|---|---|---|---|---|
| qt | Qt6Core.dll、qwindows.dll、PySide6、*.qss | 外部 skins/*.qss | replace_file / patch_text | 内嵌 qrc 不建议改 |
| electron | resources\app.asar、ffmpeg.dll、locales\*.pak | asar 内 dist/**.css、resources\app\ | asar_replace / replace_file | 有 asarIntegrity/fuses 直接拒写 |
| cef | libcef.dll、cef.pak、icudtl.dat | 应用自带 html 目录或远程 URL | 仅 detect | .pak 不可改 |
| wpf | Presentation*.dll、*.exe.config、g.resources | 外挂松散 xaml / 官方主题设置 | 引导为主, 不回编 BAML | 无官方 BAML 回编译器 |
| winforms | System.Windows.Forms.dll、*.resources | 图片/颜色资源 | pe_resource (PE 层图标/位图) | .NET 托管资源需 dnlib, v1 不做 |
| win32 | 其余 PE 兜底 (low) | 资源段 RT_DIALOG/RT_BITMAP/RT_ICON | pe_resource | 需 Resource Hacker; 改后签名失效 |

运行：`python scripts/reskin.py --json detect --target <应用目录或主exe>`。
`confidence=low/unknown` 时 apply 必须加 `--force`，且 Agent 必须先向用户人工确认。

## 2. 标准工作流（硬性）

```bash
# 1) 只读识别
python scripts/reskin.py --json detect --target "C:\Path\To\App"

# 2) 干跑计划（退出码 2, 不写任何文件）
python scripts/reskin.py --json plan --target ... --skin <皮肤包目录>

# 3) ★ Agent 必须把 plan 结果展示给用户, 取得明确口头/书面同意后才允许 --confirm
#    自有靶场演示同样要在 verification/ 里记录确认步骤。

# 4) 已获同意后才写入（写前自动备份到 .reskin-backups\<时间戳>\）
python scripts/reskin.py --json apply --target ... --skin ... --confirm

# 5) 校验
python scripts/reskin.py --json verify --target ... [--screenshot]

# 6) 不满意随时回滚（只认本工具箱写的 backup-manifest.json, 逐文件 SHA-256 校验）
python scripts/reskin.py --json rollback --target ...
```

- 退出码：`0` 成功；`2` = 需要 --confirm / 有阻断项，未写入；其它非 0 = 错误。
- 无状态：不依赖全局状态；备份固定在目标目录的 `.reskin-backups/`。
- 原子写：先写临时文件再 `os.replace`；任一 op 失败自动按本次备份回滚并报告。

## 3. 工具链与一键准备命令

| 组件 | 用途 | 准备命令（Windows PowerShell） |
|---|---|---|
| Python 3.9+ | reskin.py 本体 | 已装; 无需 pip 依赖（截图/asar 走可选路径） |
| Node.js 22+ | asar_pack.js | `winget install OpenJS.NodeJS.LTS` |
| @electron/asar | electron 路线 | `cd .tools\asar; npm install @electron/asar --registry=https://registry.npmmirror.com` |
| Resource Hacker | win32 PE 资源 | 官网 https://www.angusj.com/resourcehacker/ 或 `winget install AngusJ.ResourceHacker` |
| PySide6（可选） | 截图验证 | `pip install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| .NET SDK 8（可选） | WPF 反编译/ilspycmd | `winget install Microsoft.DotNet.SDK.8` |

环境变量：
- `RESKINNER_ASAR_DIR`：指向含 `@electron/asar` 的 node_modules 根（默认自动找项目根 `.tools\asar\node_modules`）。
- `RESKINNER_RH_EXE`：ResourceHacker.exe 完整路径。

## 4. 危险动作确认检查清单（apply 前逐条过）

1. 目标是不是**用户自有 / 开源 / 官方支持换肤**的软件？闭源商业客户端 → 停止，只给方法论。
2. 该应用**已关闭**吗？detect 的 `guards.process_running=true` 会阻断写盘。
3. 目标在 **Program Files / 系统目录**吗？写权限是否足够？
4. `authenticode_signed=true` / `strong_named=true` → 修改后签名立即失效，SmartScreen/EDR 可能报警，用户是否知情？
5. `asar_integrity=true`（含 fuses 魔数）→ **直接拒写**，不提供绕过，引导到官方主题系统。
6. 目标文件与上次备份基线 hash 不一致 → 阻断，防止覆盖用户/自动更新后的文件。
7. 是否已经把 plan 的「操作清单 + 风险标签 + 备份位置」给用户看过并拿到同意？

## 5. 回滚方案与失败恢复

- **正常回滚**：`rollback` 只读 `.reskin-backups/<时间戳>/backup-manifest.json`（非本工具箱产物直接拒绝），逐文件还原后做 SHA-256 比对，输出 mismatches。
- **apply 中途失败**：已完成的 op 自动按本次备份回滚，返回 `mode=rolled-back` + `error`。
- **依赖缺失**（node/@electron/asar/ResourceHacker 任一缺失）：返回结构化 `unsupported`（code + message + install_hint），**绝不静默跳过**，绝不自动联网安装（安装动作由 Agent 显式执行并告知用户）。
- **截图失败**：verify 返回 `screenshot_status=unsupported`，不阻塞其它校验。
- **autoUpdater 覆盖**：Electron 应用自动更新后本地皮肤会被冲掉，属预期；重新 apply 同一份皮肤即可（幂等）。

## 6. 合规红线与免责声明

- 本工具箱仅限**个人学习研究、互操作、自有/开源软件 UI 美化**；不得用于破解、授权绕过、分发修改版他人软件。
- 不提供翻 fuse / 重算 integrity / 伪造签名 / 注入 / Hook 能力；detect 到这些保护时的职责是**告知此路不通并降级到官方主题系统**。
- 闭源商业软件（Discord/Spotify/微信/QQ/钉钉/Teams 等）的第三方改包项目普遍违反厂商 ToS，可能导致封号与法律责任——本工具箱不收录、不生成、不引导使用此类产物。
- 用户对自己执行的写操作后果（签名失效、杀软报警、更新被冲掉）自行负责。
