# CEF 路线速查

## 识别
- 信号：根目录 `libcef.dll`、`cef.pak`/`cef_100_percent.pak`/`cef_resources.pak`、`icudtl.dat`、`snapshot_blob.bin`、`locales/*.pak`。
- CefSharp（.NET 嵌入）：多 `CefSharp.Core.dll`、`CefSharp.BrowserSubprocess.exe`。
- JCEF（Java 嵌入，JetBrains IDE）：`jcef.jar`/`jcef.dll`。

## UI 层入口
- CEF 只是浏览器内核；应用 UI 是宿主加载的**本地 HTML 文件或远程 URL**。
- `.pak` 是 Chromium GRIT 归档（devtools/默认图/本地化），**不是应用 UI**，改它风险极高无收益。
- 本地 HTML 通常在 `resources/html/`、`www/`、`ui/` 目录。

## 工具箱立场
- v1 **只识别、不主动改包**。detect 到 CEF 应用后引导用户看应用自带设置。
- 加载远程 URL 的应用：本地根本没有 UI 资源可改。
- JetBrains IDE 走 JCEF，但升级会覆盖，应走 IDE 官方主题市场。

## 坑
- 想改 `.pak` 里的样式 → 需要 pak_viewer/GRIT 工具链，改错渲染崩溃，**不做**。
- `icudtl.dat` 版本不匹配启动即崩；不要单独替换 CEF 文件。
- cefpython3 已停更（最后 66.1），Python 3.10+ 无 wheel，仅作识别参考。

## 合规
- CEF 应用分散度高，没有 asar 那样统一的换肤入口；默认走应用自带主题机制。
