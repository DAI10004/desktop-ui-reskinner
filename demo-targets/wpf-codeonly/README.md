# WPF code-only 演示靶场

不依赖 .NET SDK 的纯代码 WPF 最小程序，作为 desktop-ui-reskinner 的 WPF 路线验证靶场。

## 合规说明（重要）

真实成品 WPF 应用的样式通常编译进 `BAML`（内嵌在程序集资源中），**没有官方的 BAML 回编工具链**。
本靶场与配套换肤包采用研究文档中明确记载的合法替代路径：**外挂松散 ResourceDictionary（theme.xaml）**——
程序启动时用 `XamlReader.Parse` 动态加载同目录 `theme.xaml`，换肤即替换该文件。

> desktop-ui-reskinner 工具箱对 BAML 内嵌资源保持只读 / `unsupported` 立场，
> 不做任何 IL 改写、反编译重编译或签名破坏。

## 构建

用 .NET Framework 自带的 `csc.exe` 直接编译（幂等，可重复运行）：

```powershell
powershell -ExecutionPolicy Bypass -File demo-targets\wpf-codeonly\build.ps1
```

产物：`demo-targets\wpf-codeonly\WpfDemo.exe`。

## 运行

```powershell
.\demo-targets\wpf-codeonly\WpfDemo.exe
```

- 窗口标题：`Reskinner WPF Demo`。
- 含 Button / ListBox / TextBox / StatusBar，颜色走 DynamicResource 键 `AppBg`/`AppFg`/`Accent`。
- 同目录存在 `theme.xaml` 时外挂加载；不存在则用内置浅色兜底。

配套换肤包：`examples/skin-packs/wpf-dark/`（替换为暗色 theme.xaml）。
