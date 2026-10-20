# -*- coding: utf-8 -*-
"""启动外部 exe，按窗口标题找 hwnd，PrintWindow(flag=2) 截屏存 PNG，结束进程。
用法: python shoot_win.py <exe_path> <out.png> <window_title>
仅依赖 ctypes + Pillow（无需 pywin32）。
"""
import ctypes
from ctypes import wintypes
import sys, subprocess, time, os
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

PW_RENDERFULLCONTENT = 2

def find_hwnd(pid, title):
    result = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        pid_ = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_))
        if pid_.value == pid and user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title in buf.value:
                result.append(hwnd)
        return True
    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return result[0] if result else None

def screenshot(hwnd, out):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
    # 取位图
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w; bi.biHeight = -h; bi.biPlanes = 1; bi.biBitCount = 32; bi.biCompression = 0
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGB", (w, h), bytes(buf), "raw", "BGRX", 0, 1)
    img.save(out)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    return ok, w, h

def main():
    exe, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
    hwnd = None
    for _ in range(60):
        time.sleep(0.5)
        hwnd = find_hwnd(proc.pid, title)
        if hwnd:
            break
    if not hwnd:
        proc.kill()
        raise SystemExit(f"window not found for {exe} title={title}")
    time.sleep(1.0)  # 等渲染
    ok, w, h = screenshot(hwnd, out)
    proc.kill()
    proc.wait()
    print(f"saved {out} pw_ok={ok} {w}x{h}")

if __name__ == "__main__":
    main()
