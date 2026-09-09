import os
from PIL import Image

favicon_paths = [
    r"c:\Users\Admin\Downloads\code\buy\qma\favicon.ico",
    r"c:\Users\Admin\Downloads\code\buy\qma\public\assets\favicon.ico",
    r"c:\Users\Admin\Downloads\code\buy\qma\frontend\public\favicon.ico",
    r"c:\Users\Admin\Downloads\code\buy\qma\frontend\public\assets\favicon.ico",
    r"c:\Users\Admin\Downloads\code\buy\qma\logo\public\favicon.ico",
    r"c:\Users\Admin\Downloads\code\buy\qma\logo\public\assets\favicon.ico",
]

for p in favicon_paths:
    if os.path.exists(p):
        img = Image.open(p)
        print(f"Path: {p}")
        print(f"  Format: {img.format}, Mode: {img.mode}, Size: {img.size}")
        print(f"  Top-left (0,0) RGBA: {img.getpixel((0,0))}")
        print(f"  Center pixel RGBA: {img.getpixel((img.width//2, img.height//2))}")
    else:
        print(f"Missing: {p}")
