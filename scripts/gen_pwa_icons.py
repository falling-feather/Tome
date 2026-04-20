"""Generate PWA icons (192/512/maskable) for Inkless.

Run: python scripts/gen_pwa_icons.py
Output: frontend/public/icon-{192,512}.png + icon-maskable-512.png
Requires: Pillow
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path("frontend/public")
OUT.mkdir(parents=True, exist_ok=True)


def _font(px: int):
    for path in ("C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/msyh.ttc"):
        try:
            return ImageFont.truetype(path, size=px)
        except OSError:
            continue
    return ImageFont.load_default()


def make_icon(size: int, glyph_ratio: float = 0.55, with_border: bool = True) -> Image.Image:
    img = Image.new("RGB", (size, size), (24, 22, 33))
    d = ImageDraw.Draw(img)
    if with_border:
        pad = size // 12
        d.rounded_rectangle(
            (pad, pad, size - pad, size - pad),
            radius=size // 10,
            outline=(196, 168, 110),
            width=max(2, size // 64),
        )
    text = "墨"
    font = _font(int(size * glyph_ratio))
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]),
           text, font=font, fill=(232, 220, 184))
    return img


for s in (192, 512):
    p = OUT / f"icon-{s}.png"
    make_icon(s).save(p, optimize=True)
    print("wrote", p)

p = OUT / "icon-maskable-512.png"
make_icon(512, glyph_ratio=0.42, with_border=False).save(p, optimize=True)
print("wrote", p)
