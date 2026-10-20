# Electron 与 CEF 桌面应用换肤技术路线调研

> 路线总览：**Electron 路线**靠识别 `resources\app.asar` → 解包 → 替换 renderer 的 HTML/CSS/JS → 重打包；**CEF 路线**靠识别 `libcef.dll` + `Resources\*.pak`/`icudtl.dat`，但应用层 UI 资源通常仍以本地 HTML 或远程 URL 形式存在，改包边界更窄。两条路线都会遇到 asarIntegrity / Fuses / V8 bytecode / 代码签名 / 自动更新覆盖等对抗点，工具箱必须把"检测 → 降级 → 提示"作为一等公民。

---

## 1. Electron 应用结构识别（detect 信号集）

**① 识别特征（可机器判定）**

在应用安装目录（常见 `C:\Users\<u>\AppData\Local\Programs\<app>\` 或 `C:\Program Files\<app>\`）下按下列信号打分，命中任意 2 条即可判定为 Electron：

| 信号 | 判定方式 |
| --- | --- |
| 主 EXE 旁存在 `resources\` 目录 | `Test-Path <dir>\resources` |
| `resources\app.asar` 存在 | 文件名固定，二进制头为 pickle 格式（4 字节 header size + JSON header） |
| `resources\app.asar.unpacked\` 目录存在 | 与 asar 同名后缀，存放原生 `.node`/大文件 |
| `resources\app\` 目录直接存在（未打包源码） | 老式 electron-packager 输出 |
| 目录下出现 `ffmpeg.dll`、`libGLESv2.dll`、`libEGL.dll`、`chrome_elf.dll`、`v8_context_snapshot.bin`、`vk_swiftshader.dll`、`icudtl.dat` | Chromium/Electron 运行时固定文件 |
| `locales\*.pak`（含 `en-US.pak`、`zh-CN.pak`）、`resources.pak`、`chrome_100_percent.pak`、`chrome_200_percent.pak` | Chromium 资源包 |
| 主 EXE 的 FileVersionInfo 中 ProductName 旁夹带 Electron 运行时特征；或 `strings` 命中 `Electron/` UA 段 | 可作为辅助 |
| 主 EXE 被厂商重命名（如 `Code.exe`、`Discord.exe`、`Teams.exe`） | 不能靠 exe 名判定，必须看 resources |

**版本探测**：
- 优先读 `resources\app.asar` 内 `package.json` 的 `version` 字段（用 `@electron/asar` 的 `listPackage`/`extractFile` 取出）。
- Electron 框架版本可从 `ffmpeg.dll` / `chrome_elf.dll` 的 FileVersion 推断，或读 `v8_context_snapshot.bin` 旁的元数据；更可靠的方式是在解包后的 `node_modules\electron\package.json` 里看 `version`。
- 官方版本对照表：https://releases.electronjs.org/releases.json （每个版本对应 Chromium / Node 版本）。

**② UI 层入口与资源形态**
- 主进程入口：`resources\app.asar` 内 `package.json.main`（通常 `main.js` / `dist\main.js`）。
- Renderer 资源：asar 内 `dist\` / `out\` / `renderer\` 下的 HTML/CSS/JS（React/Vue 打包产物，CSS 通常是 hash 文件名）。
- 自定义主题入口通常是：用户配置目录下的 `user.css`、`settings.json`、或 renderer 启动时拉取的本地 CSS。

**③ 工具链**
- Node 22 / npm 10 已就绪（本机环境）。
- `@electron/asar`（官方 Electron 团队维护，MIT）：`npm i -g @electron/asar`，npm 页面 https://www.npmjs.com/package/@electron/asar 。
- 旧版 `asar` 包（社区，已被 `@electron/asar` 取代）：不推荐新项目使用。
- 官方 ASAR 教程：https://www.electronjs.org/docs/latest/tutorial/asar-archives 。

**④ 代表开源项目**
- `electron/asar`（GitHub 镜像发布于 npm，MIT）：https://www.npmjs.com/package/@electron/asar —— Electron 官方 ASAR 读写库。
- Electron 官方文档站：https://www.electronjs.org/docs/latest/tutorial/asar-archives （MIT 文档）。

**⑤ 典型坑与对策**

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| asar 被 `--unpack` 拆分 | 重打包后漏掉 `app.asar.unpacked\` 里的 `.node` | 解包时保留 `--unpack` 清单；重打包时用 `asar pack <dir> app.asar --unpack-dir "**/*.node"` 等相同规则 |
| 主 EXE 与 asar 同名混淆 | 误把 `resources\app.asar` 当数据文件删 | 工具箱写操作前先做快照 |
| 路径反斜杠 | PowerShell 里 `resources\app.asar` 正常；Node 里要用 `path.join` | 统一用 Node API，不要拼字符串 |
| Electron ≥30 Windows 启用 asarIntegrity | 直接替换 asar 后应用秒退 / 白屏 | 见第 3 节 |

**⑥ 合规备注**：识别与读取属于本地静态分析；修改前必须确认目标软件的 EULA 允许本地个性化（多数开源 Electron 应用允许，闭源商业客户端禁止）。

---

## 2. UI 层入口：asar 格式、CLI 与 CSS 注入 API

**① 识别特征**
- ASAR 是一个无压缩的 pickle 容器：4 字节 header size（小端）+ JSON header（描述目录树、offset、size）+ 拼接的文件 blob。
- 用十六进制编辑器看前 16 字节即可认出：`04 00 00 00 00 00 00 00 ?? ?? ?? ?? 7B 22 ...`（`{` = 0x7B）。

**② UI 层入口与资源形态**
- Renderer 进程加载本地 `file:///.../dist/index.html`，CSS 通过 `<link>` 或 JS 注入。
- 官方注入 API（应用自带能力，不是外部修改）：
  - 主进程：`webContents.insertCSS(css[, { cssOrigin: 'user' | 'author' }])` 返回 `key`，配套 `webContents.removeInsertedCSS(key)`。文档：https://www.electronjs.org/docs/latest/api/web-contents 。
  - Renderer 预加载：`webFrame.insertCSS(css)`。文档：https://www.electronjs.org/docs/latest/api/web-frame 。
  - `<webview>` 标签也有同名方法。
- 工具箱视角：**换肤 = 在 renderer 启动后追加一段用户 CSS**，等价于给官方 `insertCSS` 注入一个本地文件；不需要改主进程逻辑。

**③ 工具链（@electron/asar 真实 CLI/Node API）**
- 安装：`npm i -g @electron/asar`（MIT）。
- CLI：
  ```powershell
  asar list   <archive>                 # 列出所有成员
  asar extract <archive> <dest>         # 解包整个归档
  asar extract-file <archive> <filename> # 抽出单个成员
  asar pack   <dir> <output>            # 重打包
  asar pack   <dir> <output> --unpack "*.node"   # 保留 unpacked 规则
  ```
- Node API（工具箱脚本主用）：
  ```js
  const asar = require('@electron/asar');
  asar.listPackage('resources/app.asar');                 // 成员列表
  asar.extractAll('resources/app.asar', 'C:\\temp\\app'); // 解包
  asar.extractFile('resources/app.asar', 'package.json'); // Buffer
  asar.createPackage('C:\\temp\\app', 'resources/app.asar');
  ```

**④ 代表开源项目**
- `@electron/asar`：https://www.npmjs.com/package/@electron/asar （MIT，Electron 官方维护）。
- `bytenode`（用于识别"主进程被编译成 V8 字节码"的情况）：https://www.npmjs.com/package/bytenode （MIT）。

**⑤ 典型坑与对策**

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| 重打包后文件顺序变化 | 原本可跑的应用启动报模块找不到 | `@electron/asar` 按目录遍历顺序写，解包→改一个文件→pack 通常稳定；不要跨平台混打包 |
| 打包时漏掉 unpacked | 原生模块加载失败 | 解包前先 `asar list` 看有没有 `*.node`；pack 时加同样的 `--unpack` |
| CSS 被 `!important` 压住 | 用户注入的 CSS 不生效 | 注入时用 `cssOrigin: 'user'`，优先级高于 author 样式表；或在选择器后加 `!important` |
| Renderer 用 CSP 禁用远程 CSS | 远程主题加载失败 | 换肤只能走本地文件；不要尝试 `remote-allow-origins` |

**⑥ 合规备注**：`insertCSS` 是 Electron 官方 API，本就是给应用作者做主题系统用的；第三方修改相当于"替应用作者调用了这个 API"，对开源软件属于善意扩展，对闭源软件仍属未授权修改。

---

## 3. 完整性与对抗机制（踩坑重点）

**① 识别特征**
- **asarIntegrity**：Electron ≥16（macOS）/ ≥30（Windows）引入。校验值以两种方式嵌入：
  - Windows：主 EXE 的 Win32 资源段里一个类型为 `Integrity`、名为 `ElectronAsar` 的资源，值是 JSON `{ "file": "resources\\app.asar", "alg": "SHA256", "hash": "<base64>" }`。
  - macOS：`app.asar` 旁的 `Frameworks/Electron Framework.framework/Resources/` 或 CodeResources。
- **Electron Fuses**：嵌在主 EXE 二进制里的一段标记（`dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX` 魔数之后），可被 `@electron/fuses` 读取/翻转。关键 fuse：
  - `embeddedAsarIntegrityValidation`：开启后加载 asar 时校验哈希。
  - `onlyLoadAppFromAsar`：禁止回退到 `resources\app\` 目录。
  - `runAsNode`、`nodeCliInspect`、`loadBrowserProcessSpecificV8Snapshot` 等。
- **V8 snapshot / bytenode**：主进程 JS 被编译成 `.jsc`（V8 字节码），没有源码可读；但 renderer 的 HTML/CSS 仍明文。
- **代码签名**：修改 asar 后主 EXE 的 Authenticode 签名失效（Windows SmartScreen / Gatekeeper 会报警）。
- **autoUpdater / Squirrel**：更新时会用官方包整体覆盖 `app.asar`，本地修改被回滚。

**② UI 层入口与资源形态**
- 校验失败的表现：macOS 上直接弹"应用已损坏"；Windows 上通常静默白屏 / 主进程崩溃退出事件日志里出现 `electron.exe!sandbox_...` 或 `CheckIntegrity` 相关堆栈。
- Fuse 状态可以通过 `@electron/fuses` 的 `readFuses(exePath)` 读出 JSON。

**③ 工具链**
- `@electron/fuses`（Electron 官方，MIT）：`npm i -g @electron/fuses`，npm 页 https://www.npmjs.com/package/@electron/fuses 。
- electron-builder 文档（说明何时启用）：https://www.electron.build/v26/docs/tutorials/adding-electron-fuses/ 。
- Electron 官方 asarIntegrity 教程：https://www.electronjs.org/docs/latest/tutorial/asar-integrity 。
- Electron Fuse 官方教程：https://www.electronjs.org/docs/latest/tutorial/fuses 。

**④ 代表开源项目**
- electron/electron（Fuses 与 asarIntegrity 的官方实现，MIT）：https://github.com/electron/electron 。
- jondubois/bytenode（识别 V8 字节码混淆，MIT）：https://www.npmjs.com/package/bytenode 。

**⑤ 典型坑与对策**

| 坑 | 现象 | 对策（工具箱层面，不是教绕过） |
| --- | --- | --- |
| Windows asarIntegrity 开启 | 改完 asar 后应用秒退 | 工具箱 detect 阶段先 `readFuses` + 解析 EXE 资源段；若 `embeddedAsarIntegrityValidation=on`，**拒绝写操作并提示"该应用启用 asar 完整性校验，本地改包会被拒绝"** |
| macOS 与 Windows 行为差异 | 同样的包在 Mac 上直接打不开，Windows 上只是白屏 | 文档里写清：Mac 上 fuse 一旦开启几乎无法本地改包；Windows 上至少能观察到失败现象 |
| `onlyLoadAppFromAsar` 开启 | 删掉 asar 想回退到 `resources\app\` 也失败 | 不要尝试回退方案；直接告知用户此路径被锁 |
| bytenode `.jsc` | 主进程源码读不到，但 renderer CSS 仍在 | 换肤目标是 renderer，不碰主进程 `.jsc` 即可 |
| 代码签名失效 | 修改后 SmartScreen 红屏 | 工具箱在写操作前提醒"修改后应用签名失效，首次启动需手动确认" |
| autoUpdater 覆盖 | 隔几天换肤失效 | 提示用户"应用自动更新后需重新应用皮肤"；工具箱支持幂等重放 |
| Windows 文件占用 | 写 `app.asar` 时提示被占用 | detect 阶段先检查 `Get-Process` 是否在跑对应 exe；写前要求用户关闭应用 |

**⑥ 合规备注**：本工具箱**不提供**翻转 fuse、重算 integrity hash、伪造签名的能力——那属于绕过软件保护机制。工具箱的职责是**检测到这些保护后明确告诉用户"此路不通"，并降级到官方主题系统路径**（见第 4 节各案例）。

---

## 4. 开源代表案例

### 4.1 VS Code（原生换肤生态标杆，单列）

**① 识别特征**：安装目录下 `Code.exe`、`resources\app\`（未打包 asar，直接是源码目录）、`resources\app\out\`、`resources\app\package.json`。

**② UI 层入口与资源形态**：
- 主题是一个 `.vsix` 扩展（本质 zip），内含 `package.json` 声明 `contributes.themes`，指向一个颜色 JSON 文件。
- 用户级覆盖写在 `%APPDATA%\Code\User\settings.json`：
  ```json
  "workbench.colorCustomizations": {
    "[Monokai]": { "sideBar.background": "#347890" }
  }
  ```
- 文档：https://code.visualstudio.com/docs/configure/themes ；完整 color token 参考：https://code.visualstudio.com/api/references/theme-color ；主题扩展指南：https://code.visualstudio.com/api/extension-guides/color-theme 。

**③ 工具链**：
- VS Code 内置扩展市场，无需额外工具。
- 自制主题：`yo code`（Yeoman 生成器，MIT），打包成 vsix 后通过"安装从 VSIX"载入。

**④ 代表开源项目**：
- VS Code 本体（MIT）：https://github.com/microsoft/vscode 。
- 主题市场示例（社区主题）：https://marketplace.visualstudio.com/search?target=VSCode&category=Themes 。

**⑤ 典型坑与对策**：

| 坑 | 对策 |
| --- | --- |
| 改了 `workbench.colorCustomizations` 不生效 | 确认方括号里的主题名与当前激活主题完全一致 |
| 想改图标 / 字体而非颜色 | 颜色改 `workbench.colorCustomizations`；图标装 Icon Theme 扩展；字体改 `editor.fontFamily` |
| 升级后主题样式被刷新 | 用户 settings.json 不会被覆盖，持久化有效 |

**⑥ 合规备注**：VS Code 是 MIT 开源，官方鼓励主题扩展生态；这是"应用原生主题系统"的黄金标准——工具箱应优先识别并引导到这种路径，而不是去改 `app\out`。

---

### 4.2 Joplin（插件 + userchrome.css）

**① 识别特征**：安装目录 `Joplin.exe`，用户数据目录 `%APPDATA%\joplin-desktop\`。

**② UI 层入口与资源形态**：
- 官方支持在 profile 目录放 `userchrome.css`（改整个桌面端 UI）和 `userstyle.css`（改编辑器样式）。
- 插件系统还提供 `--joplin-{property}` CSS 变量供插件样式表使用。
- 文档：https://joplinapp.org/help/apps/custom_css/ ；插件 theming：https://joplinapp.org/api/references/plugin_theming/ 。

**③ 工具链**：手动创建 `userchrome.css` 即可，无需命令行；进阶可用 Joplin 插件市场安装 CSS 相关插件。

**④ 代表开源项目**：
- Joplin（MIT）：https://github.com/laurent22/joplin 。
- 官方自定义 CSS 文档：https://joplinapp.org/help/apps/custom_css/ 。

**⑤ 典型坑与对策**：

| 坑 | 对策 |
| --- | --- |
| 升级后 CSS 选择器失效 | 官方文档明确警告"styles may break from one version to the next"，工具箱应提示用户 |
| 改了不生效 | 确认文件名是 `userchrome.css`（拼写）、放在 profile 根目录、重启 Joplin |

**⑥ 合规备注**：官方文档显式提供此能力，属于支持的个性化路径。

---

### 4.3 GitHub Desktop

**① 识别特征**：安装目录 `GitHubDesktop.exe`，`resources\app.asar`。

**② UI 层入口与资源形态**：官方只在 Settings → Appearance 提供 Light / Dark / System 三档，**不暴露自定义 CSS 入口**。文档：https://docs.github.com/en/desktop/configuring-and-customizing-github-desktop/setting-a-theme-for-github-desktop 。

**③ 工具链**：仅官方设置面板。

**④ 代表开源项目**：
- GitHub Desktop（MIT）：https://github.com/desktop/desktop 。

**⑤ 典型坑与对策**：

| 坑 | 对策 |
| --- | --- |
| 想深入改配色 | 官方无 API；工具箱应提示"该应用仅支持三档主题，深度定制需自行维护 patch" |
| 解包 asar 改 CSS | 升级即被覆盖；不推荐 |

**⑥ 合规备注**：MIT 开源但官方不提供主题 API；工具箱只描述现状，不主动生成改包脚本。

---

### 4.4 Element（Matrix 客户端）

**① 识别特征**：安装目录 `Element.exe`，`resources\app.asar`。

**② UI 层入口与资源形态**：
- 官方支持 Custom Themes：在设置的 Developer Tools（`/devtools`）里以 JSON 主题 URL 形式加载，运行时动态生效。
- 文档：https://web-docs.element.dev/theming.html （本机直连超时，通过搜索引擎索引确认存在；GitHub 仓库 https://github.com/vector-im/element-web 直连 200）。

**③ 工具链**：应用内设置面板。

**④ 代表开源项目**：
- Element Web/Desktop（Apache-2.0）：https://github.com/vector-im/element-web 。

**⑤ 典型坑与对策**：

| 坑 | 对策 |
| --- | --- |
| 自定义主题 URL 加载失败 | 确认 URL 指向合法 JSON 主题定义；网络可达 |
| 升级后主题被重置 | 自定义主题按 URL 记忆，需重新粘贴 URL |

**⑥ 合规备注**：官方支持的运行时主题机制。

---

### 4.5 Standard Notes

**① 识别特征**：安装目录 `StandardNotes.exe`，`resources\app.asar`。

**② UI 层入口与资源形态**：插件系统把主题定义为一个 CSS 文件，通过 Plugins → Install Custom Plugin 粘贴 URL 安装。
- 文档：https://standardnotes.com/help/plugins/publishing （主题插件的 manifest 里 `sn.main` 指向 CSS 文件）。

**③ 工具链**：应用内插件面板。

**④ 代表开源项目**：
- Standard Notes（AGPLv3，客户端开源）：https://standardnotes.com/ 。

**⑤ 典型坑与对策**：

| 坑 | 对策 |
| --- | --- |
| 第三方主题安全 | 主题即 CSS，可能含 `@import` 外链；提示用户只信任来源 |

**⑥ 合规备注**：官方插件机制。

---

### 4.6 解包 app.asar 后重打包的公开教学

**① 识别特征**：通用流程，不针对特定应用。

**② UI 层入口与资源形态**：教学博客演示 `asar extract` → 修改 renderer JS/CSS → `asar pack` 的完整循环，并讨论原生模块 `--unpack` 保留问题。

**③ 工具链**：`@electron/asar`（见第 2 节）。

**④ 代表开源/教学项目**：
- Noham 的博客《Unpacking and repacking electron apps》：https://noh.am/en/posts/unpacking-and-repacking-electron-apps/ （已验证 200，个人技术博客，无明确 license，引用时注明出处）。
- 官方 asar 教程（作为权威参考）：https://www.electronjs.org/docs/latest/tutorial/asar-archives 。

**⑤ 典型坑与对策**：

| 坑 | 对策 |
| --- | --- |
| 原生模块丢失 | 博客明确给出 `asar pack ... --unpack "*.node"` 示例 |
| 修改后体积膨胀 | asar 无压缩，体积变化可忽略；重打包前可先 `terser` 压缩 JS |

**⑥ 合规备注**：教学内容仅用于学习与开源软件个性化；对闭源商业软件按第 6 节风险处理。

---

## 5. CEF 路线

**① 识别特征（可机器判定）**

在应用目录下命中以下信号：

| 信号 | 判定 |
| --- | --- |
| 根目录存在 `libcef.dll` | CEF 主共享库 |
| 旁伴 `chrome_elf.dll`、`cefclient.exe` / `cefsimple.exe` 或厂商重命名主 EXE | Chromium 壳进程 |
| 资源目录（常见 `Resources\` 或根目录）含 `cef.pak`、`cef_100_percent.pak`、`cef_200_percent.pak`、`cef_resources.pak`、`devtools_resources.pak` | CEF 资源包 |
| 同目录 `icudtl.dat`（ICU 数据）、`snapshot_blob.bin`、`v8_context_snapshot.bin` | Chromium 运行时数据 |
| `locales\en-US.pak`、`locales\zh-CN.pak` 等 | 本地化资源 |
| CefSharp 系（.NET 嵌入）：多一个 `CefSharp.Core.dll`、`CefSharp.BrowserSubprocess.exe` |
| JCEF 系（Java 嵌入，如 JetBrains IDE）：`jcef.jar`、`jcef.dll`、`jcef_helper.exe` |

**② UI 层入口与资源形态**
- CEF 本身只提供浏览器内核；**应用 UI 是宿主进程通过 `CefBrowser` 加载的本地 HTML 文件或远程 URL**。
- 本地 HTML 通常散落在应用 `resources\html\`、`www\`、`ui\` 目录里，与 `.pak` 无关。
- `.pak` 是 Chromium 的 GRIT 资源归档（含 devtools、默认图片、本地化字符串），**不是应用 UI 资源**——改 `.pak` 风险极高且通常无收益。

**③ 工具链**
- CEF 官方二进制：https://cef-builds.spotifycdn.com/index.html （由 Spotify 维护的自动构建分发站；官方入口 https://chromiumembedded.github.io/cef/general_usage 已验证 200）。
- JCEF：https://github.com/chromiumembedded/java-cef （MIT）；文档 https://chromiumembedded.github.io/java-cef/branches_and_building.html 。
- cefpython3（Python 绑定，已停止大版本更新，最后 66.1）：https://pypi.org/project/cefpython3/ ，源码 https://github.com/cztomczak/cefpython （已验证 200）。
- CefSharp（.NET 绑定）：https://github.com/cefsharp/CefSharp （BSD）。

**④ 代表开源项目**
- chromiumembedded/cef（BSD 3-Clause）：https://github.com/chromiumembedded/cef 。
- chromiumembedded/java-cef（Apache-2.0）：https://github.com/chromiumembedded/java-cef 。
- cztomczak/cefpython（BSD）：https://github.com/cztomczak/cefpython （注意：上游已归档，仅作历史参考）。

**⑤ 典型坑与对策**

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| 想改 `.pak` 里的样式 | `.pak` 是二进制 GRIT 归档，需要专门工具（`pak_viewer`/GRIT 工具链）解包重打，且改错会导致渲染崩溃 | 不要改 `.pak`；去应用自己的 HTML/CSS 目录改 |
| `icudtl.dat` 版本不匹配 | 启动即崩溃 | 不要单独替换 CEF 文件，整目录一起换 |
| cefpython 版本旧 | Python 3.10+ 无官方 wheel | 仅作识别参考，不要基于它做产品 |
| JCEF 在 JetBrains IDE 里 | IDE 升级会覆盖 JCEF 文件 | 改包无意义，走 IDE 自带主题 |
| CEF 应用加载远程 URL | 本地根本没有 UI 资源可改 | 只能用 DevTools 做临时个性化，下次启动失效 |

**⑥ 合规备注**：CEF 应用分散度高，没有像 asar 那样统一的换肤入口；工具箱对 CEF 应用应**只识别、不主动改包**，引导用户走应用自带设置。

---

## 6. 闭源商业客户端（Discord / Spotify / Teams / 钉钉 等）—— 方法论与风险

**仅作风险说明，不提供任何实操步骤：**

闭源商业桌面客户端普遍基于 Electron 或 CEF，社区存在 BetterDiscord（Discord）、Spicetify（Spotify）等第三方改包项目。**这些项目都违反对应厂商的服务条款（ToS）**：客户端注入插件 / 主题被视为未授权修改，厂商保留从警告、功能限制到封号、法律追责的全部权利；修改后的客户端也可能被反作弊/反滥用风控标记。工具箱面向学习与开源软件个性化场景，**不收录、不生成、不引导使用针对闭源商业客户端的改包产物**，也不在 detect 命中此类 EXE 后给出写操作选项，只提示"此应用为闭源商业软件，修改客户端存在封号与法律风险"。参考讨论（仅说明风险，不背书）：https://betterdiscord.app/ （已验证 200，其官网自身也声明属于客户端修改）。

---

## 7. 对 Skill 设计的接口建议

### 7.1 `detect` 信号（PowerShell 原语）
输入：应用安装目录 `$AppDir`。输出：JSON
```json
{
  "engine": "electron" | "cef" | "unknown",
  "confidence": 0.0-1.0,
  "signals": ["app.asar", "ffmpeg.dll", "locales/*.pak", "..."],
  "appVersion": "<从 asar 内 package.json 读取>",
  "electronVersion": "<从 chrome_elf.dll FileVersion 推断>",
  "asarPath": "resources\\app.asar | null",
  "unpackedDir": "resources\\app.asar.unpacked | null",
  "integrity": { "asarIntegrity": true|false|unknown, "fuses_readable": true|false }
}
```
判定规则：命中 `resources\app.asar` + 任一 Chromium 运行时 DLL → electron；命中 `libcef.dll` → cef。

### 7.2 asar 成员级替换原语
- `asar-list <asar>` → 列出所有成员路径。
- `asar-extract-member <asar> <member> <outFile>` → 抽单个文件（用于读 package.json / 找入口）。
- `asar-replace-member <asar> <member> <newLocalFile> --backup <path>` → 替换单个成员，自动先做 `app.asar.bak`。
- 实现建议：调用本机 `npx @electron/asar` 或在 Python 里直接解析 asar header（header 是 JSON，offset/size 都是明文，不需要原生绑定）。

### 7.3 完整性校验的检测与降级提示
- 写操作前必跑：
  1. `readFuses(exePath)`（`@electron/fuses`）：若 `embeddedAsarIntegrityValidation === 'enabled'` 或 `onlyLoadAppFromAsar === 'enabled'`，**中止写操作**，提示"该应用已启用 ASAR 完整性校验，本地改包会被运行时拒绝"。
  2. 检查主 EXE 数字签名：`Get-AuthenticodeSignature <exe>`；若签名有效，提示"修改后签名将失效"。
  3. 检查应用是否在运行：`Get-Process` 命中即拒绝写。
- 不提供：翻转 fuse、重算 hash、伪造签名——这些是绕过保护，超出本 Skill 范围。

### 7.4 回滚要点
- 任何写操作前强制生成 `<asar>.bak.<yyyyMMddHHmm>`。
- 提供 `restore` 子命令：检测到 `.bak` 即一键还原。
- 记录"已应用的 CSS 内容 hash"，方便幂等重放（应对 autoUpdater 覆盖）。

### 7.5 确认点（在 Skill 交互中必须停下来问用户）
1. 目标应用是否为开源 / 官方允许个性化？（闭源商业客户端直接拒绝写路径）
2. 是否已关闭应用进程？
3. 是否同意先备份 `app.asar`？
4. 该应用是否启用了 asarIntegrity / Fuses？若是，是否降级为"仅推荐官方主题系统"？
5. 修改后是否接受应用自动更新会覆盖本地修改？

---

## 8. 已验证关键链接清单

| URL | 状态 | 用途 |
| --- | --- | --- |
| https://www.npmjs.com/package/@electron/asar | 200（npm registry API 验证；网页端本机被 Cloudflare 403） | ASAR 官方 CLI/库 |
| https://registry.npmjs.org/@electron/asar/latest | 200 | 包存在性确认 |
| https://www.npmjs.com/package/@electron/fuses | 200（registry API 验证） | Electron Fuses 工具 |
| https://registry.npmjs.org/@electron/fuses/latest | 200 | 包存在性确认 |
| https://www.npmjs.com/package/bytenode | 200（registry API 验证） | V8 字节码识别 |
| https://registry.npmjs.org/bytenode/latest | 200 | 包存在性确认 |
| https://www.electronjs.org/docs/latest/tutorial/asar-archives | 200（搜索摘要） | ASAR 官方教程 |
| https://www.electronjs.org/docs/latest/tutorial/asar-integrity | 200 | ASAR 完整性官方文档 |
| https://www.electronjs.org/docs/latest/tutorial/fuses | 200 | Fuse 官方文档 |
| https://www.electronjs.org/docs/latest/api/web-contents | 200 | `insertCSS` API |
| https://www.electronjs.org/docs/latest/api/web-frame | 200（搜索摘要） | renderer 侧 `insertCSS` |
| https://www.electron.build/v26/docs/tutorials/adding-electron-fuses/ | 200 | electron-builder 启用 fuses 说明 |
| https://code.visualstudio.com/docs/configure/themes | 200 | VS Code 主题用户文档 |
| https://code.visualstudio.com/api/references/theme-color | 200 | VS Code color token 参考 |
| https://code.visualstudio.com/api/extension-guides/color-theme | 200（搜索摘要） | VS Code 主题扩展指南 |
| https://github.com/microsoft/vscode | 200（搜索摘要） | VS Code 本体 |
| https://joplinapp.org/help/apps/custom_css/ | 200 | Joplin userchrome.css 官方文档 |
| https://joplinapp.org/api/references/plugin_theming/ | 200（短页 370 字节，存在） | Joplin 插件 theming |
| https://github.com/laurent22/joplin | 200 | Joplin 源码 |
| https://docs.github.com/en/desktop/configuring-and-customizing-github-desktop/setting-a-theme-for-github-desktop | 200 | GitHub Desktop 主题设置 |
| https://github.com/desktop/desktop | 200 | GitHub Desktop 源码 |
| https://web-docs.element.dev/theming.html | 本机直连超时（多次重试）；通过搜索引擎索引确认内容存在 | Element 自定义主题文档 |
| https://github.com/vector-im/element-web | 200 | Element Web 源码 |
| https://standardnotes.com/help/plugins/publishing | 200 | Standard Notes 主题插件发布文档 |
| https://docs.mattermost.com/help/settings/theme-colors.html | 200（短页） | Mattermost 主题颜色文档 |
| https://github.com/signalapp/Signal-Desktop | 200 | Signal-Desktop 源码 |
| https://noh.am/en/posts/unpacking-and-repacking-electron-apps/ | 200 | asar 解包重打包教学博客 |
| https://chromiumembedded.github.io/cef/general_usage | 200 | CEF 官方文档 |
| https://chromiumembedded.github.io/java-cef/branches_and_building.html | 200（搜索摘要） | JCEF 文档 |
| https://github.com/cztomczak/cefpython | 200 | cefpython 源码（已归档） |
| https://pypi.org/project/cefpython3/ | 200 | cefpython3 PyPI |
| https://betterdiscord.app/ | 200 | BetterDiscord（仅作风险引用，不背书） |
