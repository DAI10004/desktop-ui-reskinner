# Electron 路线速查

## 识别
- 信号：`resources/app.asar`、`resources/app.asar.unpacked`、`resources/app\`（未打包）、`ffmpeg.dll`、`chrome_elf.dll`、`libGLESv2.dll`、`locales/*.pak`、`chrome_100/200_percent.pak`。
- 重命名的主 exe（Code.exe/Discord.exe 等）不能靠名字判定，必须看 resources。

## UI 层入口
- asar 内 `dist/`、`out/`、`renderer/` 下的 HTML/CSS/JS → 用 `asar_replace` 替换 CSS。
- `resources/app\` 未打包目录（VS Code 式）→ 直接 `replace_file`。
- 官方运行时入口：`webContents.insertCSS()`——本工具箱不改主进程，等价于替应用作者调它。

## 命令示例
```bash
python scripts/reskin.py --json detect --target "C:\Users\x\AppData\Local\Programs\App"
# 先列 asar 成员，确认 member 路径：
node scripts/asar_pack.js list "C:\...\resources\app.asar"
python scripts/reskin.py --json apply --target ... --skin templates/electron --confirm
```

## 坑
- **Electron ≥30 Windows 启用 asarIntegrity / Fuses**：直接替换 asar 后秒退/白屏。detect 命中 `asar_integrity` 会**拒写**——不提供翻 fuse/重算 hash，引导到官方主题系统。
- `--unpack` 原生模块（`.node`）：重打包要保留 unpacked 规则，否则加载失败。
- 升级被 autoUpdater 整体覆盖：皮肤失效，重新 apply 即可。
- 代码签名失效：首次启动 SmartScreen 红屏，提前告知用户。
- CSS 被 `!important` 压住：换肤包 CSS 里也加 `!important`。

## 合规
- 识别/读取属本地静态分析；修改前确认 EULA 允许本地个性化。
- 闭源商业客户端（Discord/Spotify 等）的 BetterDiscord/Spicetify 类改包违反 ToS，本工具箱不做。
