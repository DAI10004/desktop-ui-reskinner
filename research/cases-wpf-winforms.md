# WPF / WinForms 换肤与 UI 检查工具链调研

> 一句话路线总览：WPF 靠「识别 Presentation*.dll + BAML 资源」定位 UI 层，以**只读反编译 + 外挂松散 ResourceDictionary/启动器注入**为主，避免回编 BAML；WinForms 靠「System.Windows.Forms + .resources/.resx 卫星资源」定位，用 Resource Hacker / ResXResourceReader 替换图片与颜色；再用 Snoop/FlaUInspect/Inspect 做运行时可视化树检查，用 pywin32+PrintWindow 做换肤前后截图对比。

> 本机前提（2026-10-20 实测）：Windows 11，仅有 .NET 运行时、**无 .NET SDK**（`dotnet` 报 "No .NET SDKs were found"）。因此 `ilspycmd` 等 dotnet tool 当前**无法直接安装运行**，下文工具链一律标注「需先 `winget install Microsoft.DotNet.SDK.8`」。本调研**不安装任何软件、不改系统**，仅做资料整理。

---

## 一、WPF 识别特征与发布形态

### ① 识别特征（可机器判定）
- 程序集引用 `PresentationFramework.dll` / `PresentationCore.dll` / `WindowsBase.dll` / `System.Xaml.dll`（用 `dnlib` 或 PowerShell 反射读 Assembly 的 `GetReferencedAssemblies()` 即可判定）。
- 同目录存在 `<AppName>.exe.config`，且其中有 `<supportedRuntime sku=".NETFramework,v=v4.x" />`（.NET Framework 4.x 老 WPF）或指向 `Microsoft.WindowsDesktop.App`（.NET Core 3.0+ / .NET 5+）。
- 资源清单里出现 `<g>.resources`（BAML 容器）和 `themes/generic.baml`、`themes\Default.xaml` 之类条目。
- 运行时进程模块列表里能看到 `PresentationFramework.ni.dll`、`wpfgfx_v0400.dll`、`PresentationNative_*.dll`。

### ② UI 层入口与资源形态
- 编译时 `.xaml` → MSBuild 任务标记为 `Page` → 生成 `.baml`（Binary XAML）→ 作为 `EmbeddedResource` 嵌入主程序集，逻辑名通常为 `<AssemblyBaseName>.g.resources`。
- `App.xaml` 对应的 BAML 决定启动时加载哪些 `MergedDictionaries`；`themes/generic.xaml` 里放自定义控件默认样式。
- .NET Framework 4.x：依赖统一在 GAC（`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\WPF\`）。
- .NET 5/6/8/9（Windows Desktop Runtime）：依赖在 `C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App\8.0.x\`。

### ③ 工具链
| 工具 | 用途 | License | 安装/获取 |
|---|---|---|---|
| .NET SDK 8 | 跑 ilspycmd、后续重打包前置 | MIT | `winget install Microsoft.DotNet.SDK.8`（本机**未装**） |
| PowerShell 5.1 | 反射读引用程序集、列资源 | 系统自带 | 已在 |
| Python 3.13 + `pefile`/`dnfile`（可选） | 解析 PE、CLR 头 | MIT | `pip install pefile dnfile` |

### ④ 代表开源项目
- **Microsoft Learn · .NET 应用发布概述**：https://learn.microsoft.com/en-us/dotnet/core/deploying/ — 官方说明 single-file / self-contained / ReadyToRun / NativeAOT 四种发布形态的开关（`PublishSingleFile`、`PublishReadyToRun`、`PublishAot`）。CC-BY。

### ⑤ 典型坑与对策
| 坑 | 表现 | 对策 |
|---|---|---|
| Single-file 发布 | 目录里只有一个 `.exe`，无独立 dll | 实际是 bundle（apphost + 内嵌 dll），运行时解压到 `%TEMP%\.net\<app>\`；可用 `dotnet-bundle` 工具解包，或直接运行后从临时目录取 |
| ReadyToRun | 程序集带 R2R 原生代码段，ILSpy 能反编译但多出 native stub | 不影响读 BAML / 改 managed 资源；改完用 R2R 的 app 重签名即可，无需重 R2R |
| NativeAOT | **WPF 官方不支持 NativeAOT**（WPF 依赖 JIT/反射），遇到 `ilcompiler` 产物基本不是 WPF 主线 | 若真出现，按 Win32 原生程序处理，BAML 路线作废 |
| .NET Framework vs .NET Core 运行时目录混淆 | 找错 PresentationFramework.dll 路径 | 先看 exe.config / `runtimeconfig.json` 判断目标框架 |

### ⑥ 合规备注
识别只读、不修改字节；识别阶段不要 dump 用户目录里的私有程序集，只在用户指定的目标目录操作。

---

## 二、WPF UI 层入口：XAML → BAML 与反编译查看链路

### ① 识别特征
- 主 dll/exe 的 ManifestResource 里能列出 `*.g.resources`；用 `ResourceManager`/反射可枚举其中键名，形如 `App.baml`、`MainWindow.baml`、`themes/generic.baml`。
- `App.g.i.cs` 等价物不存在（已编译），但 BAML 里保留了 `StartupUri`、`MergedDictionaries` 引用的程序集短名。

### ② UI 层入口与资源形态
- BAML 是 XAML 的二进制序列化，**字符串池化 + 类型引用 token**，人类不可读，但 ILSpy/dnSpy 内置反插件能反出可读 XAML。
- 核心坑：**微软没有提供官方 BAML→XAML 回编译器**。`LocBaml` 是定位/提取本地化字符串用的工具，不是通用回编；社区里 ILSpy 的 `ICSharpCode.BamlDecompiler` 能反出 XAML 文本，但**没有把 XAML 重新编译成合法 BAML 并写回资源段**的官方支持路径。

### ③ 工具链
| 工具 | 用途 | License | 安装 |
|---|---|---|---|
| ILSpy（GUI） | 图形化浏览 BAML、反编译 C# | MIT | https://github.com/icsharpcode/ILSpy Releases 免安装 zip |
| ilspycmd（CLI） | 命令行批量反编译、导出项目 | MIT | 需先装 SDK：`dotnet tool install -g ilspycmd` |
| dnSpyEx | 反编译 + 调试 + **直接编辑 IL/方法** | GPL-2.0（含插件） | https://github.com/dnSpyEx/dnSpy/releases 免安装 |
| dnlib | 程序化读写 .NET 程序集（资源段、元数据） | MIT | NuGet `dnlib`，GitHub https://github.com/0xd4d/dnlib |
| Mono.Cecil | 另一套程序化读写库，API 友好 | MIT/X11 | NuGet `Mono.Cecil`，https://github.com/jbevain/cecil |
| ICSharpCode.BamlDecompiler | ILSpy 内置的 BAML→XAML 反插件库 | MIT | NuGet，ILSpy 已自带 |

### ④ 代表开源项目
- **ICSharpCode/ILSpy**：https://github.com/icsharpcode/ILSpy — 跨平台 .NET 反编译器，支持 ReadyToRun、PDB 生成；`ilspycmd` 是其 CLI。MIT。
- **dnSpyEx/dnSpy**：https://github.com/dnSpyEx/dnSpy — 原 dnSpy 已停更，本仓库是非官方延续分支，当前最新 v6.5.1；带调试器与程序集编辑器。GPL-2.0。
- **0xd4d/dnlib**：https://github.com/0xd4d/dnlib — 从 de4dot 衍生的低层 .NET 读写库，抗混淆强。MIT。
- **jbevain/cecil**：https://github.com/jbevain/cecil — Mono.Cecil 官方仓库。MIT/X11。

### ⑤ 典型坑与对策
| 坑 | 表现 | 对策 |
|---|---|---|
| 无官方 BAML 回编 | 改了反出来的 XAML 后无法写回 | **不要回编**；改用「外挂松散 ResourceDictionary」或「启动器注入」路线（见下） |
| BAML 反出来丢事件钩子 | 反编译 XAML 里 `Click="Button_Click"` 不见了 | BAML 只存事件 token，反 XAML 时不会重挂事件，属正常；只读参考用 |
| dnSpy 编辑 IL 后签名/版本不一致 | 改完启动报 StrongName 验证失败 | 用 `sn -Vr` 跳过验证，或用 dnlib 重命名/重签；详见第六节 |
| 单文件 bundle 里找不到 dll | 直接反编译 exe 看不到 BAML | 先解包 bundle 到临时目录，再反编译里面的 managed dll |

**替代路径（不回编 BAML）：**
1. **追加松散 ResourceDictionary**：在目标 exe 同目录放一个 `Themes/MyTheme.xaml`，再用启动器（下条）在 `App.OnStartup` 里 `Application.Current.Resources.MergedDictionaries.Add(new ResourceDictionary { Source = new Uri("Themes/MyTheme.xaml", UriKind.Relative) })`。要求目标 App 是标准 WPF App 类、且资源键不冲突。
2. **启动器注入 App.xaml 资源**：写一个 thin launcher exe，`Assembly.LoadFrom` 原主 dll、反射建 `App` 实例，在 `Run()` 之前把外部字典塞进 `Resources.MergedDictionaries`；边界是原 App 若在 `App` 构造函数里硬编码 `StartupUri`/`MainWindow` 就会被覆盖。
3. **直接换皮肤库（推荐给 Skill 默认路径）**：如果目标程序本身支持换肤（读 settings.json 里的主题包），只替换主题包文件即可，零改字节。

### ⑥ 合规备注
反编译仅用于学习研究、互操作、主题美化；不得用 dnSpy 改授权校验、时间限制、付费解锁逻辑。

---

## 三、WPF 开源主题库实战（换肤原理与接入方式）

### ① 识别特征（如何判断目标 app 用了哪个库）
- 引用了 `MaterialDesignThemes` / `MaterialDesignColors` NuGet 包 → 程序集里有 `MaterialDesignColors.dll`、`MaterialDesignThemes.Wpf.dll`。
- 引用 `WpfUI` / `HandyControl` / `ModernWpf` → 同目录对应 dll。
- `App.xaml` 的 `MergedDictionaries` 里能反出 `pack://application:,,,/MaterialDesignThemes.Wpf;...`、`/HandyControl;...`、`/ModernWpf;...`。

### ② UI 层入口与资源形态
所有主题库本质都是**一堆 ResourceDictionary + 自定义控件**，通过 `MergedDictionaries` 合并进 `App.Resources`，把原生 `Button`/`TextBox` 等样式 `TargetType` 全局覆盖掉。运行时切换主题 = 换一套字典 + 改主题色资源键。

### ③ 工具链
- NuGet 包管理：`dotnet add package <pkg>`（需 SDK）。
- 主题切换 API 多在运行时通过 `PaletteHelper` / `ThemeManager` 静态类调用。

### ④ 代表开源项目
| 项目 | URL（已验证可达） | 一句话说明 | License |
|---|---|---|---|
| MaterialDesignInXamlToolkit | https://github.com/MaterialDesignInXAML/MaterialDesignInXamlToolkit | Google Material Design 风格的 WPF 控件+主题库；`PaletteHelper.SwitchDarkThemeAsync()` 切深浅色 | MIT |
| WPF UI (lepoco) | https://github.com/lepoco/wpfui | Fluent/WinUI 风格现代控件库，自带 `ThemeManager.ApplicationTheme` 切 Light/Dark/HighContrast；官网 https://wpfui.lepo.co/ | MIT |
| HandyControl | https://github.com/HandyOrg/HandyControl | 国产轻量 WPF 控件库，重写原生样式 + 80+ 自定义控件；主题由 `ThemeManager.Current.RegionMode/ColorName` 控制 | MIT |
| ModernWpf (Kinnara) | https://github.com/Kinnara/ModernWpf | 把 WinUI/Windows 10 现代样式搬到 WPF，NuGet 包名 `ModernWpfUI`；`ThemeManager.Current.ApplicationTheme = Default/Dark/Light` | MIT |
| （补充）.NET 9 内置 Fluent 主题 | https://learn.microsoft.com/en-us/dotnet/desktop/wpf/whats-new/net90 | .NET 9 WPF 原生带 Fluent 主题，`ThemeMode` 属性切深浅色，无需第三方库 | 官方 |

### ⑤ 典型坑与对策
| 坑 | 对策 |
|---|---|
| 第三方库 dll 没随 exe 一起发布（裁剪了） | 反编译看到 PackUri 但 dll 不在 → 目标 app 是 self-contained 裁剪发布，需从 NuGet 还原同版本 dll 才能外挂字典 |
| 主题库版本与目标 .NET 版本不兼容 | WPF-UI 要求 .NET 6+；老 .NET Framework 4.x 项目只能用 MaterialDesignInXaml v4.x 或 ModernWpf |
| 颜色资源键名冲突 | 外挂字典放在 `MergedDictionaries` **最后一项**，WPF 后加者覆盖先加者 |
| 暗色模式只改客户区、标题栏仍是白色 | 必须叠加 DWM 暗色 API（见第五节），主题库不替你管非客户区 |

### ⑥ 合规备注
主题库均为 MIT，二次分发/嵌入自己的换肤包时保留 LICENSE 文件即可。

---

## 四、WPF 支持主题切换的开源应用案例：ScreenToGif

### ① 识别特征
- 主程序集 `ScreenToGif.exe`，引用 `MaterialDesignThemes` + 自研主题资源。
- 设置文件 `Settings.xaml`/JSON 里有 `DarkTheme`/`LightTheme` 布尔键。

### ② UI 层入口与资源形态
- WPF + .NET 6/8 桌面发布；主题切换走 `App.xaml` 的 `MergedDictionaries` 在运行时移除/插入不同主题字典。
- 它是「第三方主题库接入 + 运行时切主题」的参考实现，适合照抄其模式。

### ③ 工具链
- 直接从 GitHub Releases 下便携版做参考：https://github.com/NickeManarin/ScreenToGif/releases 。
- 阅读其源码 `App.xaml` / `Views/Themes/` 目录即可看主题合并写法。

### ④ 代表开源项目
- **NickeManarin/ScreenToGif**：https://github.com/NickeManarin/ScreenToGif — 开源录屏转 GIF/视频工具，WPF 写的，内置深浅色主题切换。License：MS-PL（Microsoft Public License，允许修改/再分发，需保留版权）。

### ⑤ 典型坑与对策
| 坑 | 对策 |
|---|---|
| 主题字典里写死了程序集名 | 外挂字典若想用同样 key，需保证目标 app 已加载对应主题 dll |
| 设置项分散在 user.config | 换肤前先备份 `%AppData%\ScreenToGif\` |

### ⑥ 合规备注
MS-PL 对修改后公开源码有要求；本调研仅参考其写法，不复制代码进闭源分发物。

---

## 五、WinForms 路线：System.Windows.Forms / .resx / DWM 暗色

### ① 识别特征（可机器判定）
- 程序集引用 `System.Windows.Forms.dll`、`System.Drawing.dll`。
- 同目录有 `*.exe.config` 指向 .NET Framework 4.x（WinForms 在 .NET Core 3.0+ 也支持，但老 app 基本是 .NET Framework）。
- 资源清单里有 `<AppName>.resources`、`Properties.Resources.resources`，以及 `zh-Hans\`、`en\` 等卫星程序集目录（`<AppName>.resources.dll`）。

### ② UI 层入口与资源形态
- `.resx`（XML）编译为 `.resources`（二进制 ResourceManager 格式）嵌入主 dll 或卫星 dll；里面主要存 `Bitmap`、`Icon`、`string`、`Color` 等强类型资源。
- WinForms 控件的 `BackgroundImage`、`Icon`、`Text` 都从这里取；窗体本身的布局是 IL 里 InitializeComponent 硬编码，**不像 WPF 那样有统一样式字典**，所以 WinForms 换肤基本只能「换图片资源 + 改颜色资源 + 注入 DWM 暗色标题栏」，做不到全局样式覆写。

### ③ 工具链
| 工具 | 用途 | License | 安装 |
|---|---|---|---|
| Resource Hacker | 可视化/命令行改 Win32 PE 资源（图标、位图、对话框、版本） | Freeware（免费可用、非 OSI 开源） | http://www.angusj.com/resourcehacker/ （官网，非 GitHub） |
| ResXResourceReader / ResXResourceWriter | .NET 反射读改写 .resources/.resx | MIT（.NET 运行时自带） | 无需安装，PowerShell `Add-Type -AssemblyName System.Windows.Forms` 即可 |
| Python `dnfile` + 自写脚本 | 程序化列 .resources 条目 | MIT | `pip install dnfile` |
| DwmSetWindowAttribute (dwmapi.dll) | 标题栏暗色 | Windows SDK 自带 | P/Invoke 调用，`pip install pywin32` 后用 `ctypes.windll.dwmapi` |

### ④ 代表开源项目
- **Microsoft Learn · Support Dark and Light themes in Win32 apps**：https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-windows-themes — 官方文档讲 `DWMWA_USE_IMMERSIVE_DARK_MODE`（值 19 在 Build 18985 之前，20 在之后；推荐传 -1/20 做兼容）。
- **Microsoft Learn · DWMWINDOWATTRIBUTE**：https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute — 枚举值参考。

### ⑤ 典型坑与对策
| 坑 | 对策 |
|---|---|
| `.resources` 里图片是序列化的 `System.Drawing.Bitmap`，不是裸 BMP | 用 `ResourceReader` 读出来后保存为 PNG，改完用 `ResourceWriter` 写回；不能用 Resource Hacker 直接换（Resource Hacker 只认 Win32 RT_BITMAP/RT_ICON，不认 .NET managed resources） |
| Resource Hacker 改不动 .NET 托管资源 | 它改的是 PE 原生资源段（图标、版本、对话框）；.NET 图片资源必须用 ResXResourceWriter/dnlib 改 |
| DWM 暗色只改标题栏，客户区仍是白底 | DWM 只管非客户区；客户区暗色要自己遍历控件改 BackColor/ForeColor，或用第三方库（如 DarkMode 库） |
| WinForms 4.8 调 DWM 暗色后标题栏不立即刷新 | 重发 `WM_NCACTIVATE` 触发非客户区重绘（详见社区博客做法） |
| 卫星程序集被改后文化名不匹配 | 卫星 dll 文件名必须是 `<App>.resources.dll` 放在 `zh-Hans\` 等子目录，否则 ResourceManager 找不到 |

### ⑥ 合规备注
改图标/图片资源仅用于个人美化、学习；不要改程序集版本号、公司名、版权信息去冒充他人软件。

---

## 六、通用 UI 检查与效果验证工具（跨 WPF/WinForms）

### ① 识别特征（工具选型信号）
- 进程模块里有 `PresentationFramework*.dll` → 走 WPF 专用可视化树工具（Snoop）。
- 进程模块里有 `System.Windows.Forms.dll` → 走 Win32 窗口工具（Spy++ / Inspect）。
- 只想做自动化读写控件属性 → 走 UIAutomation 路线（FlaUI / pywinauto）。

### ② UI 层入口与资源形态
- WPF：可视化树是运行时对象，不写在磁盘上，必须 attach 到运行中的进程。
- WinForms/Win32：窗口句柄、类名、消息流是可观察对象，Spy++ 直接看。
- 换肤后效果验证 = 启动目标 app → 截图 → 与基线 diff。

### ③ 工具链
| 工具 | 能力 | License | 获取 |
|---|---|---|---|
| Inspect.exe | Windows SDK 自带，看 UIA/MSAA 属性、控件树 | 系统/SDK 免费 | 随 Windows SDK 装；已被微软标记为 legacy，推荐 Accessibility Insights 替代 |
| UISpy | 老牌 UIA 查看器（已停更） | MS-PL | CodePlex 归档，不推荐新装 |
| Spy++ (SPYXX.EXE) | 随 Visual Studio 装；看 Win32 窗口/线程/消息 | VS 自带 | Visual Studio 安装包选「C++ 桌面开发」即带 |
| Snoop | WPF 专属实时可视化树浏览器，可改属性、看触发器 | MIT | https://github.com/snoopwpf/snoopwpf/releases （`winget install SnoopWpf` 亦可） |
| FlaUI / FlaUInspect | .NET UIA 自动化库 + 对应 Inspector GUI | BSD-3-Clause | https://github.com/FlaUI/FlaUI ；Inspector：https://github.com/FlaUI/FlaUInspect |
| pywinauto（Python） | Python 封装 UIA/Win32 后端，可脚本化 inspect + 截图 | BSD-3 | `pip install pywinauto` |
| pywin32 + PrintWindow（Python） | 对单个 HWND 截窗口图（即使被遮挡） | PSF（Python 软件基金会） | `pip install pywin32` |
| Pillow.ImageGrab | 全屏截 + crop 窗口区域 | HPND | `pip install pillow` |

### ④ 代表开源项目
- **snoopwpf/snoopwpf**：https://github.com/snoopwpf/snoopwpf — WPF Spy Utility，attach 到任意运行中 WPF 进程看视觉/逻辑/自动化树，改属性值、属性断点。MIT。
- **FlaUI/FlaUI**：https://github.com/FlaUI/FlaUI — .NET UIA 自动化库；配套 Inspector 在 https://github.com/FlaUI/FlaUInspect 。BSD-3。
- **Microsoft Learn · Choose the right visual tree viewer**：https://learn.microsoft.com/en-us/windows/apps/develop/ui/visual-tree — 官方建议：WinForms/Classic VB 用 Spy++；WPF 用 Visual Studio Live Visual Tree 或 Snoop；UIA 跨框架用 Inspect/Accessibility Insights。

**「换肤后自动截图对比」Python 实现路径（推荐）：**
```python
# pip install pywin32 pillow
import win32gui, win32ui, win32con
from PIL import Image

def capture_window(hwnd: int, out_path: str):
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    # PW_RENDERFULLCONTENT = 0x00000002，对 DWM 渲染的 WPF 窗口更稳
    win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0x00000002)
    bmp.SaveBitmapFile(save_dc, out_path)
    # 清理 GDI 对象略
    Image.open(out_path).convert("RGB").save(out_path)  # 转 PNG 便于 diff
```
- 已知坑：硬件加速/DWM 合成窗口 `PrintWindow` 偶尔返回黑图；备选路径是 `ImageGrab.grab(bbox=GetWindowRect(hwnd))`（要求窗口在前台不被遮挡）。
- diff 思路：`Pillow.ImageChanges.difference(a, b)` 或 `numpy.mean(abs(a-b))`，输出差异图与数值。

### ⑤ 典型坑与对策
| 坑 | 对策 |
|---|---|
| Snoop attach 不上 .NET Core WPF | 用 Snoop v5+；旧 v3 只支持 .NET Framework |
| PrintWindow 截 WPF 黑图 | 用 `PW_RENDERFULLCONTENT=2` 标志；或退到前台 + ImageGrab |
| Inspect.exe 在新版 Win11 找不到 | 它在 Windows SDK 目录 `C:\Program Files (x86)\Windows Kits\10\bin\<ver>\x64\Inspect.exe`；或直接装 Accessibility Insights |
| Spy++ 看不到 WPF 内部控件 | WPF 顶层是一个 HWND，内部全是 DirectComposition 画的；必须用 Snoop |
| 截图对比被 DWM 阴影/动画干扰 | 固定等待 1s、关动画、对比客户区客户矩形（去掉边框） |

### ⑥ 合规备注
截图仅在用户自己机器上、自己拥有授权的程序上做；不要截他人隐私窗口。

---

## 七、强命名 / Authenticode / 程序集版本等系统坑

### ① 识别特征
- 用 `Get-AuthenticodeSignature <file>` 看数字签名状态（Valid / NotSigned / HashMismatch）。
- 用 `sn -T <assembly>` 看公钥 token，判断是否强命名。
- 改任何字节后，这两个工具会立刻告诉你签名失效。

### ② UI 层入口与资源形态
- 强命名签名在 CLR 头的 CLI 元数据里；Authenticode 在 PE 校验目录。
- 只要改了 PE 内任何字节（包括 .resources 段、BAML 段），**Authenticode 哈希立刻失效**；强命名哈希同理失效。

### ③ 工具链
| 工具 | 用途 | License |
|---|---|---|
| signtool.exe（Windows SDK） | 重签 Authenticode、时间戳 | SDK 自带 |
| sn.exe（.NET SDK） | 强命名签名/跳过验证 `sn -Vr` | SDK 自带 |
| PowerShell `Set-AuthenticodeSignature` | 简易重签（自签名证书） | 系统自带 |

### ④ 代表开源项目
- **Microsoft Learn · SignTool**：https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool — sign/remove/verify 命令。
- **Microsoft Learn · Authenticode and Assemblies（ShawnFa 博客归档）**：https://learn.microsoft.com/en-us/archive/blogs/shawnfa/authenticode-and-assemblies — 讲强命名与 Authenticode 的包裹关系：改强命名会同时废掉两者，但改 Authenticode 只废 Authenticode。

### ⑤ 典型坑与对策
| 坑 | 后果 | 对策 |
|---|---|---|
| 改字节后 Authenticode 失效 | SmartScreen 警告、企业 EDR 拦截 | 个人/学习环境用 `Set-AuthenticodeSignature` 自签；商用必须用 EV/OV 证书重签（用户责任） |
| 改字节后强命名失效 | CLR 加载报 `StrongNameSignatureVerification` | 开发机 `sn -Vr *,*` 跳过验证；发布环境不能跳 |
| 程序集版本号被改 | 依赖方 binding redirect 找不到版本 | **不要改 AssemblyVersion**，只改 AssemblyFileVersion；或保持 1.0.0.0 |
| 卫星程序集文化名错 | ResourceManager 回退到中性资源 | 卫星 dll 目录名 = 文化名，dll 名 = `<App>.resources.dll` |
| 改完跑不起来：MissingMethod/TypeLoad | IL 编辑破坏了 token 引用 | 优先用「外挂字典 + 启动器」路线，不直接改 IL |
| Single-file bundle 里的 dll 被替换 | apphost 哈希校验失败启动不了 | 先解 bundle、改完重新打包成 bundle（用 `Microsoft.NET.HostModel`） |

### ⑥ 合规备注
**本工具箱不提供绕过多人授权、去除试用提示、解锁付费功能的能力**；重签名仅限用户自己拥有合法授权的软件，且用于学习/互操作。

---

## 八、对 Skill 设计的接口建议

### 8.1 `detect` 信号（只读、零副作用）
输入：目标目录或 exe 路径。输出 JSON：
```json
{
  "kind": "wpf_framework48" | "wpf_net8" | "winforms_net48" | "win32_native" | "unknown",
  "references": ["PresentationFramework","System.Windows.Forms", ...],
  "app_config": "...",
  "resources": {"g.resources": ["App.baml","MainWindow.baml","themes/generic.baml"]},
  "publish_shape": "framework_dependent" | "self_contained" | "single_file" | "readytorun" | "nativeaot",
  "signing": {"authenticode":"Valid","strong_named":true},
  "third_party_themes": ["MaterialDesignThemes","HandyControl"]
}
```
实现：PowerShell 反射列 `GetReferencedAssemblies()` + `[System.Reflection.Assembly]::ReflectionOnlyLoadFrom` 列 ManifestResource；不落地写文件。

### 8.2 策略：只读优先 / 不重编 BAML
- **默认路径**：外挂松散 ResourceDictionary（WPF）或替换主题包文件（若 app 自带换肤）；启动器注入作为 fallback。
- **禁止路径**：用 dnSpy 改 IL、用工具回编 BAML 写回主程序集。Skill 文档里把这两条写成显式黑名单。
- 所有写操作必须先备份原文件到 `<target>.bak/` 目录，并记录 SHA256。

### 8.3 资源替换原语
| 原语 | 输入 | 实现 |
|---|---|---|
| `wpf.list_themes` | exe 路径 | 列 `g.resources` 下 BAML 名 + 反出的 Theme 字典名（需 SDK+ilspycmd 可选） |
| `wpf.attach_loose_dict` | exe 路径 + 外部 xaml | 把 xaml 拷到 `<exe>.Theme/`，生成 launcher.exe 或 patch `.csproj` 等价物（不重编原 exe） |
| `winforms.list_resources` | exe 路径 | `ResourceReader` 枚举 `Properties.Resources.resources` 键 |
| `winforms.replace_image` | exe 路径 + 资源键 + png 路径 | `ResourceWriter` 写回（需先备份） |
| `winforms.set_dark_titlebar` | exe 路径 / HWND | 启动后 P/Invoke `DwmSetWindowAttribute` |

### 8.4 截图验证原语
- `shot.capture(hwnd, out_png)`：pywin32 PrintWindow + Pillow 转 PNG。
- `shot.diff(baseline, current, out_diff)`：numpy 算 MAE + 输出差异热力图。
- 调用方负责启动 app、等渲染稳定、定位窗口。

### 8.5 回滚与确认点
- 所有写操作前：`Copy-Item <exe> <exe>.bak.<timestamp>`。
- 写操作分两阶段：dry-run（只打印将做什么）→ 用户确认 → apply。
- 回滚命令：`rollback(<target>)` 从 `.bak.<timestamp>` 还原并校验哈希。
- 对签名失效的提示：**不自动重签**，只在输出里警告「Authenticode 已失效，是否继续由用户决定」。

---

## 九、已验证关键链接清单（URL + 状态）

| URL | 状态 | 说明 |
|---|---|---|
| https://github.com/dnSpyEx/dnSpy | 200（title 命中） | dnSpy 维护分支，Releases 在同仓库 |
| https://github.com/snoopwpf/snoopwpf | 200（title 命中） | WPF Spy Utility |
| https://github.com/lepoco/wpfui | 200（title 命中） | WPF UI (Fluent) |
| https://github.com/HandyOrg/HandyControl | 200（title 命中） | HandyControl |
| https://github.com/Kinnara/ModernWpf | 200（title 命中） | ModernWpf |
| https://github.com/MaterialDesignInXAML/MaterialDesignInXamlToolkit | 200（title 命中） | MaterialDesignInXaml |
| https://github.com/NickeManarin/ScreenToGif | 200（title 命中） | ScreenToGif |
| https://github.com/FlaUI/FlaUI | 200（title 命中） | FlaUI |
| https://github.com/FlaUI/FlaUInspect | 200（title 命中） | FlaUInspect |
| https://github.com/icsharpcode/ILSpy | 200（title 命中） | ILSpy / ilspycmd |
| https://github.com/0xd4d/dnlib | 200（title 命中） | dnlib |
| https://github.com/jbevain/cecil | 200（title 命中，经 Mono/.NET Foundation 页交叉验证） | Mono.Cecil |
| http://www.angusj.com/resourcehacker/ | 200（搜索结果直引） | Resource Hacker 官网 |
| https://learn.microsoft.com/en-us/dotnet/core/deploying/ | 200（搜索结果直引） | .NET 发布形态官方文档 |
| https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-windows-themes | 200（搜索结果直引） | DWM 暗色标题栏 |
| https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute | 200（搜索结果直引） | DWMWINDOWATTRIBUTE 枚举 |
| https://learn.microsoft.com/en-us/windows/apps/develop/ui/visual-tree | 200（搜索结果直引） | 可视化树工具选型 |
| https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool | 200（搜索结果直引） | signtool 命令 |
| https://learn.microsoft.com/en-us/dotnet/desktop/wpf/whats-new/net90 | 200（搜索结果直引） | .NET 9 内置 Fluent 主题 |
| https://www.nuget.org/packages/ilspycmd/ | 200（搜索结果直引） | ilspycmd NuGet 页 |
| https://pypi.org/project/appsnap/ | 200（搜索结果直引） | PrintWindow 截图 Python 参考 |

> 注：GitHub 页面因 JS 渲染返回 "Something went wrong" 是 web.fetch 抓取壳的表现，`<title>` 标签均命中预期仓库名，即视为可达。
