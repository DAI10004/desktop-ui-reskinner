# Electron 演示靶场

最小 Electron 应用，作为 desktop-ui-reskinner 的 Electron / asar 路线验证靶场。

## 结构

- `app-src/`：源码（package.json / main.js / index.html / dist/styles/theme.css）。
- `build.ps1`：把 `.tools/electron-deps/node_modules/electron/dist` 整体复制为 `App/`，
  再用 `@electron/asar` 把 `app-src` 打包成 `App/resources/app.asar`。
- `App/`：构建产物（可重复重建，大体积目录，后续由 .gitignore 排除）。

## 构建（幂等）

```powershell
# 前置一次（已在 .tools/electron-deps 装好依赖时可跳过）：
#   cd .tools\electron-deps
#   $env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'
#   npm install electron @electron/asar --registry=https://registry.npmmirror.com
powershell -ExecutionPolicy Bypass -File demo-targets\electron-demo\build.ps1
```

## 运行

```powershell
.\demo-targets\electron-demo\App\electron.exe
```

- 窗口标题：`Reskinner Electron Demo`，800x600。
- 浅色主题来自 `dist/styles/theme.css`（打包在 app.asar 内）。

配套换肤包：`examples/skin-packs/electron-dark/`（`asar_replace` 替换 app.asar 内的 `dist/styles/theme.css`）。
