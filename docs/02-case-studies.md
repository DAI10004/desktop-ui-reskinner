# 02 · 靶场实战复盘

三个靶场都是**自建的最小演示程序**（不使用任何闭源商业软件），源码与构建脚本在 [`../demo-targets/`](../demo-targets/)，换肤包在 [`../examples/skin-packs/`](../examples/skin-packs/)，原始证据在 [`../verification/`](../verification/)。

| 靶场 | 框架 | 验证方式 | 结论 |
|---|---|---|---|
| qt-pyside6 | PySide6 6.12（Python 3.13 venv） | offscreen 渲染 + 逐像素统计 | ✅ SUCCESS |
| wpf-codeonly | .NET Framework 4.x，csc.exe 编译 | PrintWindow 截图 + 逐像素统计 | ✅ SUCCESS |
| electron-demo | Electron 44 + app.asar | 窗口启动 + asar 成员断言 | 🟡 DEGRADED-SUCCESS（归档级） |

> 工程方法说明：验证过程中真实暴露了 reskin.py 的两个缺陷（相对路径按 CWD 解析、源码形态 Qt / code-only WPF 检测置信度不足）。两者均已在工具箱侧修复并新增回归用例，最终自测 **31/31 通过**（[`../desktop-ui-reskinner/tests/TEST-REPORT.md`](../desktop-ui-reskinner/tests/TEST-REPORT.md)）；修复后对三个真实靶场重跑 detect：qt=medium、wpf=medium、electron=high。下文同时保留验证当时的原始记录与修复结论。

---

## 一、Qt / PySide6：完整端到端

**靶场**：[`../demo-targets/qt-pyside6/`](../demo-targets/qt-pyside6/)，一个 QMainWindow（菜单栏、工具栏、QListWidget、QTextEdit、按钮、状态栏），启动时读取同目录 `skins/style.qss` 套样式、读取 `config.ini` 的 `[ui] theme=` 显示在状态栏。

**换肤包**：[`../examples/skin-packs/qt-dark-blue/`](../examples/skin-packs/qt-dark-blue/)，两个操作：
1. `replace_file`：浅色系 `skins/style.qss` → 深蓝暗色 QSS；
2. `patch_text`：`config.ini` 中 `theme=light` → `theme=dark`（`must_match=1`）。

**命令序列**（退出码均为实测）：

| 步骤 | 退出码 | 结果 |
|---|---|---|
| `plan`（无 --confirm） | 2 | 干跑列出 2 个 op 与风险，无写入 |
| `apply`（无 --confirm） | 2 | 无写入 |
| `apply --confirm` | 0 | 两 op 落盘，写入前自动备份 |
| `verify` | 0 | 变更点与计划一致 |
| `rollback` | 0 | `mismatches=[]` |

**像素断言**（`QWidget.grab()` 全图均值；离屏平台不发现系统字体，截图脚本与靶场 `bootstrap_fonts()` 显式注册 Segoe UI，[原始报告](../verification/qt-pyside6/verify-report.json)）：

| 状态 | R | G | B | 亮度 |
|---|---|---|---|---|
| before | 246.10 | 246.56 | 246.18 | 246.38（近白浅灰） |
| after | 22.08 | 36.04 | 62.32 | 34.86（深蓝，蓝通道占优） |
| restored | 246.10 | 246.56 | 246.18 | 246.38 |

- `after 亮度 < 0.7 × before`：成立；`after 蓝色占优`：成立；
- `before` 与 `restored` 差异像素数：**0**。

这一案例对应业界 OBS Studio 的官方主题机制（安装目录/用户配置目录加载 `themes/*.qss`，见 [`../research/cases-qt-win32.md`](../research/cases-qt-win32.md)）——当应用本身支持外部样式表时，静态替换是零侵入、可回滚的最佳路径。

---

## 二、WPF code-only：外挂松散 ResourceDictionary 的合法边界

**为什么需要这个靶场**：真实 WPF 应用的 XAML 在编译期变为 **BAML**，嵌入程序集的 `<g>.resources`。**WPF 没有官方 BAML 回编工具**：用 dnSpyEx / ILSpy 可以反编译查看，但改 IL/资源再回编会破坏程序集签名、强名称，且不同编译器版本极易损坏文件。因此工具箱对 BAML 内嵌资源坚持**只读 / unsupported**，可写路径是 WPF 原生支持的**外挂松散 ResourceDictionary**。

**靶场**：[`../demo-targets/wpf-codeonly/`](../demo-targets/wpf-codeonly/)，`Program.cs` 为纯代码 WPF（不经过 XAML 编译器），控件以 `DynamicResource` 取 `AppBg/AppFg/Accent` 三个画刷键；启动时若同目录存在 `theme.xaml`，就 `XamlReader.Load` 为 ResourceDictionary 合并进应用资源，否则使用内置浅色兜底。构建脚本用系统自带编译器 `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`（无需安装 .NET SDK），引用 GAC 中的 PresentationFramework / PresentationCore / WindowsBase / System.Xaml，实测编译出 `WpfDemo.exe`（6 KB）。

**换肤包**：[`../examples/skin-packs/wpf-dark/`](../examples/skin-packs/wpf-dark/)，一个 `replace_file`：暗色 `theme.xaml`（#0E1626）→ 目标 `theme.xaml`。

**像素断言**（`PrintWindow(PW_RENDERFULLCONTENT=2)`，[原始报告](../verification/wpf-codeonly/verify-report.json)）：

| 状态 | R | G | B | 亮度 |
|---|---|---|---|---|
| before | 237.98 | 238.06 | 233.92 | 237.57 |
| after | 44.96 | 51.86 | 65.54 | 51.36 |
| restored | 237.98 | 238.06 | 233.92 | 237.57 |

before 与 restored **0 像素差异**；rollback `mismatches=[]`。

**对真实 WPF 应用的方法论**（详见 [`../research/cases-wpf-winforms.md`](../research/cases-wpf-winforms.md)）：优先引导应用自身的主题机制——MaterialDesignInXamlToolkit（`PaletteHelper`）、WPF-UI / HandyControl / ModernWpf（`ThemeManager`）等开源主题库均有运行时切主题 API；其次是外部松散 XAML / 设置文件。反编译回编仅用于学习理解，不作为换肤交付路径。

---

## 三、Electron：asar 成员级替换（归档级验证）

**靶场**：[`../demo-targets/electron-demo/`](../demo-targets/electron-demo/)，`app-src/` 是最小 Electron 应用（main.js + index.html + `dist/styles/theme.css` 浅色）。`build.ps1` 用 npmmirror 安装 electron 与 @electron/asar（经 `ELECTRON_MIRROR` 加速），复制 electron dist 为 `App/`，把 `app-src` 打包成 `App/resources/app.asar`，由 `App/electron.exe` 直接启动。

**换肤包**：[`../examples/skin-packs/electron-dark/`](../examples/skin-packs/electron-dark/)，一个 `asar_replace`：将 asar 内成员 `dist/styles/theme.css` 替换为暗色版本（#0e1626 / #d7e6ff）。

**实测流程**（[原始报告](../verification/electron-demo/verify-report.json)）：

| 步骤 | 退出码 | 结果 |
|---|---|---|
| build | 0 | electron 44.9.1 + app.asar（4 个成员） |
| detect | 0 | framework=electron，**confidence=high** |
| plan / apply 干跑 | 2 | 风险标签含「asar 重打包；若启用 asarIntegrity 会被运行时拒绝」，无写入 |
| apply --confirm | 0 | 成员替换为暗色 CSS（570 字节，内容首行 `#0e1626`），其余成员不变 |
| rollback | 0 | app.asar 字节级还原（内容回到浅色 581 字节，mtime 回到构建时刻，`mismatches=[]`） |

**为什么是「降级」而不是像素级 SUCCESS**：

1. electron.exe **能正常启动**——PrintWindow 抓到了原生标题栏与 File/Edit/View/Window 菜单（见 [`../verification/electron-demo/before.png`](../verification/electron-demo/before.png)）；
2. 但 Chromium 的 **GPU 合成客户区不响应 PrintWindow**，before/after 客户区均为空白；整屏 BitBlt 在共享桌面环境又受前台窗口抢占污染，像素断言不可得；
3. 因此按既定验收约定降级为**归档级验证**：用 @electron/asar 独立提取成员核对内容、核对成员集合不变、核对 rollback 后字节还原。

**守卫行为（合规要点）**：对启用了 electron-builder **asarIntegrity** 或 **Electron Fuses** 的应用，detect 会标出守卫，apply 直接拒写——修改后应用会因完整性校验拒绝启动，而工具箱**不提供**翻转 fuse / 重算 hash 的能力。VS Code、Joplin、GitHub Desktop 等开源 Electron 应用都提供官方主题/CSS 扩展机制，应优先走官方路径（见 [`../research/cases-electron-cef.md`](../research/cases-electron-cef.md)）；对 Discord 等闭源客户端的改包违反服务条款，本工具箱不收录、不引导。

**已记录的工具行为（非缺陷）**：@electron/asar 4.3.1 在 Windows 下成员键以反斜杠存储，全新 `asar pack` 同样如此，Electron 运行时加载正常。

---

## 四、验证阶段发现并修复的缺陷（透明记录）

1. **相对路径 containment 按 CWD 解析（阻断级，已修）**：早期版本中，manifest 里的相对 `dst`/`file` 按执行命令的 CWD 拼接，CWD 不在 target 根时误报「操作目标越出 target 根」，`--force` 也不放行（验证报告中的 workaround 是 `cd` 到 target 根）。修复后所有相对路径一律相对 `--target` 根，并新增「从非 target CWD 执行 apply」回归用例。
2. **检测置信度缺口（已修）**：源码形态 Qt（无 Qt6Core.dll）与 code-only WPF（程序集引用在 GAC）最初都落入 win32/low 兜底。修复后新增 Python 源码 Qt 导入扫描（0.6）与 .NET 程序集字节特征扫描（`PresentationFramework` 0.8）；修复后实测 qt=medium、wpf=medium。

修复后全量回归：**31/31 用例通过**，含框架识别、Qt 端到端、Electron asar 端到端、越界拒绝、must_match 不符中止+自动回滚、基线 hash 阻断等。
