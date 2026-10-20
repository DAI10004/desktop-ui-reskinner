# 03 · 发布到 GitHub 指南

本仓库目前已完成**本地 git 初始化**（分支 `main`），但**尚未配置任何远端**——创建 GitHub 仓库、提供账号凭据与推送动作由你本人完成。以下步骤在 Windows PowerShell / Git Bash 均可执行。

## 1. 发布前检查

```powershell
cd E:\逆向桌面级软件自定义UI

# 大体积/运行时产物应已被 .gitignore 排除（.venv/、.tools/、electron-demo/App/、*.exe、.reskin-backups/）
git status --short
git check-ignore .venv .tools "demo-targets/electron-demo/App"   # 应逐行回显，说明已忽略
```

确认将要提交的只有源码、文档、模板、换肤包、验证截图与报告，不含 venv、node_modules、Electron 运行时或备份目录。

## 2. 配置提交身份（如尚未配置）

```powershell
# 查看
git config --global user.name
git config --global user.email

# 全局配置（一次配置，所有仓库生效）
git config --global user.name  "你的 GitHub 用户名或昵称"
git config --global user.email "你的邮箱"

# 或只对本仓库配置
git config user.name  "你的 GitHub 用户名或昵称"
git config user.email "你的邮箱"
```

## 3. 首次提交

```powershell
git add -A
git commit -m "feat: desktop-ui-reskinner skill - 桌面软件通用换肤工具箱（Qt/Electron/WPF 靶场验证）"
git branch -M main
```

> 本地仓库已在项目目录初始化；若你在别的机器上从零开始，先执行 `git init -b main`。

## 4. 在 GitHub 上创建空仓库

1. 打开 <https://github.com/new>；
2. Repository name 建议用 `desktop-ui-reskinner`；
3. 选择 **Public**（开源）；
4. **不要**勾选 “Add a README file”、“.gitignore”、“license”——本地已含这些文件，保持空仓库以避免无关合并；
5. 点击 Create repository。

## 5. 关联远端并推送

```powershell
# 把 <你的用户名> 换成实际 GitHub 用户名
git remote add origin https://github.com/<你的用户名>/desktop-ui-reskinner.git
git push -u origin main
```

认证说明：

- Windows 推荐安装 **Git Credential Manager**（Git for Windows 自带），首次 push 会弹出浏览器登录，按提示授权即可，凭据自动保存；
- 或使用 **Personal AccessToken**（GitHub → Settings → Developer settings → Tokens，勾 `repo` 权限），在用户名/密码提示处粘贴 token（密码位置填 token，而非账号密码）；
- 也可改用 SSH 远端：`git remote add origin git@github.com:<你的用户名>/desktop-ui-reskinner.git`（需先在 GitHub 配置 SSH key）。

## 6. 推送后建议

- 仓库主页会自动渲染 `README.md`（含 mermaid 流程图与效果图对照）；
- 在 GitHub 仓库 **About → ⚙ → Topics** 中添加 `qt`、`electron`、`wpf`、`theming`、`ai-agent`、`skill`、`windows` 等标签，便于被检索；
- 可选：用 GitHub Pages 发布 `docs/` 系列文章（Settings → Pages → 选择分支/目录），或在知乎、掘金发布导读文章并链接回仓库——文章应以仓库 README 为准，避免双份维护。

## 7. 后续更新流程

```powershell
git add -A
git commit -m "docs: 更新说明"
git push
```

> 安全提醒：不要把任何闭源商业软件的修改产物、安装包、截图中涉及他人版权的素材提交进仓库；本仓库定位始终是**工具箱 + 自建靶场 + 方法论**，合规边界见 [../DISCLAIMER.md](../DISCLAIMER.md)。
