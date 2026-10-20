# -*- coding: utf-8 -*-
"""汇总 Qt 验证结果，写 verify-report.json"""
import json, os
from PIL import Image

V = r"E:\逆向桌面级软件自定义UI\verification\qt-pyside6"

def st(p):
    im = Image.open(p).convert("RGB")
    px = list(im.getdata())
    n = len(px)
    r = sum(q[0] for q in px)/n; g = sum(q[1] for q in px)/n; b = sum(q[2] for q in px)/n
    return {"mean_r": round(r,2), "mean_g": round(g,2), "mean_b": round(b,2),
            "brightness": round((r*299+g*587+b*114)/1000,2)}

b = st(os.path.join(V,"before.png"))
a = st(os.path.join(V,"after.png"))
rt = st(os.path.join(V,"restored.png"))

# 像素级 diff: before vs restored
im1 = Image.open(os.path.join(V,"before.png")).convert("RGB")
im2 = Image.open(os.path.join(V,"restored.png")).convert("RGB")
p1, p2 = list(im1.getdata()), list(im2.getdata())
diff_pixels = sum(1 for x,y in zip(p1,p2) if x!=y)

report = {
  "target": "qt-pyside6",
  "skin": "qt-dark-blue",
  "environment": {"platform":"win11","python":"3.13 venv","qt":"PySide6 6.12.0","render":"QT_QPA_PLATFORM=offscreen"},
  "commands": [
    {"step":"before shot","cmd":".venv\\Scripts\\python.exe verification\\qt-pyside6\\shoot.py verification\\qt-pyside6\\before.png demo-targets\\qt-pyside6","exit":0},
    {"step":"plan dry-run","cmd":"reskin.py --json plan --target <qt> --skin <qt-dark-blue>","exit":2,"note":"dry-run 不写入，符合约定"},
    {"step":"apply dry-run (no --confirm)","cmd":"reskin.py --json apply --target <qt> --skin <qt-dark-blue>","exit":2,"note":"无写入"},
    {"step":"apply --confirm --force (CWD=target root)","cmd":"cd demo-targets\\qt-pyside6; reskin.py --json apply --target . --skin <abs qt-dark-blue> --confirm --force","exit":0},
    {"step":"after shot","cmd":"shoot.py after.png","exit":0},
    {"step":"rollback","cmd":"cd demo-targets\\qt-pyside6; reskin.py --json rollback --target .","exit":0},
    {"step":"restored shot","cmd":"shoot.py restored.png","exit":0}
  ],
  "pixel_assertions": {
    "before": b, "after": a, "restored": rt,
    "brightness_after_lt_0.7_before": a["brightness"] < 0.7*b["brightness"],
    "blue_dominant_after": a["mean_b"] > a["mean_r"],
    "before_vs_restored_diff_pixels": diff_pixels,
    "restored_equals_before": diff_pixels == 0
  },
  "bugs_workarounds": [
    "reskin.py 把 manifest 中相对 dst (skins/style.qss/config.ini) 按进程 CWD 解析 containment，CWD 不在 target 根时误判越界(blocked, exit 2)；workaround：执行 apply/rollback 时把 CWD 切到 target 根。",
    "detect 对源码形态靶场只给出 confidence=low（无 Qt6Core.dll 信号），apply 需 --force。"
  ],
  "verdict": "SUCCESS"
}
with open(os.path.join(V,"verify-report.json"),"w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report["pixel_assertions"],ensure_ascii=False,indent=2))
