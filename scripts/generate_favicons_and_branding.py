#!/usr/bin/env python3
"""
generate_favicons_and_branding.py
Generates standardized vector branding assets (SVGs) and converts them into
PNG favicons and multi-resolution favicon.ico files across the repository.
"""

import os
import sys
import subprocess
import tempfile
from PIL import Image

# Root directory of QMA project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SVG Template for QMA Logo Mark
SVG_MARK = """<svg width="743" height="700" viewBox="0 0 743 700" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M350 0C543.3 0 700 156.7 700 350C700 402.299 688.528 451.918 667.965 496.479L593.563 406.607C597.774 388.418 600 369.469 600 350C600 211.929 488.071 100 350 100C211.929 100 100 211.929 100 350C100 488.071 211.929 600 350 600C367.397 600 384.378 598.222 400.773 594.84L470.27 678.787C432.765 692.51 392.257 700 350 700C156.7 700 0 543.3 0 350C0 156.7 156.7 0 350 0Z" fill="url(#qma-ring-gradient)"/>
<path d="M493.834 400H328.264L576.619 700H742.189L493.834 400Z" fill="url(#qma-slash-gradient)"/>
<defs>
<linearGradient id="qma-ring-gradient" x1="0" y1="0" x2="743" y2="700" gradientUnits="userSpaceOnUse">
<stop stop-color="#6745FA"/>
<stop offset="1" stop-color="#30FCEB"/>
</linearGradient>
<linearGradient id="qma-slash-gradient" x1="328.264" y1="400" x2="742.189" y2="700" gradientUnits="userSpaceOnUse">
<stop stop-color="#6745FA"/>
<stop offset="1" stop-color="#30FCEB"/>
</linearGradient>
</defs>
</svg>"""

SVG_FULL_DARK = """<svg width="2500" height="700" viewBox="0 0 2500 700" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="qma-ring" x1="0" y1="0" x2="743" y2="700" gradientUnits="userSpaceOnUse">
      <stop stop-color="#6745FA"/>
      <stop offset="1" stop-color="#30FCEB"/>
    </linearGradient>
    <linearGradient id="qma-slash" x1="328.264" y1="400" x2="742.189" y2="700" gradientUnits="userSpaceOnUse">
      <stop stop-color="#6745FA"/>
      <stop offset="1" stop-color="#30FCEB"/>
    </linearGradient>
  </defs>
  <path d="M350 0C543.3 0 700 156.7 700 350C700 402.299 688.528 451.918 667.965 496.479L593.563 406.607C597.774 388.418 600 369.469 600 350C600 211.929 488.071 100 350 100C211.929 100 100 211.929 100 350C100 488.071 211.929 600 350 600C367.397 600 384.378 598.222 400.773 594.84L470.27 678.787C432.765 692.51 392.257 700 350 700C156.7 700 0 543.3 0 350C0 156.7 156.7 0 350 0Z" fill="url(#qma-ring)"/>
  <path d="M493.834 400H328.264L576.619 700H742.189L493.834 400Z" fill="url(#qma-slash)"/>
  <text x="860" y="490" font-family="'Sora', 'Inter', sans-serif" font-weight="800" font-size="360" fill="#ffffff" letter-spacing="12">QMA</text>
  <text x="870" y="590" font-family="'Sora', 'Inter', sans-serif" font-weight="400" font-size="70" fill="#6745FA" letter-spacing="22">QUANT MEMORY AGENT</text>
</svg>"""

SVG_FULL_LIGHT = """<svg width="2500" height="700" viewBox="0 0 2500 700" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="qma-ring" x1="0" y1="0" x2="743" y2="700" gradientUnits="userSpaceOnUse">
      <stop stop-color="#6745FA"/>
      <stop offset="1" stop-color="#30FCEB"/>
    </linearGradient>
    <linearGradient id="qma-slash" x1="328.264" y1="400" x2="742.189" y2="700" gradientUnits="userSpaceOnUse">
      <stop stop-color="#6745FA"/>
      <stop offset="1" stop-color="#30FCEB"/>
    </linearGradient>
  </defs>
  <path d="M350 0C543.3 0 700 156.7 700 350C700 402.299 688.528 451.918 667.965 496.479L593.563 406.607C597.774 388.418 600 369.469 600 350C600 211.929 488.071 100 350 100C211.929 100 100 211.929 100 350C100 488.071 211.929 600 350 600C367.397 600 384.378 598.222 400.773 594.84L470.27 678.787C432.765 692.51 392.257 700 350 700C156.7 700 0 543.3 0 350C0 156.7 156.7 0 350 0Z" fill="url(#qma-ring)"/>
  <path d="M493.834 400H328.264L576.619 700H742.189L493.834 400Z" fill="url(#qma-slash)"/>
  <text x="860" y="490" font-family="'Sora', 'Inter', sans-serif" font-weight="800" font-size="360" fill="#0B1020" letter-spacing="12">QMA</text>
  <text x="870" y="590" font-family="'Sora', 'Inter', sans-serif" font-weight="400" font-size="70" fill="#6745FA" letter-spacing="22">QUANT MEMORY AGENT</text>
</svg>"""

SVG_HORIZONTAL = """<svg width="400" height="100" viewBox="0 0 400 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="qma-ring" x1="0" y1="0" x2="743" y2="700" gradientUnits="userSpaceOnUse">
      <stop stop-color="#6745FA"/>
      <stop offset="1" stop-color="#30FCEB"/>
    </linearGradient>
    <linearGradient id="qma-slash" x1="328.264" y1="400" x2="742.189" y2="700" gradientUnits="userSpaceOnUse">
      <stop stop-color="#6745FA"/>
      <stop offset="1" stop-color="#30FCEB"/>
    </linearGradient>
  </defs>
  <g transform="translate(10, 10) scale(0.114)">
    <path d="M350 0C543.3 0 700 156.7 700 350C700 402.299 688.528 451.918 667.965 496.479L593.563 406.607C597.774 388.418 600 369.469 600 350C600 211.929 488.071 100 350 100C211.929 100 100 211.929 100 350C100 488.071 211.929 600 350 600C367.397 600 384.378 598.222 400.773 594.84L470.27 678.787C432.765 692.51 392.257 700 350 700C156.7 700 0 543.3 0 350C0 156.7 156.7 0 350 0Z" fill="url(#qma-ring)"/>
    <path d="M493.834 400H328.264L576.619 700H742.189L493.834 400Z" fill="url(#qma-slash)"/>
  </g>
  <text x="110" y="62" font-family="'Sora', 'Inter', sans-serif" font-weight="800" font-size="48" fill="#ffffff" letter-spacing="2">QMA</text>
  <text x="112" y="80" font-family="'Sora', 'Inter', sans-serif" font-weight="500" font-size="11" fill="#6745FA" letter-spacing="3.2">QUANT MEMORY AGENT</text>
</svg>"""


def write_file(filepath, content):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {filepath}")


def render_svg_to_png_edge(svg_text, out_png_path, width=512, height=512):
    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_exe):
        edge_exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

    tmp_dir = tempfile.gettempdir()
    tmp_html = os.path.join(tmp_dir, f"qma_icon_{width}x{height}.html")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0;
    padding: 0;
    width: {width}px;
    height: {height}px;
    background: transparent;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  svg {{
    width: 100%;
    height: 100%;
  }}
</style>
</head>
<body>
{svg_text}
</body>
</html>"""
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    tmp_shot = os.path.join(tmp_dir, f"shot_{width}x{height}.png")
    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--default-background-color=00000000",
        "--hide-scrollbars",
        f"--screenshot={tmp_shot}",
        f"--window-size={width},{height}",
        f"file:///{tmp_html}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(tmp_shot):
        img = Image.open(tmp_shot).convert("RGBA")
        os.makedirs(os.path.dirname(out_png_path), exist_ok=True)
        img.save(out_png_path, "PNG")
        print(f"Rendered PNG ({width}x{height}): {out_png_path}")
        return img
    else:
        raise RuntimeError(f"Failed to render PNG for {out_png_path}")


def generate_branding_assets():
    print("=== Generating QMA Branding Kit Assets & Favicons ===")

    # Target directories
    branding_dirs = [
        os.path.join(ROOT_DIR, "public", "assets", "branding"),
        os.path.join(ROOT_DIR, "frontend", "public", "assets", "branding"),
    ]

    for bdir in branding_dirs:
        # SVG Assets
        write_file(os.path.join(bdir, "qma-logo-mark.svg"), SVG_MARK)
        write_file(os.path.join(bdir, "qma-logo-full-dark.svg"), SVG_FULL_DARK)
        write_file(os.path.join(bdir, "qma-logo-full-light.svg"), SVG_FULL_LIGHT)
        write_file(os.path.join(bdir, "qma-logo-horizontal.svg"), SVG_HORIZONTAL)
        write_file(os.path.join(bdir, "qma-icon-16.svg"), SVG_MARK)
        write_file(os.path.join(bdir, "qma-icon-32.svg"), SVG_MARK)
        write_file(os.path.join(bdir, "qma-icon-192.svg"), SVG_MARK)
        write_file(os.path.join(bdir, "qma-icon-512.svg"), SVG_MARK)

        # PNG Transparent Assets
        render_svg_to_png_edge(SVG_MARK, os.path.join(bdir, "qma-logo-mark.png"), 512, 512)
        render_svg_to_png_edge(SVG_FULL_DARK, os.path.join(bdir, "qma-logo-full-dark.png"), 2500, 700)
        render_svg_to_png_edge(SVG_FULL_LIGHT, os.path.join(bdir, "qma-logo-full-light.png"), 2500, 700)
        render_svg_to_png_edge(SVG_HORIZONTAL, os.path.join(bdir, "qma-logo-horizontal.png"), 800, 200)
        render_svg_to_png_edge(SVG_MARK, os.path.join(bdir, "qma-icon-16.png"), 16, 16)
        render_svg_to_png_edge(SVG_MARK, os.path.join(bdir, "qma-icon-32.png"), 32, 32)
        render_svg_to_png_edge(SVG_MARK, os.path.join(bdir, "qma-icon-192.png"), 192, 192)
        render_svg_to_png_edge(SVG_MARK, os.path.join(bdir, "qma-icon-512.png"), 512, 512)

    # Render PNGs at high res
    tmp_512_png = os.path.join(tempfile.gettempdir(), "qma_logo_512.png")
    img512 = render_svg_to_png_edge(SVG_MARK, tmp_512_png, 512, 512)

    # Generate multi-res favicons & app icons
    fav_sizes = [16, 32, 48, 64, 128, 180, 192, 512]
    png_outputs = {
        16: ["favicon-16x16.png"],
        32: ["favicon-32x32.png"],
        180: ["apple-touch-icon.png"],
        192: ["android-chrome-192x192.png"],
        512: ["android-chrome-512x512.png"],
    }

    # Public dirs for favicons
    target_favicon_dirs = [
        os.path.join(ROOT_DIR, "public", "assets"),
        os.path.join(ROOT_DIR, "frontend", "public", "assets"),
        os.path.join(ROOT_DIR, "frontend", "public"),
        os.path.join(ROOT_DIR, "logo", "public"),
        os.path.join(ROOT_DIR, "logo", "public", "assets"),
        ROOT_DIR,
    ]

    # Save PNG variations
    for sz, filenames in png_outputs.items():
        resized = img512.resize((sz, sz), Image.Resampling.LANCZOS)
        for fdir in target_favicon_dirs:
            for fname in filenames:
                out_p = os.path.join(fdir, fname)
                os.makedirs(os.path.dirname(out_p), exist_ok=True)
                resized.save(out_p, "PNG")
                print(f"Saved PNG ({sz}x{sz}): {out_p}")

    # Generate multi-resolution ICO file (Frame 0 MUST be 16x16 for browser tab favicons)
    img16 = img512.resize((16, 16), Image.Resampling.LANCZOS)
    img32 = img512.resize((32, 32), Image.Resampling.LANCZOS)
    img48 = img512.resize((48, 48), Image.Resampling.LANCZOS)
    img64 = img512.resize((64, 64), Image.Resampling.LANCZOS)
    img128 = img512.resize((128, 128), Image.Resampling.LANCZOS)
    img256 = img512.resize((256, 256), Image.Resampling.LANCZOS)

    for fdir in target_favicon_dirs:
        ico_path = os.path.join(fdir, "favicon.ico")
        os.makedirs(os.path.dirname(ico_path), exist_ok=True)
        img16.save(
            ico_path,
            format="ICO",
            append_images=[img32, img48, img64, img128, img256],
        )
        print(f"Generated multi-res Favicon ICO (Frame 0 = 16x16): {ico_path}")

    print("\nSUCCESS: All branding kit assets and favicons successfully generated!")


if __name__ == "__main__":
    generate_branding_assets()
