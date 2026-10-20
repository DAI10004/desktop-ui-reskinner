# desktop-ui-reskinner 自测报告

- 测试时间：2026-10-20
- 环境：Windows 11 / PowerShell 5.1 / Python 3.13.16 / Node v22.23.2
- 运行方式：`powershell -ExecutionPolicy Bypass -File tests\run-tests.ps1`
- 结果：**31 / 31 通过，0 失败**

## 一、夹具自测（run-tests.ps1）

| # | 用例 | 命令 | 结果 |
|---|---|---|---|
| 0 | 夹具重建 | `python tests\build_fixtures.py` | PASS |
| 1a | detect fake-qt | `python scripts\reskin.py --json detect --target tests\fixtures\fake-qt` | PASS：framework=qt, high |
| 1b | detect fake-electron | 同上 | PASS：framework=electron, high |
| 1c | detect fake-wpf | 同上 | PASS：framework=wpf, medium |
| 2a | plan 无 --confirm 退出码 2 | `--json plan --target ... --skin ...` | PASS：exit=2, mode=dry-run |
| 2b | plan 不写入 | 检查 config.ini 前后一致 | PASS |
| 3a | apply --confirm | `--json apply ... --confirm` | PASS：exit=0, mode=applied |
| 3b | qss 落盘深色 | 检查 `#1e1e1e` | PASS |
| 3c | patch_text 命中 | config.ini theme=dark | PASS |
| 4a | verify | `--json verify --target ...` | PASS：两文件 status=changed |
| 4b | verify-report.json 生成 | 检查 report_path | PASS |
| 5a | rollback | `--json rollback` | PASS：exit=0, mismatches=[] |
| 5b | 还原断言 | qss 回 `#ffffff`、config.ini 回 light | PASS |
| 6a | asar_replace 端到端 | apply electron-dark 皮肤 | PASS：exit=0 |
| 6b | 成员替换验证 | `node scripts\asar_pack.js extract-member ... dist/styles/theme.css` | PASS：内容为深色 `#111111` |
| 6c | 其余成员不变 | extract package.json | PASS：`"name": "fake-app"` |
| 7a | dst 越界 `../evil.qss` 拒绝 | apply bad-escape | PASS：exit=2, 越界文件未落盘 |
| 8a | must_match 不符中止 | apply bad-patch（期望 2 次实际 1 次） | PASS：mode=rolled-back |
| 8b | 已完成 op 自动回滚 | rollback_mismatches=[]，qss 回浅色 | PASS |
| 9 | pe_resource 缺工具 | apply win32-synth（本机无 ResourceHacker） | PASS：unsupported.code=RESOURCE_HACKER_MISSING + install_hint |
| 10a | Bug1 回归：从 tests 目录 CWD 执行 apply | `Push-Location tests; apply ...` | PASS：成功落盘 |
| 10b | Bug1 回归：qss 落盘正确 | 检查 `#1e1e1e` | PASS |

## 二、真实靶场 detect 实测（2026-10-20 修复后）

从任意 CWD（实测 `C:\Users\24425`）执行：

```
python scripts\reskin.py --json detect --target <靶场>
```

| 靶场 | framework | confidence | 命中信号 |
|---|---|---|---|
| demo-targets\qt-pyside6 | **qt** | **medium** | external-qss=0.3, py-qt-import=0.6 |
| demo-targets\wpf-codeonly | **wpf** | **medium** | dotnet-presentationframework-str=0.8, dotnet-presentationcore-str=0.4 |
| demo-targets\electron-demo | **electron** | **high** | ffmpeg.dll=0.4, v8_context_snapshot.bin=0.4, vk_swiftshader.dll=0.4, chromium-locales=0.3, chrome-pak=0.3 |

关键实测 JSON 摘要：

```json
// qt-pyside6
{"framework":"qt","confidence":"medium",
 "signals":[{"name":"py-qt-import","found":"main.py","weight":0.6},
             {"name":"external-qss","found":"skins/style.qss","weight":0.3}]}

// wpf-codeonly
{"framework":"wpf","confidence":"medium",
 "signals":[{"name":"dotnet-presentationframework-str","found":"WpfDemo.exe","weight":0.8},
            {"name":"dotnet-presentationcore-str","weight":0.4}]}

// electron-demo
{"framework":"electron","confidence":"high","signals":[...合计 1.8...]}
```

## 三、修复记录（第二轮）

1. **Bug 1（路径按 CWD 解析）**：新增 `norm_target()`，detect/backup/plan/apply/rollback/verify 全部入口先把 `--target` 规范化为绝对目录；`load_skin` 的 `_dir` 也改为 abspath。所有 manifest 相对路径一律 `os.path.join(绝对root, rel)`，与 CWD 无关。回归用例 #10 从 tests 目录 CWD 执行 apply 成功。
2. **Bug 2a（Qt 源码形态漏检）**：detect 新增扫描 target 内 `*.py` 头 256KB，正则 `^\s*(from|import)\s+(PySide6|PySide2|PyQt5|PyQt6)` → 信号 `py-qt-import`（权重 0.6）；`requirements.txt` 含对应包 → `requirements-qt`（0.3）。
3. **Bug 2b（code-only WPF 误判 win32）**：detect 对 target 内 exe/dll（≤32MB，读前 8MB）做 ASCII 字节串搜索：`PresentationFramework`→wpf 0.8；`PresentationCore`→wpf 0.4；`System.Windows.Forms`→winforms 0.7。

## 四、已知限制

- `asar_pack.js` 依赖 `@electron/asar` v4（ESM-only），本机已装于 `.tools/asar`；换机器需按 SKILL.md 一键命令准备。
- `pe_resource` 本机无 ResourceHacker，仅验证到 unsupported 路径，真实改资源未端到端测。
- 截图（verify --screenshot）未在本套件覆盖；PySide6 路径可用，ctypes 回退落 BMP。
- 真实 .NET 程序集的强命名/Authenticode 守卫在非签名靶场上只验证了容错分支。
- 基线 hash 守卫设计如此：apply 过一次皮肤后，再 apply 另一份皮肤会因"文件自上次备份后变化"被阻断，需先 rollback——这是防覆盖用户/更新文件的有意行为。
