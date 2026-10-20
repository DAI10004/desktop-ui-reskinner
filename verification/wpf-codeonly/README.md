# WPF (code-only) 靶场端到端验证记录

时间：2026-10-20（Asia/Shanghai）

## 环境

- 无 .NET SDK；使用系统自带 `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`。
- 引用程序集（GAC，已验证存在）：PresentationFramework / PresentationCore(GAC_64) / WindowsBase / System.Xaml，版本 `v4.0_4.0.0.0__31bf3856ad364e35`。
- 编译产物：`demo-targets\wpf-codeonly\WpfDemo.exe`（6144 字节，幂等可重复）。
- 截图：ctypes `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT=2)` + Pillow，无需 pywin32。

## 命令序列与退出码

| 步骤 | 命令 | 退出码 | 实际结果 |
|---|---|---|---|
| build | `powershell -File demo-targets\wpf-codeonly\build.ps1` | 0 | WpfDemo.exe 产出；theme.light.xaml 拷贝为 theme.xaml |
| detect | `reskin.py --json detect --target demo-targets\wpf-codeonly` | 0 | **framework=win32, confidence=low**（探测器未识别 code-only WPF，见 bug） |
| before 截图 | `shoot_win.py WpfDemo.exe before.png 'Reskinner WPF Demo'` | 0 | before.png 640×420，pw_ok=1 |
| plan 干跑 | `reskin.py --json plan --target <wpf> --skin <wpf-dark>` | 2 | dry-run，列出 replace_file(theme.xaml)，未写入 |
| apply 不带 --confirm | `cd <wpf>; reskin.py --json apply --target . --skin <wpf-dark>` | 2 | blocker 仅「low 需 --force」，未写入（theme.xaml 仍 #F5F5F0） |
| apply 确认 | `cd <wpf>; reskin.py --json apply --target . --skin <abs> --confirm --force` | 0 | theme.xaml 写入 387 字节暗色版（AppBg #0E1626），备份 `.reskin-backups\20261020-163138-wpf-dark` |
| after 截图 | `shoot_win.py ... after.png` | 0 | after.png |
| rollback | `reskin.py --json rollback --target .` | 0 | theme.xaml 还原，mismatches=[]，AppBg 回到 #F5F5F0 |
| restored 截图 | `shoot_win.py ... restored.png` | 0 | restored.png |

## 像素断言

- before 亮度 **237.57**（浅色）；after **51.36**（深暗，after/before=0.22）。
- after 通道 R=44.96 / G=51.86 / **B=65.54**，蓝色占优。
- restored 与 before **0 像素差异**（窗口内容字节级一致）。

## 合规说明（如实声明）

- 本靶场采用研究案例库记载的**外挂松散 ResourceDictionary** 合法路径：exe 启动时 `XamlReader.Parse` 加载同目录 `theme.xaml`，换肤=替换该文件。
- 真实成品 WPF 的样式编译为 BAML 内嵌资源，**无官方回编工具链**；工具箱对 BAML 保持只读 / `unsupported`，不做 IL 改写、不反编译重编译、不破坏强命名/Authenticode。

## 结论：SUCCESS

## 证据文件

- `before.png` / `after.png` / `restored.png`（PrintWindow 真实截图）
- `verify-report.json`；共享截图器 `..\shoot_win.py`；报告脚本 `make_report.py`
