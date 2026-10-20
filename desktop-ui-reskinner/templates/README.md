# 换肤包字段说明（每个字段必须这样填）

换肤包 = 一个目录，至少含 `skin.json` + `assets/`。`reskin.py plan/apply` 只认这个结构。

## skin.json 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `manifest_version` | 是 | 固定 `1` |
| `name` | 是 | 皮肤名（英文短名，也是备份目录名后缀） |
| `framework` | 是 | `qt` / `electron` / `cef` / `wpf` / `winforms` / `win32` |
| `version` | 是 | 语义化版本号 |
| `author` | 否 | 作者 |
| `description` | 否 | 一句话说明 |
| `target_match` | 是 | 目标校验，见下 |
| `ops` | 是 | 操作数组，见下 |

## target_match

- `signals_all`：detect 输出里必须全部出现的信号名（如 `qt6core-dll`）。
- `files_any`：目标目录里**任意一个**存在的相对文件路径。两者都不满足会被 plan 拒绝。

## ops（顺序执行）

| op | 字段 | 说明 |
|---|---|---|
| `replace_file` | `src`（包内）、`dst`（目标内相对路径）、`backup` | 整文件替换；dst 越出目标根一律拒绝 |
| `patch_text` | `file`、`find`、`replace`、`must_match`、`encoding`、`backup` | 精确串替换；命中次数 != must_match 立即中止并回滚；encoding 仅 `utf-8` 或 `utf-8-sig`（默认 utf-8，不写 BOM） |
| `asar_replace` | `archive`、`member`、`src`、`backup` | 成员级替换进 asar；依赖 node + @electron/asar，缺失返回结构化 unsupported |
| `pe_resource` | `image`、`restype`、`resname`、`lang`、`src`、`backup` | 经 Resource Hacker 改 exe 资源；缺 ResourceHacker.exe 返回 unsupported |

- `backup` 默认 true；为 true 的目标 apply 前必须存在于备份清单。
- 禁止原语：进程注入、DLL 写入、注册表启动项、exe 字节补丁、授权校验修改——写了 plan 会拒绝。

## 目录骨架示例

```
my-skin/
├─ skin.json
├─ README.md（本说明）
└─ assets/
   ├─ style.qss
   └─ theme.css
```
