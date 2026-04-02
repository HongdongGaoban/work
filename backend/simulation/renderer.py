"""
PIL-based 2D renderer for plant frames.
Renders at 2× resolution then downsamples for soft anti-aliasing.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple

from .parameters import Era
from .lsystem import get_turtle_path

# Output canvas size (display)
CANVAS_W = 800
CANVAS_H = 600
SCALE = 2  # supersampling factor

# Internal render size
RENDER_W = CANVAS_W * SCALE
RENDER_H = CANVAS_H * SCALE

GROUND_RATIO = 0.20  # bottom 20% is ground

# ------------------------------------------------------------------
# Era colour palettes
# ------------------------------------------------------------------
ERA_PALETTE = {
    Era.HADEAN: {
        "sky_top":    (35,  8,  2),
        "sky_bottom": (80, 28,  8),
        "ground":     (60, 22,  6),
        "ground_tex": (35, 12,  2),
        "haze":       (110, 45, 12),
    },
    Era.ARCHEAN: {
        "sky_top":    ( 8, 18,  8),
        "sky_bottom": (18, 35, 18),
        "ground":     (40, 30, 14),
        "ground_tex": (24, 17,  7),
        "haze":       (30, 55, 30),
    },
    Era.PROTEROZOIC: {
        "sky_top":    (10, 10, 30),
        "sky_bottom": (22, 22, 55),
        "ground":     (35, 35, 20),
        "ground_tex": (20, 20, 10),
        "haze":       (45, 45, 90),
    },
    Era.CAMBRIAN: {
        "sky_top":    (15, 30, 55),
        "sky_bottom": (28, 55, 90),
        "ground":     (42, 48, 26),
        "ground_tex": (26, 30, 15),
        "haze":       (65, 90, 130),
    },
}


def _lerp(c1: Tuple, c2: Tuple, t: float) -> Tuple[int, ...]:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def _build_background(era: Era, moisture: float) -> Tuple[Image.Image, int]:
    """Return (RGBA background image at RENDER size, ground_y in render coords)."""
    pal = ERA_PALETTE.get(era, ERA_PALETTE[Era.ARCHEAN])
    img = Image.new("RGB", (RENDER_W, RENDER_H))
    draw = ImageDraw.Draw(img)

    ground_y = int(RENDER_H * (1 - GROUND_RATIO))

    # Sky gradient
    for y in range(ground_y):
        t = y / ground_y
        draw.line([(0, y), (RENDER_W, y)], fill=_lerp(pal["sky_top"], pal["sky_bottom"], t))

    # Ground gradient
    for y in range(ground_y, RENDER_H):
        t = (y - ground_y) / (RENDER_H - ground_y)
        draw.line([(0, y), (RENDER_W, y)], fill=_lerp(pal["ground"], pal["ground_tex"], t))

    # Ground texture lines
    rng = np.random.RandomState(42)
    for _ in range(200):
        x = int(rng.uniform(0, RENDER_W))
        y = int(rng.uniform(ground_y, RENDER_H - 4))
        x2 = x + int(rng.uniform(-20, 20))
        y2 = y + int(rng.uniform(0, 10))
        draw.line([(x, y), (x2, y2)], fill=pal["ground_tex"], width=1)

    # Horizon atmospheric haze (alpha composite)
    haze_h = 80
    haze = Image.new("RGBA", (RENDER_W, haze_h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(haze)
    for i in range(haze_h):
        alpha = int(150 * ((1 - i / haze_h) ** 2))
        hd.line([(0, i), (RENDER_W, i)], fill=pal["haze"] + (alpha,))
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(haze, dest=(0, ground_y - haze_h // 2))
    img = img_rgba.convert("RGB")

    # Wet ground glint
    if moisture > 0.55:
        for _ in range(20):
            x = int(rng.uniform(0, RENDER_W))
            y = int(rng.uniform(ground_y, ground_y + 30))
            w = int(rng.uniform(15, 60))
            glint = _lerp(pal["ground"], (180, 200, 240), 0.35)
            ImageDraw.Draw(img).line([(x, y), (x + w, y)], fill=glint, width=1)

    # Volcanic glow for Hadean
    if era == Era.HADEAN:
        glow = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for cx, radius in [(RENDER_W // 5, 90), (RENDER_W * 4 // 5, 70)]:
            gd.ellipse(
                [cx - radius, ground_y - radius // 4,
                 cx + radius, ground_y + radius // 4],
                fill=(220, 80, 10, 70),
            )
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(glow)
        img = img_rgba.convert("RGB")

    return img, ground_y


def render_frame(
    sentence: str,
    angle_deg: float,
    step_scale: float,
    stem_color: Tuple[int, int, int],
    leaf_color: Tuple[int, int, int],
    era: Era,
    moisture: float,
    base_step: float = 10.0,
) -> np.ndarray:
    """
    Render one frame. Returns HxWx3 uint8 numpy array (RGB).
    """
    bg, ground_y = _build_background(era, moisture)
    img = bg.convert("RGBA")
    plant_layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plant_layer)

    step = max(0.5, base_step * step_scale * SCALE)
    start_width = max(1.0, step * 0.45)

    segments, leaves = get_turtle_path(sentence, angle_deg, step, start_width)

    origin_x = RENDER_W // 2
    origin_y = ground_y

    # Draw stems (sorted deepest-first so trunk is beneath branches)
    for seg in sorted(segments, key=lambda s: -s[5]):
        x1, y1, x2, y2, w, depth = seg
        px1, py1 = int(origin_x + x1), int(origin_y - y1)
        px2, py2 = int(origin_x + x2), int(origin_y - y2)
        t = min(depth / 7.0, 1.0)
        color = _lerp(stem_color, tuple(min(255, c + 25) for c in stem_color), t)
        draw.line([(px1, py1), (px2, py2)], fill=color + (220,), width=max(1, int(w)))

    # Draw leaves
    leaf_r = max(3, int(step * 0.55))
    for lx, ly, la, depth in leaves:
        px = int(origin_x + lx)
        py = int(origin_y - ly)
        if -leaf_r <= px <= RENDER_W + leaf_r and -leaf_r <= py <= RENDER_H + leaf_r:
            t = min(depth / 9.0, 1.0)
            lc = _lerp(leaf_color, tuple(min(255, c + 40) for c in leaf_color), t)
            # Slightly elongated ellipse oriented along branch direction
            rx, ry = leaf_r, max(2, leaf_r // 2)
            draw.ellipse([px - rx, py - ry, px + rx, py + ry], fill=lc + (190,))

    # Composite plant onto background
    img.alpha_composite(plant_layer)

    # Downscale with anti-aliasing
    result = img.convert("RGB").resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    return np.array(result)
