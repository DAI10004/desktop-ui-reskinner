# -*- coding: utf-8 -*-
"""启动 exe，按标题找 hwnd，前置后用 GDI BitBlt 从屏幕截窗口区域（对 Chromium 合成窗口有效）。
用法: python shoot_screen.py <exe> <out.png> <title>
"""
import ctypes, sys, subprocess, time, os
from ctypes import wintypes
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

def find_hwnd(pid, title):
    res = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        p = wintypes.DWORD(); user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd); buf = ctypes.create_unicode_buffer(n+1)
            user32.GetWindowTextW(hwnd, buf, n+1)
            if title in buf.value: res.append(hwnd)
        return True
    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return res[0] if res else None

def main():
    exe, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
    hwnd = None
    for _ in range(60):
        time.sleep(0.5); hwnd = find_hwnd(proc.pid, 'Reskinner Electron Demo') or find_hwnd(proc.pid, title)
        if hwnd: break
    if not hwnd:
        proc.kill(); raise SystemExit('window not found')
    # 前置并恢复
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(2.5)  # 等渲染
    rect = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right-rect.left, rect.bottom-rect.top
    hdcScreen = user32.GetDC(0)
    mdc = gdi32.CreateCompatibleDC(hdcScreen)
    bmp = gdi32.CreateCompatibleBitmap(hdcScreen, w, h)
    gdi32.SelectObject(mdc, bmp)
    gdi32.BitBlt(mdc, 0, 0, w, h, hdcScreen, rect.left, rect.top, 0x00CC0020)  # SRCCOPY
    class BMI(ctypes.Structure):
        _fields_=[("biSize",wintypes.DWORD),("biWidth",wintypes.LONG),("biHeight",wintypes.LONG),
                  ("biPlanes",wintypes.WORD),("biBitCount",wintypes.WORD),("biCompression",wintypes.DWORD),
                  ("biSizeImage",wintypes.DWORD),("biXPPM",wintypes.LONG),("biYPPM",wintypes.LONG),
                  ("biUsed",wintypes.DWORD),("biImp",wintypes.DWORD)]
    bmi = BMI(); bmi.biSize=ctypes.sizeof(BMI); bmi.biWidth=w; bmi.biHeight=-h; bmi.biPlanes=1; bmi.biBitCount=32; bmi.biCompression=0
    buf=(ctypes.c_ubyte*(w*h*4))()
    gdi32.GetDIBits(mdc,bmp,0,h,buf,ctypes.byref(bmi),0)
    Image.frombuffer("RGB",(w,h),bytes(buf),"raw","BGRX",0,1).save(out)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(0,hdcScreen)
    proc.kill(); proc.wait()
    print(f"saved {out} {w}x{h}")

if __name__=="__main__":
    main()
