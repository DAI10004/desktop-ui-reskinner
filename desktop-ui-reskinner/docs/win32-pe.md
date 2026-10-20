# Win32 原生 PE 路线速查

## 识别
- 兜底框架：目录里只有 exe/dll、没有 Qt/Electron/CEF/.NET 信号 → `win32`，置信度 low，apply 需 `--force`。
- PE 资源段：RT_DIALOG/RT_MENU/RT_STRING/RT_BITMAP/RT_ICON/RT_MANIFEST。
- 标杆案例：Notepad++（`notepad++.exe`）——但它的换肤走**配置文件层**（`stylers.xml`/`Themes/*.xml`），不改 exe。

## UI 层入口（两层，边界要清楚）
- **PE 资源段**：改布局/菜单/文案/图标 → 用 Resource Hacker CLI（`pe_resource` 原语）。
- **配置文件层**（Notepad++ 式）：XML 主题丢进 Themes 目录重启生效，**这是更安全的首选**。
- UxTheme/msstyles、DWM 暗色 API：只决定标题栏/系统控件外观，改不了自绘客户区。

## 命令示例
```bash
python scripts/reskin.py --json detect --target "C:\Program Files\App"
# pe_resource 需要 ResourceHacker.exe；缺失时 apply 返回结构化 unsupported + 安装指引。
python scripts/reskin.py --json apply --target ... --skin templates/win32 --confirm --force
```

## 坑
- 改完 exe 起不来/被杀软拦：重写 PE 破坏签名，只在自有/靶场 exe 上玩。
- 加壳程序：Resource Hacker 打开乱码/空资源，官方不脱壳，放弃资源路线。
- 改对话框颜色无效：颜色在代码 `WM_CTLCOLORDLG` 里画，资源段存不了颜色。
- 第三方 msstyles patch uxtheme：**不做**，系统会崩。

## 合规
- Resource Hacker 授权条款禁止非法修改软件；只对自有/开源/官方允许自定义资源的程序操作。
- 不碰微信/QQ 等闭源商业软件 exe 资源段（即使只改图标）。
