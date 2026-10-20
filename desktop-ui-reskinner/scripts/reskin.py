#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reskin.py — desktop-ui-reskinner 唯一 CLI 入口

子命令: detect / backup / plan / apply / rollback / verify
约定:
  * --json 时 stdout 只输出一个 JSON 对象, 日志走 stderr;
  * 退出码: 0 成功; 2 安全约定「需要 --confirm / 存在阻断项, 未写入」; 其它非 0 错误;
  * 除截图与 asar 外仅用标准库, 兼容 Python 3.9+;
  * 面向用户/Agent 的输出文字一律中文。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime

TOOL_NAME = "desktop-ui-reskinner"
BACKUP_DIRNAME = ".reskin-backups"
MANIFEST_VERSION = 1

# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def log(msg):
    """普通日志一律走 stderr, 保证 stdout 干净。"""
    print(msg, file=sys.stderr)


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def relpath_safe(rel, root):
    """将 rel 视为相对 root 的路径; 越出 root 返回 None, 否则返回以 / 分隔的相对路径。"""
    try:
        child = os.path.normpath(os.path.abspath(os.path.join(root, rel)))
        r = os.path.normpath(os.path.abspath(root))
    except (ValueError, TypeError):
        return None
    if child != r and not child.startswith(r + os.sep):
        return None
    return os.path.relpath(child, r).replace(os.sep, "/")


def is_within(child, root):
    """child 是否位于 root 之内(含 root 本身)。"""
    try:
        c = os.path.normpath(os.path.abspath(child))
        r = os.path.normpath(os.path.abspath(root))
        return c == r or c.startswith(r + os.sep)
    except (ValueError, TypeError):
        return False


def now_ts():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def norm_target(t):
    """把 --target 统一规范化为绝对目录路径; 与 CWD 无关。"""
    t = os.path.abspath(t)
    if os.path.isfile(t):
        t = os.path.dirname(t)
    return os.path.normpath(t)


def list_exe_files(root):
    out = []
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if os.path.isfile(p) and name.lower().endswith(".exe"):
            out.append(p)
    return out


def pick_main_exe(target):
    if os.path.isfile(target):
        return target
    exes = list_exe_files(target)
    if not exes:
        return None
    # 优先与目录同名的 exe, 否则取体积最大者
    base = os.path.basename(os.path.normpath(target)).lower()
    for e in exes:
        if os.path.splitext(os.path.basename(e))[0].lower() == base:
            return e
    return max(exes, key=lambda p: os.path.getsize(p))


# ---------------------------------------------------------------------------
# 检测器
# ---------------------------------------------------------------------------

# 每条信号: (信号名, 命中的相对路径 glob 模式列表, 框架, 权重)
# glob 仅用相对路径的简单后缀/包含判断, 不引第三方库。

def _walk_files(root, max_depth=4):
    """浅层遍历目标目录, 返回所有文件相对路径(用 / 分隔)。"""
    collected = []
    root = os.path.normpath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirnames[:] = []
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            r = os.path.relpath(full, root)
            collected.append(r.replace(os.sep, "/"))
    return collected


def detect_framework(root):
    """返回 (signals列表, per-framework 加权分, ui_entry_points)。"""
    files = _walk_files(root)
    fileset = set(files)
    lower_files = {f.lower(): f for f in files}

    signals = []  # {name, found, weight, framework}
    scores = {}

    def hit(name, found, framework, weight):
        signals.append({
            "name": name,
            "found": found,
            "weight": weight,
            "_fw": framework,
        })
        scores[framework] = scores.get(framework, 0.0) + weight

    def find(pred):
        for lf, orig in lower_files.items():
            if pred(lf):
                return orig
        return None

    # ---- Qt ----
    q = find(lambda p: p.endswith("/qt6core.dll") or p.split("/")[-1] == "qt6core.dll")
    if q:
        hit("qt6core-dll", q, "qt", 0.9)
    q = find(lambda p: p.endswith("/qt5core.dll") or p.split("/")[-1] == "qt5core.dll")
    if q:
        hit("qt5core-dll", q, "qt", 0.9)
    for pkg in ("pyqt5", "pyside2", "pyqt6", "pyside6"):
        q = find(lambda p, pk=pkg: ("/" + pk + "/") in ("/" + p) or p.startswith(pk + "/"))
        if q:
            hit(pkg + "-dir", q, "qt", 0.8)
            break
    q = find(lambda p: p.endswith("platforms/qwindows.dll"))
    if q:
        hit("qwindows-plugin", q, "qt", 0.7)
    qss_files = [f for f in fileset if f.lower().endswith(".qss")]
    if qss_files:
        hit("external-qss", qss_files[0], "qt", 0.3)
    rcc_files = [f for f in fileset if f.lower().endswith(".rcc")]
    if rcc_files:
        hit("external-rcc", rcc_files[0], "qt", 0.4)

    # ---- Electron ----
    if "resources/app.asar" in lower_files:
        hit("app-asar", "resources/app.asar", "electron", 0.95)
    if "resources/app.asar.unpacked" in lower_files or any(
        f.startswith("resources/app.asar.unpacked/") for f in fileset
    ):
        hit("app-asar-unpacked", "resources/app.asar.unpacked", "electron", 0.6)
    if "resources/app" in [f.rstrip("/") for f in fileset]:
        hit("resources-app-dir", "resources/app", "electron", 0.5)
    for dll in ("ffmpeg.dll", "chrome_elf.dll", "libegl.dll", "libglesv2.dll",
                 "v8_context_snapshot.bin", "vk_swiftshader.dll"):
        q = find(lambda p, d=dll: p.split("/")[-1] == d)
        if q:
            hit(dll, q, "electron", 0.4)
    q = find(lambda p: p.endswith("/locales/en-us.pak") or p.endswith("/locales/zh-cn.pak"))
    if q:
        hit("chromium-locales", q, "electron", 0.3)
    q = find(lambda p: p.split("/")[-1] in ("chrome_100_percent.pak", "chrome_200_percent.pak"))
    if q:
        hit("chrome-pak", q, "electron", 0.3)

    # ---- CEF ----
    q = find(lambda p: p.split("/")[-1] == "libcef.dll")
    if q:
        hit("libcef-dll", q, "cef", 0.95)
    q = find(lambda p: p.split("/")[-1] in ("cef.pak", "cef_100_percent.pak",
                                            "cef_200_percent.pak", "cef_resources.pak"))
    if q:
        hit("cef-pak", q, "cef", 0.5)

    # ---- WPF / WinForms ----
    for dll in ("presentationframework.dll", "presentationcore.dll",
                "presentationnative.dll", "presentationnative.ni.dll"):
        q = find(lambda p, d=dll: p.split("/")[-1] == d)
        if q:
            hit(dll, q, "wpf", 0.8)
            break
    deps = [f for f in fileset if f.lower().endswith(".deps.json")]
    for dep in deps:
        try:
            with open(os.path.join(root, dep.replace("/", os.sep)), "r",
                      encoding="utf-8", errors="replace") as fh:
                txt = fh.read().lower()
            if "presentationframework" in txt:
                hit("deps-json-wpf", dep, "wpf", 0.7)
                break
        except OSError:
            pass
    cfg_files = [f for f in fileset if f.lower().endswith(".exe.config")]
    if cfg_files:
        hit("exe-config", cfg_files[0], "wpf", 0.3)
    gres = [f for f in fileset if f.lower().endswith(".g.resources")]
    if gres:
        hit("g-resources", gres[0], "wpf", 0.5)
    q = find(lambda p: p.split("/")[-1] == "system.windows.forms.dll")
    if q:
        hit("system-windows-forms", q, "winforms", 0.7)
    q = find(lambda p: p.split("/")[-1] == "system.drawing.dll")
    if q:
        hit("system-drawing", q, "winforms", 0.3)

    # ---- Qt 源码形态: 目录里没有 Qt dll, 但 *.py 直接 import PySide*/PyQt* ----
    qt_import_re = re.compile(
        rb"^\s*(?:from|import)\s+(PySide6|PySide2|PyQt5|PyQt6)\b", re.M)
    for py in [f for f in fileset if f.lower().endswith(".py")]:
        try:
            with open(os.path.join(root, py.replace("/", os.sep)), "rb") as fh:
                head = fh.read(262144)
            if qt_import_re.search(head):
                hit("py-qt-import", py, "qt", 0.6)
                break
        except OSError:
            pass
    for req in [f for f in fileset if f.lower().endswith("requirements.txt")]:
        try:
            with open(os.path.join(root, req.replace("/", os.sep)), "rb") as fh:
                head = fh.read(65536)
            if any(pkg in head for pkg in (b"PySide6", b"PySide2", b"PyQt5", b"PyQt6")):
                hit("requirements-qt", req, "qt", 0.3)
                break
        except OSError:
            pass

    # ---- .NET 程序集字节串扫描: 同目录无 Presentation*.dll 时, 元数据 #Strings 堆里仍有引用名 ----
    for pe in [f for f in fileset if f.lower().endswith((".exe", ".dll"))]:
        pe_path = os.path.join(root, pe.replace("/", os.sep))
        try:
            if os.path.getsize(pe_path) > 32 * 1024 * 1024:
                continue
            with open(pe_path, "rb") as fh:
                data = fh.read(8 * 1024 * 1024)
        except OSError:
            continue
        if b"PresentationFramework" in data:
            hit("dotnet-presentationframework-str", pe, "wpf", 0.8)
        if b"PresentationCore" in data:
            hit("dotnet-presentationcore-str", pe, "wpf", 0.4)
        if b"System.Windows.Forms" in data:
            hit("dotnet-winforms-str", pe, "winforms", 0.7)

    # ---- 兜底 win32 ----
    has_pe = any(f.lower().endswith(".exe") or f.lower().endswith(".dll") for f in fileset)
    if has_pe and not scores:
        hit("pe-fallback", "*.exe/*.dll", "win32", 0.2)

    # 选定框架
    if not scores:
        framework = "unknown"
        confidence = "low"
    else:
        framework = max(scores, key=lambda k: scores[k])
        top = scores[framework]
        if top >= 1.3:
            confidence = "high"
        elif top >= 0.7:
            confidence = "medium"
        else:
            confidence = "low"

    # UI 层入口
    entries = []
    if framework == "qt":
        for qss in qss_files:
            entries.append({"kind": "external-qss", "path": qss,
                            "note": "外部 QSS 样式表, 替换文件即可换肤"})
        for rcc in rcc_files:
            entries.append({"kind": "qt-external-rcc", "path": rcc,
                            "note": "外部注册的 .rcc 资源包"})
        if not entries:
            entries.append({"kind": "embedded-qrc", "path": None,
                            "note": "未发现外部 qss/rcc, 样式可能内嵌于 exe, 本工具箱不建议改"})
    elif framework == "electron":
        if "resources/app.asar" in lower_files:
            entries.append({"kind": "asar", "path": "resources/app.asar",
                            "note": "renderer HTML/CSS/JS 位于 asar 内, 用 asar_replace"})
        if any(f.startswith("resources/app/") for f in fileset):
            entries.append({"kind": "loose-app", "path": "resources/app",
                            "note": "未打包源码目录, 可直接 replace_file"})
    elif framework == "cef":
        entries.append({"kind": "cef-html", "path": None,
                        "note": "CEF 只提供内核, UI 多为本地 HTML 或远程 URL; 本工具箱默认只识别不改包"})
    elif framework == "wpf":
        for cfg in cfg_files[:1]:
            entries.append({"kind": "wpf-exe-config", "path": cfg,
                            "note": ".NET 运行时配置; BAML 内嵌, 推荐外挂 ResourceDictionary 路线"})
    elif framework == "winforms":
        entries.append({"kind": "winforms-resources", "path": None,
                        "note": "图片/颜色在 .resources 内, 可用 pe_resource 换 PE 层图标/位图"})

    public_signals = [{k: v for k, v in s.items() if not k.startswith("_")} for s in signals]
    return public_signals, framework, confidence, entries


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------

def _run_ps(cmd, timeout=30):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.stdout, r.stderr, r.returncode
    except Exception as e:  # noqa: BLE001
        return "", str(e), -1


def guard_authenticode(exe_path):
    """True=已签名且有效; False=未签名; None=判定失败/无 exe。"""
    if not exe_path or not os.path.isfile(exe_path):
        return None
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$s=Get-AuthenticodeSignature -LiteralPath '%s';"
        "if ($s) { $s.Status } else { 'NONE' }" % exe_path.replace("'", "''")
    )
    out, err, rc = _run_ps(ps, timeout=20)
    status = (out or "").strip().upper()
    if "VALID" in status:
        return True
    if "NOTSIGNED" in status or status == "NONE":
        return False
    return None


def _parse_pe_clr(path):
    """最小 PE/CLR 解析: 返回 (is_dotnet, strong_name_signed)。失败返回 (None, None)。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data[:2] != b"MZ":
            return None, None
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            return None, None
        coff = e_lfanew + 4
        # COFF header: 20 字节; optional header size 在 coff+16 (2 字节)
        opt_size = struct.unpack_from("<H", data, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from("<H", data, opt)[0]
        # PE32=0x10b, PE32+=0x20b
        if magic not in (0x10B, 0x20B):
            return None, None
        # data directories 起始: PE32 opt+96, PE32+ opt+112; 每项 8 字节 (RVA, size)
        dd_base = opt + (96 if magic == 0x10B else 112)
        # CLI header = 第 15 个目录 (index 14)
        clr_rva, clr_size = struct.unpack_from("<II", data, dd_base + 14 * 8)
        if clr_rva == 0:
            return False, None
        # 节表
        num_sections = struct.unpack_from("<H", data, coff + 2)[0]
        sec_start = opt + opt_size
        sections = []
        for i in range(num_sections):
            off = sec_start + i * 40
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
            sections.append((vaddr, vsize, rawptr, rawsize))

        def rva2off(rva):
            for vaddr, vsize, rawptr, rawsize in sections:
                if vaddr <= rva < vaddr + max(vsize, rawsize):
                    return rawptr + (rva - vaddr)
            return None

        clr_off = rva2off(clr_rva)
        if clr_off is None:
            return None, None
        # CLI header: StrongNameSignature 目录在偏移 0x28 (RVA, size)
        sn_rva, sn_size = struct.unpack_from("<II", data, clr_off + 0x28)
        return True, (sn_size > 0)
    except Exception:  # noqa: BLE001
        return None, None


def guard_strong_named(exe_path):
    if not exe_path:
        return None
    is_dotnet, sn = _parse_pe_clr(exe_path)
    if not is_dotnet:
        return None  # 非 .NET, 强命名概念不适用
    return bool(sn)


def guard_asar_integrity(root, files_list):
    """检测 electron-builder / fuses / asarIntegrity 信号。True=发现完整性保护信号。"""
    lower = {f.lower(): f for f in files_list}
    for sig in ("resources/electron-builder.yml", "resources/electron-builder.yaml",
                "resources/electron-builder.json"):
        if sig in lower:
            return True, "发现 " + lower[sig] + " (electron-builder 产物)"
    # 扫描 resources/app.asar 旁 package.json 里的 asarIntegrity
    pkg = lower.get("resources/app.asar")  # 仅作为存在性线索
    # fuses 魔数扫描主 exe (二进制内搜索, 限制在 4MB 内)
    return False, None


def guard_fuses_magic(exe_path):
    """在主 exe 内搜索 Electron fuses 魔数; 返回 True/False/None。"""
    if not exe_path or not os.path.isfile(exe_path):
        return None
    try:
        with open(exe_path, "rb") as f:
            chunk = f.read(8 * 1024 * 1024)
        return b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX" in chunk
    except Exception:  # noqa: BLE001
        return None


def guard_in_program_files(root):
    low = os.path.normpath(os.path.abspath(root)).lower()
    return low.startswith("c:\\program files") or low.startswith("c:\\program files (x86)")


def guard_process_running(exe_path):
    if not exe_path:
        return False
    name = os.path.basename(exe_path)
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + name, "/FO", "CSV"],
                           capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace")
        return name.lower() in (r.stdout or "").lower()
    except Exception:  # noqa: BLE001
        return False


def guard_writable(root):
    try:
        fd, tmp = tempfile.mkstemp(dir=root, prefix=".reskin-write-test-")
        os.close(fd)
        os.remove(tmp)
        return True
    except OSError:
        return False


def collect_guards(root, exe_path):
    files_list = _walk_files(root)
    asar_int, asar_note = guard_asar_integrity(root, files_list)
    fuses = guard_fuses_magic(exe_path)
    if fuses is True and not asar_int:
        asar_int = True
        asar_note = "主 exe 内发现 Electron fuses 魔数"
    return {
        "authenticode_signed": guard_authenticode(exe_path),
        "asar_integrity": asar_int,
        "strong_named": guard_strong_named(exe_path),
        "writable": guard_writable(root),
        "in_program_files": guard_in_program_files(root),
        "process_running": guard_process_running(exe_path),
    }, asar_note


# ---------------------------------------------------------------------------
# skin 包解析
# ---------------------------------------------------------------------------

def load_skin(skin_dir):
    manifest = os.path.join(skin_dir, "skin.json")
    if not os.path.isfile(manifest):
        raise ValueError("换肤包缺少 skin.json: " + manifest)
    with open(manifest, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if data.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("skin.json manifest_version 不支持: %r" % data.get("manifest_version"))
    data["_dir"] = os.path.abspath(skin_dir)
    return data


def validate_target_match(skin, root, signals):
    """按 target_match 校验; 返回 warnings 列表(不通过则抛错)。"""
    sig_names = {s["name"] for s in signals}
    fileset = set(_walk_files(root))
    tm = skin.get("target_match") or {}
    problems = []
    for s in tm.get("signals_all") or []:
        if s not in sig_names:
            problems.append("缺少必需信号: " + s)
    for f in tm.get("files_any") or []:
        if f not in fileset:
            problems.append("target 缺少匹配文件: " + f)
    if tm.get("files_any") and problems:
        # files_any 语义是「任意一个」, 这里宽松: 只要有一个存在即可
        found_any = any(f in fileset for f in tm["files_any"])
        if found_any:
            problems = [p for p in problems if not p.startswith("target 缺少匹配文件:")]
    if problems:
        raise ValueError("target_match 校验失败: " + "; ".join(problems))


# ---------------------------------------------------------------------------
# 操作原语
# ---------------------------------------------------------------------------

class OpUnsupported(Exception):
    def __init__(self, code, message, install_hint=None):
        super().__init__(message)
        self.code = code
        self.install_hint = install_hint


def atomic_write_bytes(dst_root, rel_dst, data_bytes):
    """先写临时文件再 os.replace, 保证原子。"""
    final = os.path.join(dst_root, rel_dst.replace("/", os.sep))
    os.makedirs(os.path.dirname(final), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(final), prefix=".reskin-tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data_bytes)
        os.replace(tmp, final)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def op_replace_file(skin, op, root):
    src = os.path.join(skin["_dir"], op["src"].replace("/", os.sep))
    if not os.path.isfile(src):
        raise ValueError("replace_file 源不存在: " + op["src"])
    with open(src, "rb") as f:
        data = f.read()
    dst = op["dst"]
    if relpath_safe(dst, root) is None:
        raise ValueError("replace_file dst 越出 target 根: " + dst)
    atomic_write_bytes(root, dst, data)
    return {"op": "replace_file", "dst": dst, "bytes": len(data)}


def op_patch_text(skin, op, root):
    rel = op["file"]
    final = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(final):
        raise ValueError("patch_text 目标文件不存在: " + rel)
    enc = op.get("encoding", "utf-8")
    if enc not in ("utf-8", "utf-8-sig"):
        raise ValueError("patch_text 仅支持 utf-8 / utf-8-sig, 收到: " + enc)
    with open(final, "rb") as f:
        raw = f.read()
    text = raw.decode(enc)
    find = op["find"]
    replace = op["replace"]
    must = int(op.get("must_match", 1))
    count = text.count(find)
    if count != must:
        raise ValueError(
            "patch_text must_match 不符: 期望 %d 次, 实际 %d 次 (%s)" % (must, count, rel))
    new_text = text.replace(find, replace)
    out_bytes = new_text.encode(enc)
    atomic_write_bytes(root, rel, out_bytes)
    return {"op": "patch_text", "dst": rel, "matches": count}


def _node_exe():
    return shutil.which("node") or shutil.which("node.exe")


def op_asar_replace(skin, op, root):
    node = _node_exe()
    if not node:
        raise OpUnsupported("NODE_MISSING",
                            "未找到 node 可执行文件, 请先安装 Node.js 22+",
                            "winget install OpenJS.NodeJS.LTS")
    archive_rel = op["archive"]
    archive = os.path.join(root, archive_rel.replace("/", os.sep))
    if not os.path.isfile(archive):
        raise ValueError("asar_replace 归档不存在: " + archive_rel)
    src = os.path.join(skin["_dir"], op["src"].replace("/", os.sep))
    if not os.path.isfile(src):
        raise ValueError("asar_replace 源文件不存在: " + op["src"])
    here = os.path.dirname(os.path.abspath(__file__))
    js = os.path.join(here, "asar_pack.js")
    member = op["member"]
    proc = subprocess.run(
        [node, js, "replace", archive, member, src],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    # 解析 JSON Lines
    last_event = None
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        last_event = evt
        if evt.get("event") == "error":
            if evt.get("code") == "MISSING_ASAR":
                raise OpUnsupported("ASAR_MISSING", evt.get("message", "asar 依赖缺失"),
                                    evt.get("install_hint"))
            raise ValueError("asar_pack 错误: " + evt.get("message", "未知"))
    if last_event is None or last_event.get("event") != "replaced":
        raise ValueError("asar_replace 未收到 replaced 事件: " + (proc.stderr or "")[:400])
    return {"op": "asar_replace", "archive": archive_rel, "member": member}


def find_resource_hacker():
    candidates = []
    env = os.environ.get("RESKINNER_RH_EXE")
    if env:
        candidates.append(env)
    candidates += [
        r"C:\Program Files\Resource Hacker\ResourceHacker.exe",
        r"C:\Program Files (x86)\Resource Hacker\ResourceHacker.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Resource Hacker\ResourceHacker.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return shutil.which("ResourceHacker.exe") or shutil.which("ResourceHacker")


def op_pe_resource(skin, op, root):
    rh = find_resource_hacker()
    if not rh:
        raise OpUnsupported(
            "RESOURCE_HACKER_MISSING",
            "未检测到 ResourceHacker.exe, pe_resource 不可用",
            "官网 https://www.angusj.com/resourcehacker/ 下载, 或执行: winget install AngusJ.ResourceHacker")
    image = os.path.join(root, op["image"].replace("/", os.sep))
    if not os.path.isfile(image):
        raise ValueError("pe_resource 目标 exe 不存在: " + op["image"])
    src = os.path.join(skin["_dir"], op["src"].replace("/", os.sep))
    if not os.path.isfile(src):
        raise ValueError("pe_resource 源文件不存在: " + op["src"])
    restype = op.get("restype", "RCDATA")
    resname = op["resname"]
    lang = str(op.get("lang", 0))
    # Resource Hacker 不原地写; 先输出到临时 exe, 再原子替换
    fd, tmp_exe = tempfile.mkstemp(suffix=".exe", dir=os.path.dirname(image))
    os.close(fd)
    os.remove(tmp_exe)
    mask = "%s,%s,%s" % (restype, resname, lang)
    cmd = [rh, "-open", image, "-save", tmp_exe,
           "-action", "addoverwrite", "-res", src, "-mask", mask,
           "-log", os.devnull]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not os.path.isfile(tmp_exe):
        try:
            if os.path.exists(tmp_exe):
                os.remove(tmp_exe)
        except OSError:
            pass
        raise ValueError("Resource Hacker 执行失败 (rc=%d): %s" %
                         (proc.returncode, (proc.stderr or "")[:300]))
    os.replace(tmp_exe, image)
    return {"op": "pe_resource", "image": op["image"], "resource": mask}


OP_HANDLERS = {
    "replace_file": op_replace_file,
    "patch_text": op_patch_text,
    "asar_replace": op_asar_replace,
    "pe_resource": op_pe_resource,
}


def op_target_relpath(op):
    """返回该 op 会修改的相对路径(用于备份/校验)。"""
    kind = op["op"]
    if kind == "replace_file":
        return op["dst"]
    if kind == "patch_text":
        return op["file"]
    if kind == "asar_replace":
        return op["archive"]
    if kind == "pe_resource":
        return op["image"]
    return None


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

def make_backup(root, entries_rel_paths, label=""):
    """对给定相对路径集合做备份, 返回 (backup_dir, manifest_dict)。"""
    bdir = os.path.join(root, BACKUP_DIRNAME, now_ts() + ("-" + label if label else ""))
    files_dir = os.path.join(bdir, "files")
    os.makedirs(files_dir, exist_ok=True)
    entries = []
    for rel in entries_rel_paths:
        if rel is None:
            continue
        final = os.path.join(root, rel.replace("/", os.sep))
        bak_rel = os.path.join("files", rel)
        bak_full = os.path.join(bdir, bak_rel)
        existed = os.path.isfile(final)
        entry = {
            "relpath": rel.replace(os.sep, "/"),
            "backup_relpath": bak_rel.replace(os.sep, "/"),
            "existed_before": existed,
            "sha256": None, "size": None, "mtime": None,
        }
        if existed:
            os.makedirs(os.path.dirname(bak_full), exist_ok=True)
            shutil.copy2(final, bak_full)
            st = os.stat(final)
            entry["sha256"] = sha256_of_file(final)
            entry["size"] = st.st_size
            entry["mtime"] = st.st_mtime
        entries.append(entry)
    manifest = {
        "tool": TOOL_NAME,
        "manifest_version": MANIFEST_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target_root": os.path.normpath(os.path.abspath(root)),
        "skin": label,
        "entries": entries,
    }
    with open(os.path.join(bdir, "backup-manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return bdir, manifest


def find_latest_backup(root):
    base = os.path.join(root, BACKUP_DIRNAME)
    if not os.path.isdir(base):
        return None
    dirs = []
    for name in os.listdir(base):
        p = os.path.join(base, name)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "backup-manifest.json")):
            dirs.append(p)
    if not dirs:
        return None
    return sorted(dirs)[-1]


def load_backup_manifest(bdir):
    mp = os.path.join(bdir, "backup-manifest.json")
    with open(mp, "r", encoding="utf-8-sig") as f:
        m = json.load(f)
    if m.get("tool") != TOOL_NAME or m.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("备份清单不是本工具箱生成的, 拒绝还原: " + mp)
    return m


# ---------------------------------------------------------------------------
# 截图(可选)
# ---------------------------------------------------------------------------

def try_screenshot(out_path, window_title=None):
    """返回 (ok, method, error)。优先 PySide6, 其次 ctypes 全屏 BitBlt。"""
    # 路线 1: PySide6
    try:
        from PySide6.QtWidgets import QApplication  # type: ignore
        from PySide6.QtGui import QGuiApplication  # type: ignore
        app = QApplication.instance() or QApplication([])
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("no screen")
        pix = screen.grabWindow(0)
        pix.save(out_path, "PNG")
        return True, "pyside6-grabWindow", None
    except Exception as e:  # noqa: BLE001
        err1 = str(e)
    # 路线 2: 纯 ctypes 全屏抓取 (落 BMP)
    try:
        import ctypes
        from ctypes import wintypes
        bmp_path = os.path.splitext(out_path)[0] + ".bmp"
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        hdc = user32.GetDC(0)
        mdc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        gdi32.SelectObject(mdc, bmp)
        gdi32.BitBlt(mdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.UINT), ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.USHORT),
                        ("biBitCount", wintypes.USHORT), ("biCompression", wintypes.ULONG),
                        ("biSizeImage", wintypes.ULONG), ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.ULONG),
                        ("biClrImportant", wintypes.ULONG)]
        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = w; bi.biHeight = h
        bi.biPlanes = 1; bi.biBitCount = 24; bi.biCompression = 0
        row_size = ((w * 3 + 3) // 4) * 4
        img_size = row_size * h
        buf = ctypes.create_string_buffer(img_size)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        with open(bmp_path, "wb") as f:
            fhdr = struct.pack("<2I2xI", 0x228, 14 + 40 + img_size, 0)
            ihdr = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, img_size, 0, 0, 0, 0)
            f.write(b"BM" + fhdr + ihdr + buf.raw)
        gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(0, hdc)
        return True, "ctypes-bitblt", bmp_path
    except Exception as e:  # noqa: BLE001
        return False, "none", "pyside6 失败(%s); ctypes 失败(%s)" % (err1, e)


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def cmd_detect(args):
    target = norm_target(args.target)
    signals, framework, confidence, entries = detect_framework(target)
    exe = pick_main_exe(target)
    guards, asar_note = collect_guards(target, exe)
    warnings = []
    if asar_note:
        warnings.append("asar 完整性保护信号: " + asar_note)
    if framework == "unknown":
        warnings.append("未识别任何 UI 框架信号, 建议人工确认目标")
    if confidence == "low":
        warnings.append("置信度 low, apply 需 --force 并人工确认")
    result = {
        "ok": True,
        "target_root": os.path.normpath(os.path.abspath(target)),
        "main_exe": os.path.relpath(exe, target).replace(os.sep, "/") if exe else None,
        "framework": framework,
        "confidence": confidence,
        "signals": signals,
        "ui_entry_points": entries,
        "guards": guards,
        "warnings": warnings,
    }
    return result, 0


def cmd_backup(args):
    target = norm_target(args.target)
    skin = None
    if args.skin:
        skin = load_skin(args.skin)
        rels = [op_target_relpath(op) for op in skin.get("ops", [])]
    else:
        rels = args.files or []
    if not rels:
        raise ValueError("backup 子命令需要 --skin 或 --files")
    bdir, manifest = make_backup(target, rels, label=(skin or {}).get("name", "manual"))
    return {"ok": True, "backup_dir": bdir,
            "entries": len(manifest["entries"]),
            "manifest": os.path.join(bdir, "backup-manifest.json")}, 0


def _plan_common(args):
    target = norm_target(args.target)
    skin = load_skin(args.skin)
    signals, framework, confidence, entries = detect_framework(target)
    validate_target_match(skin, target, signals)
    ops_plan = []
    risks = set()
    for op in skin.get("ops", []):
        kind = op.get("op")
        if kind not in OP_HANDLERS:
            raise ValueError("未知操作原语: " + str(kind))
        item = {"op": kind, "target": op_target_relpath(op)}
        if kind == "asar_replace":
            item["archive"] = op["archive"]; item["member"] = op["member"]
            risks.add("asar 重打包"); risks.add("若启用 asarIntegrity 会被运行时拒绝")
        if kind == "pe_resource":
            item["image"] = op["image"]
            risks.add("改写 exe 资源段, Authenticode 签名将失效")
        if kind == "patch_text":
            item["file"] = op["file"]; item["must_match"] = op.get("must_match", 1)
        if kind == "replace_file":
            item["dst"] = op["dst"]
        ops_plan.append(item)
    return target, skin, {
        "framework": framework, "confidence": confidence,
        "ops": ops_plan, "risks": sorted(risks),
    }


def cmd_plan(args):
    target, skin, plan = _plan_common(args)
    return {
        "ok": True, "mode": "dry-run",
        "target_root": target,
        "skin": skin.get("name"),
        "plan": plan,
        "note": "未写入任何文件; 向用户展示本计划并取得明确同意后, 方可带 --confirm 执行 apply",
    }, 2


def cmd_apply(args):
    target, skin, plan = _plan_common(args)
    exe = pick_main_exe(target)
    guards, asar_note = collect_guards(target, exe)

    # ---- 前置阻断检查 ----
    blockers = []
    warns = []
    if plan["confidence"] not in ("high", "medium") and not args.force:
        blockers.append("框架置信度 %s, 需 --force 并人工确认" % plan["confidence"])
    if guards["process_running"]:
        blockers.append("目标进程正在运行, 请先关闭 %s" % (os.path.basename(exe) if exe else "exe"))
    if not guards["writable"]:
        blockers.append("目标目录不可写")
    if guards["authenticode_signed"]:
        warns.append("目标已 Authenticode 签名, 修改后签名将失效")
    if guards["asar_integrity"]:
        blockers.append("检测到 asarIntegrity/fuses 完整性保护, 本地改包会被运行时拒绝; "
                        "本工具箱不提供绕过能力, 请走官方主题系统")
    if guards["strong_named"]:
        warns.append("目标为强命名 .NET 程序集, 修改后强命名校验将失效")
    if guards["in_program_files"]:
        warns.append("目标位于 Program Files, 可能需要管理员权限")

    # 基线 hash 一致性: 与最近一次备份比对
    latest = find_latest_backup(target)
    baseline_map = {}
    if latest:
        try:
            lm = load_backup_manifest(latest)
            for e in lm["entries"]:
                baseline_map[e["relpath"]] = e
        except ValueError:
            latest = None

    ops = skin.get("ops", [])
    rels = [op_target_relpath(op) for op in ops]
    # containment 预检
    for op in ops:
        rel = op_target_relpath(op)
        if rel and relpath_safe(rel, target) is None:
            blockers.append("操作目标越出 target 根: " + str(rel))
        if op["op"] in ("replace_file",) and relpath_safe(op["dst"], target) is None:
            blockers.append("replace_file dst 越界: " + op["dst"])
    # 基线 hash 预检(只对已存在于上一次备份且当前文件已变化的情况)
    for rel in rels:
        if rel in baseline_map:
            cur = os.path.join(target, rel.replace("/", os.sep))
            if os.path.isfile(cur) and baseline_map[rel].get("sha256"):
                cur_hash = sha256_of_file(cur)
                if cur_hash != baseline_map[rel]["sha256"]:
                    blockers.append("文件 %s 自上次备份后已被外部改动 (hash 不一致), 阻断以防覆盖" % rel)

    if not args.confirm:
        # dry-run
        return {
            "ok": True, "mode": "dry-run",
            "target_root": target, "skin": skin.get("name"),
            "plan": plan, "guards": guards,
            "warnings": warns, "blockers": blockers,
            "note": "未写入; 带 --confirm 并解决上述 blockers 后才会写入",
        }, 2

    if blockers:
        return {
            "ok": False, "mode": "blocked",
            "target_root": target,
            "blockers": blockers, "warnings": warns,
        }, 2

    # ---- 先备份 ----
    bdir, manifest = make_backup(target, rels, label=skin.get("name", "skin"))

    # ---- 顺序执行, 失败自动回滚 ----
    done = []
    results = []
    try:
        for op in ops:
            handler = OP_HANDLERS[op["op"]]
            res = handler(skin, op, target)
            results.append(res)
            done.append(op_target_relpath(op))
    except OpUnsupported as e:
        restored, mismatches = _rollback_manifest(bdir, target, manifest)
        return {
            "ok": False, "mode": "rolled-back",
            "unsupported": {"code": e.code, "message": str(e), "install_hint": e.install_hint},
            "already_done": done, "rolled_back": restored, "rollback_mismatches": mismatches,
        }, 1
    except Exception as e:  # noqa: BLE001
        restored, mismatches = _rollback_manifest(bdir, target, manifest)
        return {
            "ok": False, "mode": "rolled-back",
            "error": str(e), "already_done": done,
            "backup_dir": bdir, "rolled_back": restored, "rollback_mismatches": mismatches,
        }, 1

    return {
        "ok": True, "mode": "applied",
        "target_root": target, "skin": skin.get("name"),
        "backup_dir": bdir,
        "results": results,
        "warnings": warns,
    }, 0


def _rollback_manifest(bdir, root, manifest):
    """按备份清单还原本次已写入的文件; 逐文件 hash 校验。"""
    restored = []
    mismatches = []
    for e in manifest["entries"]:
        rel = e["relpath"]
        final = os.path.join(root, rel.replace("/", os.sep))
        bak_full = os.path.join(bdir, e["backup_relpath"].replace("/", os.sep))
        if not e["existed_before"]:
            if os.path.isfile(final):
                try:
                    os.remove(final)
                except OSError:
                    mismatches.append(rel + ": 新增文件删除失败")
            restored.append(rel)
            continue
        if not os.path.isfile(bak_full):
            mismatches.append(rel + ": 备份缺失")
            continue
        try:
            os.makedirs(os.path.dirname(final), exist_ok=True)
            tmp = final + ".restore-tmp"
            shutil.copy2(bak_full, tmp)
            os.replace(tmp, final)
            if e.get("sha256") and sha256_of_file(final) != e["sha256"]:
                mismatches.append(rel + ": 还原后 hash 不一致")
            restored.append(rel)
        except OSError as ex:
            mismatches.append(rel + ": 还原失败 " + str(ex))
    return restored, mismatches


def cmd_rollback(args):
    target = norm_target(args.target)
    if args.backup_dir:
        bdir = args.backup_dir
    else:
        bdir = find_latest_backup(target)
    if not bdir:
        return {"ok": False, "error": "未找到任何备份目录"}, 1
    manifest = load_backup_manifest(bdir)
    restored = []
    mismatches = []
    for e in manifest["entries"]:
        rel = e["relpath"]
        final = os.path.join(target, rel.replace("/", os.sep))
        bak_full = os.path.join(bdir, e["backup_relpath"].replace("/", os.sep))
        if not e["existed_before"]:
            if os.path.isfile(final):
                os.remove(final)
            restored.append(rel + " (原为不存在, 已删除)")
            continue
        if not os.path.isfile(bak_full):
            mismatches.append(rel + ": 备份文件缺失")
            continue
        os.makedirs(os.path.dirname(final), exist_ok=True)
        tmp = final + ".restore-tmp"
        shutil.copy2(bak_full, tmp)
        os.replace(tmp, final)
        # 还原后 hash 校验
        if e.get("sha256"):
            cur = sha256_of_file(final)
            if cur != e["sha256"]:
                mismatches.append(rel + ": 还原后 hash 不一致")
        restored.append(rel)
    ok = len(mismatches) == 0
    return {"ok": ok, "backup_dir": bdir, "restored": restored, "mismatches": mismatches}, (0 if ok else 1)


def cmd_verify(args):
    target = norm_target(args.target)
    result = {"ok": True, "target_root": target, "checks": []}
    # 对比最近一次 apply 的备份: 文件当前 hash 应 != 备份时 hash
    bdir = args.backup_dir or find_latest_backup(target)
    if bdir:
        try:
            manifest = load_backup_manifest(bdir)
            for e in manifest["entries"]:
                if not e.get("sha256"):
                    continue
                final = os.path.join(target, e["relpath"].replace("/", os.sep))
                if not os.path.isfile(final):
                    result["checks"].append({"file": e["relpath"], "status": "missing"})
                    continue
                cur = sha256_of_file(final)
                status = "changed" if cur != e["sha256"] else "unchanged"
                result["checks"].append({"file": e["relpath"], "status": status,
                                         "current_sha256": cur[:16] + "...",
                                         "baseline_sha256": e["sha256"][:16] + "..."})
        except ValueError as ex:
            result["ok"] = False
            result["error"] = str(ex)
    else:
        result["checks"].append({"file": "(none)", "status": "no-backup"})

    if args.screenshot:
        out_dir = args.out or os.path.join(target, "..", "..", "verification")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "verify-%s.png" % now_ts())
        ok, method, info = try_screenshot(out_path, args.window_title)
        result["screenshot"] = {"ok": ok, "method": method, "path": info if ok else None,
                                 "error": None if ok else info}
        if not ok:
            result["screenshot_status"] = "unsupported"

    out_dir = args.out or os.path.join(target, BACKUP_DIRNAME)
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "verify-report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result["report_path"] = report_path
    return result, 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="reskin.py", description="desktop-ui-reskinner 通用换肤工具箱")
    p.add_argument("--json", action="store_true", help="stdout 只输出一个 JSON 对象")
    sub = p.add_subparsers(dest="command", required=True)

    def add_target(sp):
        sp.add_argument("--target", required=True, help="应用根目录或主 exe 路径")

    sp = sub.add_parser("detect", help="只读识别框架/置信度/UI 入口/守卫状态")
    add_target(sp)

    sp = sub.add_parser("backup", help="备份待改文件并写清单")
    add_target(sp)
    sp.add_argument("--skin", help="换肤包目录(自动按其 ops 备份目标)")
    sp.add_argument("--files", nargs="*", help="或显式列出要备份的相对路径")

    sp = sub.add_parser("plan", help="干跑解析换肤包, 列出操作与风险")
    add_target(sp)
    sp.add_argument("--skin", required=True)

    sp = sub.add_parser("apply", help="默认 dry-run; --confirm 才写入, 写前强制备份")
    add_target(sp)
    sp.add_argument("--skin", required=True)
    sp.add_argument("--confirm", action="store_true", help="显式确认写入")
    sp.add_argument("--force", action="store_true", help="置信度低/unknown 时强制放行")
    sp.add_argument("--backup-dir", help="自定义备份目录(默认 .reskin-backups/<时间戳>)")

    sp = sub.add_parser("rollback", help="按备份清单还原并逐文件 hash 校验")
    add_target(sp)
    sp.add_argument("--backup-dir", help="指定备份目录(缺省取最近一次)")

    sp = sub.add_parser("verify", help="比对计划与实际变更; 可选截图")
    add_target(sp)
    sp.add_argument("--skin")
    sp.add_argument("--screenshot", action="store_true")
    sp.add_argument("--window-title")
    sp.add_argument("--backup-dir", help="指定备份目录(缺省取最近一次)")
    sp.add_argument("--out")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "detect":
            result, code = cmd_detect(args)
        elif args.command == "backup":
            result, code = cmd_backup(args)
        elif args.command == "plan":
            result, code = cmd_plan(args)
        elif args.command == "apply":
            result, code = cmd_apply(args)
        elif args.command == "rollback":
            result, code = cmd_rollback(args)
        elif args.command == "verify":
            result, code = cmd_verify(args)
        else:
            raise ValueError("未知命令: " + str(args.command))
    except OpUnsupported as e:
        result = {"ok": False, "unsupported": {"code": e.code, "message": str(e),
                                              "install_hint": e.install_hint}}
        code = 1
    except Exception as e:  # noqa: BLE001
        result = {"ok": False, "error": str(e)}
        code = 1

    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        # 人类可读摘要
        if result.get("ok"):
            log("操作完成: " + json.dumps(result, ensure_ascii=False))
        else:
            log("操作未成功: " + json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
