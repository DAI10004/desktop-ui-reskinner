# -*- coding: utf-8 -*-
"""像素统计：读取 png，输出平均亮度与 R/G/B 均值。"""
import sys
from PIL import Image

def stats(path):
    im = Image.open(path).convert("RGB")
    px = im.getdata()
    n = len(px)
    r = sum(p[0] for p in px) / n
    g = sum(p[1] for p in px) / n
    b = sum(p[2] for p in px) / n
    bright = (r * 299 + g * 587 + b * 114) / 1000
    return {"mean_r": round(r, 2), "mean_g": round(g, 2), "mean_b": round(b, 2), "brightness": round(bright, 2)}

if __name__ == "__main__":
    import json
    print(json.dumps(stats(sys.argv[1])))
