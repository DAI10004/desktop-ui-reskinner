# WPF / WinForms 路线速查

## 识别
- WPF 信号：`PresentationFramework.dll`/`PresentationCore.dll`/`PresentationNative*.dll`、`*.exe.config`（supportedRuntime）、`*.g.resources`、`.deps.json` 引用 PresentationFramework。
- WinForms 信号：`System.Windows.Forms.dll`、`System.Drawing.dll`、`*.resources`、`zh-Hans\*.resources.dll` 卫星目录。

## UI 层入口
- WPF：XAML 编译成 BAML 内嵌主程序集。**微软没有官方 BAML→XAML 回编译器**，本工具箱不回编 BAML。
  - 推荐路径：外挂松散 ResourceDictionary / 走应用自带主题库（MaterialDesignInXaml、WPF-UI、HandyControl、ModernWpf）/ 应用设置文件。
  - 禁止路径：dnSpy 改 IL、回编 BAML 写回主程序集。
- WinForms：控件布局在 IL 里硬编码，无统一样式字典；能换的只有 `.resources` 里的图片/图标/颜色。

## 命令示例
```bash
python scripts/reskin.py --json detect --target "C:\Path\WpfApp"
# WPF 换肤本质是配置/主题文件层操作，多数走 replace_file 即可，不碰 exe 字节。
```

## 坑
- Single-file 发布：目录里只有一个 exe（bundle），运行时解压到 `%TEMP%\.net\`。
- StrongName：改字节后强命名校验失效，`sn -Vr` 只适合开发机。
- WinForms 的图片是序列化 `System.Drawing.Bitmap`，不是裸 BMP——Resource Hacker 换不了 .NET 托管资源。
- DWM 暗色 API 只改标题栏，客户区要自己遍历控件改色。

## 合规
- 反编译仅用于学习研究/互操作/主题美化；不用 dnSpy 改授权校验、时间限制、付费解锁。
- 主题库（MaterialDesignInXaml 等）多为 MIT，二次分发保留 LICENSE 即可。
