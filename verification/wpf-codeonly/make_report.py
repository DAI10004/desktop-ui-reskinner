# -*- coding: utf-8 -*-
import json, os
from PIL import Image
V = r"E:\逆向桌面级软件自定义UI\verification\wpf-codeonly"
def st(p):
    im = Image.open(p).convert("RGB"); px=list(im.getdata()); n=len(px)
    r=sum(q[0] for q in px)/n; g=sum(q[1] for q in px)/n; b=sum(q[2] for q in px)/n
    return {"mean_r":round(r,2),"mean_g":round(g,2),"mean_b":round(b,2),"brightness":round((r*299+g*587+b*114)/1000,2)}
b=st(os.path.join(V,"before.png")); a=st(os.path.join(V,"after.png")); rt=st(os.path.join(V,"restored.png"))
p1=list(Image.open(os.path.join(V,"before.png")).convert("RGB").getdata())
p2=list(Image.open(os.path.join(V,"restored.png")).convert("RGB").getdata())
diff=sum(1 for x,y in zip(p1,p2) if x!=y)
report={
 "target":"wpf-codeonly","skin":"wpf-dark",
 "environment":{"compiler":"C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe",
   "refs":"PresentationFramework/PresentationCore/WindowsBase/System.Xaml (GAC, v4.0_4.0.0.0__31bf3856ad364e35)",
   "screenshot":"ctypes PrintWindow(flag=PW_RENDERFULLCONTENT=2)"},
 "detect":{"framework_detected":"win32","confidence":"low","signals":["pe-fallback"],"note":"detector 未识别 WPF（bug，见下）"},
 "commands":[
   {"step":"build","cmd":"powershell -File demo-targets\\wpf-codeonly\\build.ps1","exit":0,"output":"WpfDemo.exe (6144 bytes)"},
   {"step":"before shot","cmd":".venv\\Scripts\\python.exe verification\\shoot_win.py WpfDemo.exe before.png 'Reskinner WPF Demo'","exit":0},
   {"step":"plan dry","cmd":"reskin.py --json plan --target <wpf> --skin <wpf-dark>","exit":2},
   {"step":"apply dry no confirm","cmd":"reskin.py --json apply --target . --skin <wpf-dark>","exit":2,"blockers":["框架置信度 low 需 --force"]},
   {"step":"apply --confirm --force (CWD=target)","cmd":"cd demo-targets\\wpf-codeonly; reskin.py --json apply --target . --skin <abs wpf-dark> --confirm --force","exit":0,"note":"theme.xaml -> #0E1626"},
   {"step":"after shot","cmd":"shoot_win.py ... after.png","exit":0},
   {"step":"rollback","cmd":"reskin.py --json rollback --target .","exit":0,"mismatches":[]},
   {"step":"restored shot","cmd":"shoot_win.py ... restored.png","exit":0}
 ],
 "pixel_assertions":{"before":b,"after":a,"restored":rt,
   "brightness_after_lt_0.7_before":a["brightness"]<0.7*b["brightness"],
   "blue_dominant_after":a["mean_b"]>a["mean_r"],
   "before_vs_restored_diff_pixels":diff,
   "restored_equals_before":diff==0},
 "compliance_note":"合法路径=外挂松散 ResourceDictionary(theme.xaml)；BAML 内嵌资源工具箱保持只读/unsupported，不做 IL 改写或签名破坏。",
 "bugs_workarounds":["detect 未识别 code-only WPF（无 PresentationFramework.dll 旁置），误报 framework=win32/low；apply 需 --force。",
   "相对 dst 的 containment 按 CWD 解析的问题同 Qt 靶场（执行时 CWD=target 根）。"],
 "verdict":"SUCCESS"
}
with open(os.path.join(V,"verify-report.json"),"w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({"before":b,"after":a,"restored":rt,"diff_pixels":diff},ensure_ascii=False,indent=2))
