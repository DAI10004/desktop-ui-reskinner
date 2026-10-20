# Qt 桌面框架与 Win32 原生 PE 程序换肤路线调研

> 路线总览：**Qt 路线**换肤以 QSS 样式表 + 资源系统（.qrc/.rcc/qrc:/）+ QPalette 为核心，检测信号是 `Qt5Core.dll/Qt6Core.dll`、`plugins\platforms\qwindows.dll` 等模块；**Win32 原生路线**换肤分两层——「PE 资源段层」（RT_DIALOG/RT_MENU/RT_STRING/位图图标，用 Resource Hacker/ResEdit 改 exe）与「配置文件层」（如 Notepad++ 的 Scintilla XML 主题），DWM/UxTheme 只决定标题栏与系统主题，改不了自绘客户区。两条路线都**不涉及破解/授权绕过**，只做 UI 美化与互操作。

---

## 一、Qt 路线：QSS / 资源系统 / QPalette

### ① 框架/类型识别特征（可机器判定）

| 信号类别 | 具体判定项 |
| --- | --- |
| 进程模块（dll 名单） | 进程已加载 `Qt5Core.dll` / `Qt6Core.dll`、`Qt5Gui.dll` / `Qt6Gui.dll`、`Qt5Widgets.dll` / `Qt6Widgets.dll`、`Qt5Quick.dll`（QML 程序） |
| 目录结构 | 安装目录下存在 `plugins\platforms\qwindows.dll`（QPA 平台插件，Windows 必需）；常见同级目录 `plugins\styles\`、`plugins\imageformats\`、`plugins\iconengines\` |
| 部署产物特征 | `windeployqt` 部署出来的目录树：根目录一堆 `Qt6*.dll` + `platforms\qwindows.dll` + `translations\` + `resources\` |
| 资源系统信号 | exe/dll 内可能内嵌 `qrc:/` 前缀资源（QSS、图标）；外部可注册 `.rcc` 编译产物；磁盘上可能散落 `.qss`、`.qrc` 文件 |
| Python 绑定程序 | 目录里没有 Qt dll，但进程加载 `python.exe` + `PyQt5/PySide2/PyQt6/PySide6` 模块，或目录内含 `PyQt5\Qt5\bin\Qt5Core.dll` 这类 bundled Python 包 |
| 导入表 | PE 导入表出现 `Qt6Core.dll!QApplication` 系列符号（或 dumpbin 看到 `Qt6Core` 导入） |

### ② UI 层入口与资源形态

- **QSS（Qt Style Sheets）**：CSS2 子集，`qApp->setStyleSheet(QString::fromUtf8(qssText))` 全局注入；选择器/伪状态/子控件语法见官方参考文档（已验证）。
- **资源系统**：`.qrc` 是 XML 清单，`rcc` 编译为 C++ 或外部 `.rcc` 二进制；运行时用 `:/prefix/file.png` 或 `qrc:/prefix/file.png` 访问；外部 `.rcc` 用 `QResource::registerResource()` 注册。
- **QPalette**：按 ColorRole（Window/WindowText/Highlight/Base/Text…）着色，对未写死 QSS 的原生 widget 生效；暗色模式常靠切 palette 而非 QSS。
- **样式插件**：`QStyle` 插件（如 windowsvista/Windows11 风格、Kvantum），`-style` 命令行或 `QApplication::setStyle()` 切换。

### ③ 工具链（Windows 优先，注明 license）

| 工具 | 用途 | 安装方式 | 开源/license |
| --- | --- | --- | --- |
| Qt 官方 SDK（含 rcc、windeployqt） | 资源编译 + 部署 + 检测 | 官网在线安装器或 `winget install Qt.Qt.6`（按需） | 开源 LGPLv3 / 商业双授权 |
| Python 生态 | 直接 pip 装主题库 | `pip install qdarkstyle qt-material pyqtdarktheme` | 见各库 LICENSE |
| 官方文档（只读参考） | QSS 语法/资源系统/部署 | 浏览器访问 doc.qt.io | — |

> 纯调研约束：本次**不实际安装**任何软件，仅记录命令形式。

### ④ 代表开源项目（URL 均已验证可达）

| 项目 | URL | 一句话说明 | License |
| --- | --- | --- | --- |
| QDarkStyleSheet | https://github.com/ColinDuquesnoy/QDarkStyleSheet | 最完整的 Qt 暗色/亮色 QSS 库，支持 PyQt5/PySide2/C++，文档在 readthedocs | 开源（仓库 LICENSE，MIT 系） |
| Qt-Material | https://github.com/UN-GCPDS/qt-material | Material Design 风格 QSS，运行时换色（`apply_stylesheet(app, theme='dark_teal.xml')`），支持 PySide2/6、PyQt5/6 | 开源（见仓库 LICENSE） |
| Kvantum | https://github.com/tsujan/Kvantum | 基于 SVG 的 Qt 主题引擎（KDE/LXQt 生态，Linux 为主，Windows 支持有限） | GPL-3.0-or-later（Fedora/openSUSE 包元数据确认） |
| PyQtDarkTheme | https://github.com/5yutan5/PyQtDarkTheme | 扁平暗色/亮色主题，自动适配系统暗色模式 | 开源（见仓库 LICENSE） |
| PyQt-Fluent-Widgets | https://github.com/zhiyiYo/PyQt-Fluent-Widgets | Fluent Design 组件库（含暗色主题能力），**注意：GPLv3 仅限非商业，商用需购买商业授权** | GPLv3（非商业）/ 商业双授权 |
| PyDracula 模板 | https://github.com/Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6 | PySide6/PyQt6 现代深色 GUI 模板（社区评测标注已停止维护，仅作参考样本） | 开源（见仓库 LICENSE） |

文档镜像（已验证）：QDarkStyleSheet https://qdarkstylesheet.readthedocs.io/en/stable/readme.html ；Qt-Material https://qt-material.readthedocs.io/en/latest/ 。

### ⑤ 典型坑与对策

| 现象 | 原因 | 对策 |
| --- | --- | --- |
| QSS 写了但某些控件不变色 | 该控件在代码里硬编码了 `setStyleSheet` 或 palette，子级覆盖全局 | 用更具体选择器（类名+objectName），或改 palette |
| 换肤后图标发白/错位 | 图标来自 `qrc:/` 内嵌资源，主题只换了色没换图 | 主题包需自带 images 目录并改 QSS 里的 `image: url(...)` |
| 外部 `.rcc` 改了不生效 | 资源在编译期嵌进 exe，运行时只读；改磁盘 .rcc 不等于改 exe 内副本 | 区分「内嵌资源」与「外部注册资源」；后者才是可换肤入口 |
| Qt6 程序打包后缺平台插件起不来 | 缺 `platforms\qwindows.dll` | 这是识别信号也是部署诊断点，不是换肤问题，但 detect 阶段要区分「无法识别」和「缺插件」 |
| Python 打包程序（PyInstaller）找不到主题 | 主题资源未打进 bundle | 换肤应走用户配置目录（如 `%APPDATA%\AppName\themes\`），不要改 bundle 内文件 |
| Kvantum 在 Windows 上无效 | Kvantum 是 Linux/X11 主题引擎，Windows QPA 不支持 | Windows 目标放弃 Kvantum，走 QSS/palette 路线 |

### ⑥ 合规备注

- 仅对**自有软件或官方开放主题机制的软件**（如 OBS）做 QSS 替换；不得反编译商业软件内嵌 QSS 后重打包分发。
- PyQt-Fluent-Widgets 商用需商业授权，引用其设计稿作学习参考可以，直接捆绑进闭源商业产品需付费。
- 不破解、不绕过授权；不修改 exe 内资源去改别人付费软件的界面。

---

## 二、实战案例：OBS Studio（Qt 原生换肤标杆）

> OBS Studio 是 Qt 写的、**官方原生支持主题热切换**的标杆——换肤零破解，纯放文件到用户目录即可。

### ① 识别特征

- 进程模块：加载 `Qt6Core.dll` / `Qt6Widgets.dll`（OBS 28+ 已迁 Qt6），主程序 `obs64.exe`。
- 安装目录：`<安装目录>\data\obs-studio\themes\` 下每个主题一个文件夹（含 `Yami.qss`、`Acri.qss` 等 + images 子目录）。
- 用户目录：`%APPDATA%\obs-studio\themes\`（自定义主题存放处，可能需手动创建）。

### ② UI 层入口与资源形态

- 入口：OBS 设置 → General（或 OBS 30.2+ 的 Appearance）→ Theme 下拉框。
- 格式：QSS（CSS2 子集）+ 同名 images 目录；OBS 30.2+ 引入**可组合主题系统**（OBT/OVT），支持 `@OBSThemeMeta` 元数据块、变量、`extends` 继承（如 `extends: 'com.obsproject.Yami'`）。
- 官方内置主题：Yami（28+ 默认，Warchamp7 设计）、Grey、Light、Acri、Rachni、Dark（legacy）、System。

### ③ 工具链

- 不需要任何编译工具：主题就是文本文件，用记事本/VSCode 改 `.qss` 即可。
- 官方文档（已验证）：
  - 主题指南 https://obsproject.com/kb/themes-guide
  - GitHub Wiki「Custom Themes」https://obsproject.com/wiki/Custom-Themes
  - 源码主题目录 `UI/data/themes/`（仓库 obsproject/obs-studio）。

### ④ 代表开源/社区资源

| 资源 | URL | 说明 |
| --- | --- | --- |
| 官方主题指南 | https://obsproject.com/kb/themes-guide | 内置主题列表 + 自定义主题安装路径 |
| 官方 Wiki | https://obsproject.com/wiki/Custom-Themes | 自定义主题开发方法 + 30.2 可组合主题说明 |
| Catppuccin OBS 主题 | https://github.com/catppuccin/obs（社区主题，经第三方指南引用） | 第三方配色主题示例 |

### ⑤ 典型坑与对策

| 现象 | 原因 | 对策 |
| --- | --- | --- |
| 放了主题文件但下拉框看不到 | 用户目录 `themes` 不存在或没重启 OBS | 手动创建 `%APPDATA%\obs-studio\themes\`，主题按文件夹组织，重启 OBS |
| 改 QSS 后图标错乱 | OBS 30.2+ 主题预处理改了资源路径命名 | 基于 `Yami.qss` 复制改造，不要从零写；用官方可组合主题的 `extends` 继承 |
| 升级 OBS 后自定义主题失效 | OBT/OVT 变量随版本演进 | 用 `@OBSThemeMeta` + `extends` 只覆盖变量，跟随基主题更新 |
| System 主题在 Windows 永远浅色 | 官方明确：Windows 上 System 主题恒为浅色（macOS/Linux 才有暗色） | Windows 目标直接选 Yami/Acri 等内置暗色 |

### ⑥ 合规备注

OBS Studio 是 GPLv2 开源软件，官方鼓励社区主题；自定义主题放用户目录、不重分发 OBS 本体，完全合规。

---

## 三、Win32 原生 PE 路线：资源段 + UxTheme/DWM 边界

### ① 识别特征（可机器判定）

- 进程模块：只有 `user32.dll`、`comctl32.dll`、`uxtheme.dll`、`dwmapi.dll` 等系统库，**没有 Qt/Qt6 前缀 dll**。
- PE 导入表：导入 `CreateWindowExW`、`DialogBoxParamW`、`LoadMenuW`、`LoadStringW`、`InitCommonControlsEx` 等 Win32 API。
- PE 资源段：用 Resource Hacker 打开 exe 能看到 `RT_RCDATA`、`RT_DIALOG`、`RT_MENU`、`RT_STRING`、`RT_BITMAP`、`RT_ICON`、`RT_MANIFEST`（uAC 兼容声明）等分类节点。
- 清单文件：exe 内嵌 RT_MANIFEST 里可能声明 `Microsoft.Windows.Common-Controls v6.0`（启用视觉样式/UxTheme）。

### ② UI 层入口与资源形态

- **PE 资源段**：对话框布局（RT_DIALOG）、菜单（RT_MENU）、字符串表（RT_STRING）、位图/图标（RT_BITMAP/RT_ICON/RT_GROUP_ICON）。改这些等于改 exe 本体。
- **UxTheme/msstyles**：Windows 桌面主题（`.msstyles`）管的是**系统级控件外观**（按钮、滚动条、标题栏），对程序自绘客户区无效；第三方 msstyles 主题常伴随 uxtheme patch，风险高。
- **DWM 暗色 API**：`DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &TRUE, sizeof(BOOL))` 只把**标题栏**刷成暗色；客户区颜色程序自己画，DWM 管不着。
- **边界结论**：改 exe 资源段 → 改的是布局/菜单/图标/文案；改 DWM 属性 → 只改标题栏；真正的「整窗暗色」要么程序自己支持，要么走配置文件层（见 Notepad++ 案例）。

### ③ 工具链（Windows 优先）

| 工具 | 用途 | 获取方式 | License |
| --- | --- | --- | --- |
| Resource Hacker | PE 资源查看/反编译/命令行批量改资源 | 官网 https://angusj.com/resourcehacker （v5.2.8，已验证） | **免费软件（freeware）**，但授权条款禁止非法修改软件、禁止未经允许二次分发 |
| ResEdit | 可视化对话框/菜单/图标资源编辑，支持 .rc/.res/.exe/.dll，命令行格式转换 | 官网 http://www.resedit.net/ （已验证） | 免费（见官网条款） |
| 微软官方文档（只读） | DWM/UxTheme/Win32 主题 API | https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-windows-themes （已验证） | — |

**Resource Hacker 命令行真实语法（来自官网，已验证）**：

```bat
REM 单动作：从 old.exe 抽出所有对话框源码存为 dialogs.rc
ResourceHacker.exe -open source.exe -save dialogs.rc -action extract -mask DIALOG,, -log rh.log

REM 单动作：用新图标覆盖 ICONGROUP,MAINICON，另存 new.exe（不动原文件）
ResourceHacker.exe -open old.exe -save new.exe -action addoverwrite -res my.ico -mask ICONGROUP,MAINICON,

REM 脚本批量执行（脚本文本格式如下）
ResourceHacker.exe -script myscript.txt
```

脚本文件 `myscript.txt` 格式：

```
[FILENAMES]
Exe=    MyProg.exe
SaveAs= MyProg_Updated.exe
Log=    MyProg.log
[COMMANDS]
-addoverwrite Bitmap128.bmp, BITMAP,128,
-addoverwrite MainIcon.ico, ICONGROUP,MAINICON,0
-delete  MENU,,0
```

可用 action：`add / addoverwrite / addskip / compile / delete / extract / modify / changelanguage(langID)`；mask 格式 `Type,Name,Language`（逗号必填，可空）。

### ④ 代表开源/工具项目

| 项目 | URL | 说明 | License |
| --- | --- | --- | --- |
| Resource Hacker | https://angusj.com/resourcehacker | 老牌 PE 资源编译器/反编译器，GUI + CLI | freeware（非开源） |
| ResEdit | http://www.resedit.net/ | 开源生态外的免费资源编辑器，支持 VS .rc 导入 | 免费 |
| 微软 Win32 暗色主题文档 | https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-windows-themes | DWMWA_USE_IMMERSIVE_DARK_MODE 官方用法 | — |

### ⑤ 典型坑与对策

| 现象 | 原因 | 对策 |
| --- | --- | --- |
| 改完 exe 资源后程序起不来/被杀软拦 | 重写 PE 破坏数字签名，部分杀软视之为可疑修改 | 只在自有/靶场 exe 上玩；保留原 exe 备份；Resource Hacker 默认另存不覆盖原文件 |
| Resource Hacker 打开是乱码/空资源 | exe 是加壳（packed）的 | 官方明确不脱壳；加壳程序放弃资源路线 |
| 改了对话框颜色无效 | Win32 对话框颜色在代码里用 `WM_CTLCOLORDLG` 绘制，资源段存不了颜色 | 资源段只能改布局/文案/图标，颜色得程序自己支持或走配置层 |
| 上了第三方 msstyles 后系统崩/资源管理器异常 | 未签名 msstyles 需要 patch uxtheme，破坏系统主题校验 | 不做；只参考官方 DWM 标题栏暗色 API |
| `DwmSetWindowAttribute` 调了标题栏不变 | 程序客户区自绘标题栏（非标准 WM_NCCALCSIZE） | DWM 属性只对标准标题栏有效 |

### ⑥ 合规备注

- Resource Hacker 授权条款明确「不得用于非法修改软件」——本路线**只对自有 exe、开源软件、或官方允许自定义资源的程序**操作。
- 不碰微信/QQ 等闭源商业软件的 exe 资源段（即使只是改图标），违反其 EULA 且可能触发杀软/风控。
- msstyles patch、uxtheme hook 类手段不纳入工具箱。

---

## 四、实战案例：Notepad++（Win32 配置文件层换肤标杆）

> Notepad++ 是原生 Win32 + Scintilla 编辑控件的程序，**换肤不靠改 exe，靠 XML 配置文件**——这是「配置文件层换肤」的范式。

### ① 识别特征

- 进程：`notepad++.exe`，模块只有系统 dll + 自带 `Scintilla.dll`（或静态链接）。
- 配置目录：普通安装在 `%APPDATA%\Notepad++\`；便携版/本地配置在安装目录下。
- 关键文件：`stylers.xml`（默认主题）、`stylers.model.xml`（模板）、`Themes\*.xml`（其它主题）、`config.xml`（含暗色模式开关）。

### ② UI 层入口与资源形态

- 入口：设置 → 语言格式设置（Style Configurator）→ 顶部 Select theme 下拉。
- 格式：XML。`<GlobalStyles>` 管全局/控件样式，`<LexerType name="...">` 按语言分，语言下挂 `<WordsStyle>` 条目，每个条目带 `styleID`（对应 Scintilla 的样式编号）、fgColor/bgColor/fontName/fontSize/bold/italic/underline。
- 暗色模式：Notepad++ v8.0.0 起原生支持 Dark Mode（设置 → 首选项 → Dark Mode，三态：Dark/Light/Follow Windows）；暗色主题模板是 `Themes\DarkModeDefault.xml`。
- 路径（已验证）：`%AppData%\Notepad++\Themes\`（普通安装）或安装目录 `Themes\` 子目录（便携版）。

### ③ 工具链

- 纯文本编辑：复制一个现有主题 XML 改名 → 丢进 Themes 目录 → 重启 Notepad++。
- 官方用户手册（已验证）：
  - Themes 页 https://npp-user-manual.org/docs/themes/
  - 暗色模式说明在 Preferences 页 https://npp-user-manual.org/docs/preferences/
  - XML 格式细节在 Config Files 页 https://npp-user-manual.org/docs/config-files/

### ④ 代表开源/社区资源

| 资源 | URL | 说明 |
| --- | --- | --- |
| Notepad++ 官方用户手册 Themes | https://npp-user-manual.org/docs/themes/ | 主题存放路径、新建/重置/导入方法 |
| Dracula for Notepad++ | https://draculatheme.com/notepad-plus-plus | 第三方成熟暗色主题示例（生成 `Dracula.xml`/`Alucard.xml` 丢 Themes 目录） |
| 官方主题集合（GitHub） | 见手册「Sharing Themes」节链接 | 社区主题发布/下载入口 |

### ⑤ 典型坑与对策

| 现象 | 原因 | 对策 |
| --- | --- | --- |
| 复制 XML 进 Themes 后下拉框看不到 | 没重启 Notepad++；或文件编码不对 | 必须退出所有 NPP 实例再开；XML 须 UTF-8 无 BOM |
| 用 Style Configurator 改完又手改 XML，结果打架 | 两种编辑方式同时改会冲突 | 一次只用一种方式 |
| 升级 NPP 后新语言样式丢失/变色 | v8.8.9 起才自动从 model 补齐；老版本需手工同步 `stylers.model.xml` | 升级到 v8.9+；或对照 model 逐段补 `<LexerType>`/`<WordsStyle>` |
| 暗色模式下某些 tab 文字看不清 | 自定义主题没调 Inactive tab 前景色 | 在主题 XML 里补 GlobalStyles 对应条目 |
| 导入主题提示要管理员 | 「设置 → 导入 → 导入主题」写的是安装目录（Program Files） | 用管理员启动 NPP，或手动复制到 `%APPDATA%\Notepad++\Themes\` |

### ⑥ 合规备注

Notepad++ 是 GPL 开源软件，官方文档鼓励自制/分享主题；XML 主题放用户目录完全合规，不涉及任何修改 exe。

---

## 五、DLL 注入 / API Hook 类运行时改色（仅风险分级，不实操）

> 本节只做名词级风险说明，**工具箱不实现、不给出步骤**。

- 原理名词：`SetWindowsHookEx` 全局钩子、DLL 注入（把着色 DLL 塞进目标进程）、`uxtheme.dll` 函数 Hook（拦截 `DrawThemeBackground` 改色）、`WM_PAINT` subclass。
- 能做什么：对任何 Win32 程序运行时强制改色、改标题栏暗色、绕过程序自身配色。
- **风险分级（红区，禁止进工具箱）**：
  - 杀软/EDR 几乎必然报毒（注入 + Hook 是恶意软件经典手法）；
  - 修改他人进程内存可能违反软件 EULA、违反《计算机软件保护条例》对他人软件的完整性要求；
  - 仅可在**自有靶场 exe / 自己写的测试程序**上做研究，不得对日常软件使用。
- 工具箱立场：**不做运行时注入改色**；能走「官方配置文件层」（Notepad++ 式）或「官方主题目录」（OBS 式）的，绝不用注入。

---

## 六、对 Skill 设计的接口建议

### detect 阶段应检测的信号

1. **进程模块扫描**（`Get-Process | Select-Object Modules` 或 Python psutil）：
   - 命中 `Qt5Core.dll/Qt6Core.dll` + `platforms\qwindows.dll` → 判定 **Qt 路线**，记录 Qt 大版本（5/6）。
   - 命中 `Scintilla.dll` 或目录含 `notepad++.exe` + `stylers.xml` → 判定 **Notepad++ 配置层**。
   - 都不命中但 PE 导入表有 `user32.dll!/DialogBoxParamW` → 判定 **Win32 原生**。
2. **目录探测**（只读）：
   - Qt：安装目录 `data\*\themes\*.qss`（OBS 特征）、用户目录 `%APPDATA%\*\themes\`。
   - Notepad++：`%APPDATA%\Notepad++\Themes\*.xml`、`stylers.xml`、`config.xml`。
   - Win32：exe 同目录是否有 RT_MANIFEST（用 Resource Hacker 命令行 `extract` 试探，只读不写）。
3. **配置文件解析**：读 NPP `config.xml` 看暗色开关状态、读 OBS 配置看当前 theme 名。

### apply 需要的操作原语

| 原语 | 说明 | 适用路线 |
| --- | --- | --- |
| `copy_theme_to_user_dir` | 把主题包复制到用户 themes 目录（不碰安装目录） | OBS / NPP / Qt 通用 |
| `backup_file` | 改任何配置/资源前先复制 `.bak-<timestamp>` | 全部 |
| `edit_xml_theme` | 定位 XML 节点替换 fgColor/bgColor（NPP WordsStyle） | NPP |
| `replace_qss_variables` | 只改 QSS 里颜色变量，不动选择器 | OBS 30.2+ / Qt |
| `resource_hacker_extract` | 只读抽取 exe 资源清单做识别（不动写） | Win32 |
| `restart_app` | 提示用户重启目标程序（NPP/OBS 改完都要重启） | 全部 |

### rollback 要点

- 每个 apply 动作必须记录：改了哪个文件、备份路径、目标主题名。
- rollback = 把 `.bak-<timestamp>` 还原 + 删除本次新增的主题文件 + （如改了 NPP 配置）切回原 theme 名。
- 绝不 rollback 到「我不确定原状」的状态——detect 阶段必须先记录当前 theme 名再动手。

### 需要的确认点（执行前必须问用户）

1. 目标程序是不是**用户自有/开源/官方明确支持换肤**的？是闭源商业软件（微信/QQ/付费专业软件）→ 拒绝。
2. 是否允许修改 `%APPDATA%` 下的用户配置（默认允许，但要展示将要写的文件清单）？
3. 是否允许备份原配置到同目录 `.bak-*`（默认允许）？
4. 改完是否由用户自行重启目标程序（Skill 不主动 kill 进程）？

---

## 附：实际验证过的关键链接清单

| URL | 验证方式 | 状态 |
| --- | --- | --- |
| https://github.com/ColinDuquesnoy/QDarkStyleSheet | web.fetch 取页面标题「ColinDuquesnoy/QDarkStyleSheet: A dark style sheet for QtWidgets application」 | 可达 |
| https://qdarkstylesheet.readthedocs.io/en/stable/readme.html | general_search 命中正文 | 可达 |
| https://github.com/UN-GCPDS/qt-material | web.fetch 标题「Material inspired stylesheet for PySide2, PySide6, PyQt5 and PyQt6」 | 可达 |
| https://qt-material.readthedocs.io/en/latest/ | general_search 命中正文 | 可达 |
| https://github.com/tsujan/Kvantum | web.fetch 标题「A Linux SVG-based theme engine for Qt」；Fedora 包页确认 GPL-3.0-or-later | 可达 |
| https://github.com/5yutan5/PyQtDarkTheme | web.fetch 标题「A flat dark theme for PySide and PyQt」 | 可达 |
| https://github.com/Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6 | general_search 命中仓库路径（社区评测标注停更） | 可达 |
| https://github.com/zhiyiYo/PyQt-Fluent-Widgets | general_search + qfluentwidgets.github.io 确认 GPLv3 非商业/商业双授权 | 可达 |
| https://obsproject.com/kb/themes-guide | web.fetch 全文抓取（主题路径/内置主题列表/自定义目录） | 可达 |
| https://obsproject.com/wiki/Custom-Themes | web.fetch 全文抓取（30.2 可组合主题说明） | 可达 |
| https://angusj.com/resourcehacker | web.fetch 全文抓取（v5.2.8，CLI 语法表、脚本格式、freeware 条款） | 可达 |
| http://www.resedit.net/ | web.fetch 抓取（Features 页，支持 .rc/.res/.exe/.dll） | 可达 |
| https://npp-user-manual.org/docs/themes/ | web.fetch 全文抓取（路径/新建/重置/UTF-8 无 BOM 要求） | 可达 |
| https://npp-user-manual.org/docs/preferences/ | general_search 命中 Dark Mode v8.0.0 段落 | 可达 |
| https://npp-user-manual.org/docs/config-files/ | general_search 命中 stylers.xml 格式说明 | 可达 |
| https://draculatheme.com/notepad-plus-plus | general_search 命中（生成 XML 丢 Themes 目录） | 可达 |
| https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-windows-themes | general_search 命中 DWMWA_USE_IMMERSIVE_DARK_MODE 官方说明 | 可达 |
| https://doc.qt.io/qt-6/resources.html | general_search 命中（Qt Resource System 官方文档） | 可达 |
| https://doc.qt.io/qt-6/stylesheet-reference.html | web.fetch 全文抓取（QSS 选择器/属性/伪状态参考） | 可达 |
| https://doc.qt.io/qt-6/windows-deployment.html | general_search 命中（windeployqt、qwindows.dll 部署文档） | 可达 |

> 备注：GitHub 仓库页在自动化抓取时会返回「Something went wrong」的 UI 占位，但页面 `<title>` 已正确返回仓库名与描述，视为链接有效；文档站与官网均为正文级抓取。
