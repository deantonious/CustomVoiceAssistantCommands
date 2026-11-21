"""Generate the Assist Utils brand icons.

A speech bubble with a circular "restart" arrow, drawn at 4x and downsampled
for smooth edges. Output: custom_components/assist_utils/brand/icon.png (256 px)
and icon@2x.png (512 px). Home Assistant falls back to the icon for the logo
and for dark mode.

    python scripts/make_icon.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

BLUE = (24, 188, 242, 255)  # #18BCF2
WHITE = (255, 255, 255, 255)
OUT = Path(__file__).parent.parent / "custom_components" / "assist_utils" / "brand"


def draw(size: int) -> Image.Image:
    s = size * 4  # supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 256  # design grid: 256 units

    # Bubble body and tail (bottom left).
    d.rounded_rectangle((16 * u, 20 * u, 240 * u, 200 * u), radius=56 * u, fill=BLUE)
    d.polygon([(52 * u, 180 * u), (44 * u, 244 * u), (112 * u, 194 * u)], fill=BLUE)

    # Circular arrow, centred in the bubble.
    cx, cy, r, w = 128 * u, 110 * u, 52 * u, 20 * u
    start, end = -60, 230  # degrees, clockwise from 3 o'clock; gap at top right
    d.arc((cx - r, cy - r, cx + r, cy + r), start=start, end=end, fill=WHITE, width=int(w))
    # Round caps at the tail of the arc.
    tail = math.radians(end)
    tx, ty = cx + (r - w / 2) * math.cos(tail), cy + (r - w / 2) * math.sin(tail)
    d.ellipse((tx - w / 2, ty - w / 2, tx + w / 2, ty + w / 2), fill=WHITE)
    # Arrow head at the start of the arc, following the circle into the gap
    # (screen angles grow clockwise, so "backwards along the arc" is a - 90°).
    a = math.radians(start)
    mx, my = cx + (r - w / 2) * math.cos(a), cy + (r - w / 2) * math.sin(a)
    tangent = a - math.pi / 2
    normal = a
    head, half = 30 * u, 24 * u
    tip = (mx + head * math.cos(tangent), my + head * math.sin(tangent))
    left = (mx + half * math.cos(normal), my + half * math.sin(normal))
    right = (mx - half * math.cos(normal), my - half * math.sin(normal))
    d.polygon([tip, left, right], fill=WHITE)

    return img.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(256).save(OUT / "icon.png", optimize=True)
    draw(512).save(OUT / "icon@2x.png", optimize=True)
    print("written", OUT)
