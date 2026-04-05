"""
PIL-based 2D renderer — enhanced for visual realism.

Improvements over original:
  - Value noise for organic bark/leaf texture variation
  - Bezier-curved branch segments with cylindrical lighting (highlight + shadow)
  - Teardrop-polygon leaf shapes with vein detail
  - Procedural cloud layer for modern/Cambrian backgrounds
  - Noise-driven ground texture
  - Cinematic vignette post-processing
  - AI-generated extinction note support
"""
from __future__ import annotations

import math
import random
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .parameters import Era
from .lsystem import get_turtle_path

# ── Canvas ────────────────────────────────────────────────────────────
CANVAS_W = 800
CANVAS_H = 600
SCALE = 2  # supersampling
RENDER_W = CANVAS_W * SCALE
RENDER_H = CANVAS_H * SCALE
GROUND_RATIO = 0.20

# ── Era colour palettes ───────────────────────────────────────────────
ERA_PALETTE = {
    Era.HADEAN: {
        "sky_top":    (30,  6,  1),
        "sky_bottom": (85, 28,  6),
        "ground":     (65, 22,  5),
        "ground_tex": (38, 12,  2),
        "haze":       (120, 50, 12),
        "particle":   (200, 120, 40),
    },
    Era.ARCHEAN: {
        "sky_top":    ( 6, 16,  6),
        "sky_bottom": (16, 32, 16),
        "ground":     (42, 30, 13),
        "ground_tex": (25, 17,  7),
        "haze":       (28, 52, 28),
        "particle":   (180, 160, 60),
    },
    Era.PROTEROZOIC: {
        "sky_top":    ( 8,  8, 28),
        "sky_bottom": (20, 20, 52),
        "ground":     (36, 36, 20),
        "ground_tex": (20, 20, 10),
        "haze":       (42, 42, 88),
        "particle":   (160, 140, 200),
    },
    Era.CAMBRIAN: {
        "sky_top":    (12, 28, 52),
        "sky_bottom": (26, 52, 88),
        "ground":     (44, 50, 26),
        "ground_tex": (26, 30, 14),
        "haze":       (60, 88, 130),
        "particle":   (220, 200, 100),
    },
}

MODERN_SKY_TOP    = (100, 160, 220)
MODERN_SKY_BOTTOM = (160, 210, 250)
MODERN_GROUND     = (60, 90, 40)
MODERN_HAZE       = (140, 190, 230)

EXTINCT_SKY_TOP    = (25, 20, 18)
EXTINCT_SKY_BOTTOM = (45, 35, 28)
EXTINCT_GROUND     = (55, 45, 35)


# ── Math helpers ─────────────────────────────────────────────────────

def _lerp(c1: Tuple, c2: Tuple, t: float) -> Tuple[int, ...]:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def _to_rgb(c: Tuple[int, ...]) -> Tuple[int, int, int]:
    return (int(c[0]), int(c[1]), int(c[2]))


def _value_noise(x: float, y: float, seed: int = 0) -> float:
    """2D value noise returning approximately -1 to 1."""
    def _hash(ix: int, iy: int) -> float:
        n = ix * 1619 + iy * 31337 + seed * 1013904223
        n = (n ^ (n >> 13)) * 1664525
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0

    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    # Smoothstep
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    v00 = _hash(ix,     iy)
    v10 = _hash(ix + 1, iy)
    v01 = _hash(ix,     iy + 1)
    v11 = _hash(ix + 1, iy + 1)
    return v00 + (v10 - v00) * ux + (v01 - v00) * uy + (v00 - v10 - v01 + v11) * ux * uy


# ── Branch rendering ──────────────────────────────────────────────────

def _draw_curved_segment(
    draw: ImageDraw.ImageDraw,
    x1: float, y1: float,
    x2: float, y2: float,
    width: float,
    color: Tuple[int, int, int],
    opacity: int,
    curve_amount: float = 0.0,
) -> None:
    """Draw one branch segment as a slightly curved bezier with cylindrical lighting."""
    dx, dy = x2 - x1, y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.5:
        return

    # Quadratic bezier control point: perpendicular offset
    mx, my = (x1 + x2) * 0.5, (y1 + y2) * 0.5
    if length > 0:
        perp_x, perp_y = -dy / length, dx / length
    else:
        perp_x, perp_y = 0.0, 1.0
    cx = mx + perp_x * curve_amount
    cy = my + perp_y * curve_amount

    # Approximate bezier with line segments
    n_seg = max(2, int(length / 14))
    pts: list[Tuple[int, int]] = []
    for k in range(n_seg + 1):
        t = k / n_seg
        bx = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2
        by = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2
        pts.append((int(bx), int(by)))

    w = max(1, int(width))

    # ── Shadow side (right of growth direction) ──────────────────────
    if w >= 3:
        shadow_c = tuple(max(0, c - 35) for c in color)
        off = max(1, w // 3)
        s_pts = [(px + off, py) for px, py in pts]
        for k in range(len(s_pts) - 1):
            draw.line(
                [s_pts[k], s_pts[k + 1]],
                fill=shadow_c + (int(opacity * 0.65),),
                width=max(1, w // 2),
            )

    # ── Main stem ────────────────────────────────────────────────────
    for k in range(len(pts) - 1):
        draw.line([pts[k], pts[k + 1]], fill=color + (opacity,), width=w)

    # ── Highlight side (left of growth direction) ─────────────────────
    if w >= 4:
        hi_c = tuple(min(255, c + 45) for c in color)
        off = max(1, w // 4)
        h_pts = [(px - off, py) for px, py in pts]
        for k in range(len(h_pts) - 1):
            draw.line(
                [h_pts[k], h_pts[k + 1]],
                fill=hi_c + (int(opacity * 0.45),),
                width=max(1, w // 3),
            )


# ── Leaf rendering ────────────────────────────────────────────────────

def _draw_leaf_polygon(
    draw: ImageDraw.ImageDraw,
    cx: float, cy: float,
    angle_deg: float,
    size: float,
    color: Tuple[int, int, int],
    opacity: int,
) -> None:
    """Draw a teardrop-shaped leaf polygon with a centre vein."""
    if size < 2:
        return
    n = 14
    pts: list[Tuple[int, int]] = []
    rad = math.radians(angle_deg - 90)
    cos_r, sin_r = math.cos(rad), math.sin(rad)

    for i in range(n):
        theta = i / n * math.pi * 2
        # Teardrop parametric: wide in the middle, pointed at tip
        r = size * (0.55 + 0.45 * math.cos(theta)) * abs(math.sin(theta / 2)) * 1.6
        lx = r * 0.65 * math.sin(theta)
        ly = r * math.cos(theta / 2 + 0.3)
        # Rotate
        rx = lx * cos_r - ly * sin_r
        ry = lx * sin_r + ly * cos_r
        pts.append((int(cx + rx), int(cy + ry)))

    if len(pts) >= 3:
        draw.polygon(pts, fill=color + (opacity,))

    # Vein: thin mid-rib from base toward tip
    vein_len = size * 0.85
    tip_x = int(cx + (-vein_len * sin_r))
    tip_y = int(cy + ( vein_len * cos_r))
    vein_c = tuple(max(0, c - 18) for c in color)
    draw.line([(int(cx), int(cy)), (tip_x, tip_y)],
              fill=vein_c + (min(255, int(opacity * 0.55)),), width=max(1, int(size * 0.07)))


# ── Vignette ──────────────────────────────────────────────────────────

def _apply_vignette(img: Image.Image, strength: float = 0.55) -> Image.Image:
    """Darken image edges for a cinematic look."""
    w, h = img.size
    y_arr = np.linspace(-1.0, 1.0, h)[:, np.newaxis]
    x_arr = np.linspace(-1.0, 1.0, w)[np.newaxis, :]
    dist = np.sqrt((x_arr * 0.75) ** 2 + y_arr ** 2)
    alpha = np.clip((dist - 0.45) / 0.65 * strength, 0.0, 1.0)
    vignette_alpha = (alpha * 195).astype(np.uint8)

    overlay = np.zeros((h, w, 4), dtype=np.uint8)
    overlay[:, :, 3] = vignette_alpha
    vig_img = Image.fromarray(overlay, "RGBA")

    result = img.convert("RGBA")
    result.alpha_composite(vig_img)
    return result.convert("RGB")


# ── Background ────────────────────────────────────────────────────────

def _draw_clouds(img_rgba: Image.Image, sky_color: Tuple, alpha_max: int, seed: int) -> None:
    """Paint a few soft procedural cloud blobs onto an RGBA image."""
    cloud_layer = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cloud_layer)
    rng = random.Random(seed + 777)
    w, h = img_rgba.size
    sky_h = int(h * (1 - GROUND_RATIO))
    cr, cg, cb = min(255, sky_color[0] + 55), min(255, sky_color[1] + 55), min(255, sky_color[2] + 40)
    for _ in range(5):
        bx = rng.randint(0, w)
        by = rng.randint(int(sky_h * 0.05), int(sky_h * 0.55))
        for blob in range(rng.randint(3, 6)):
            rx = rng.randint(40, 120)
            ry = rng.randint(18, 45)
            ox = rng.randint(-60, 60)
            oy = rng.randint(-12, 12)
            a = rng.randint(int(alpha_max * 0.25), alpha_max)
            cd.ellipse(
                [bx + ox - rx, by + oy - ry, bx + ox + rx, by + oy + ry],
                fill=(cr, cg, cb, a),
            )
    img_rgba.alpha_composite(cloud_layer)


def _build_background(
    era: Era,
    moisture: float,
    fate_progress: float = 0.0,
    fate_survived: bool | None = None,
    frame_idx: int = 0,
) -> Tuple[Image.Image, int]:
    """Return (RGB background image at RENDER size, ground_y)."""
    pal = ERA_PALETTE.get(era, ERA_PALETTE[Era.ARCHEAN])
    ground_y = int(RENDER_H * (1 - GROUND_RATIO))

    if fate_progress > 0 and fate_survived is not None:
        t = fate_progress
        if fate_survived:
            sky_top    = _lerp(pal["sky_top"],    MODERN_SKY_TOP,    t)
            sky_bottom = _lerp(pal["sky_bottom"], MODERN_SKY_BOTTOM, t)
            gnd        = _lerp(pal["ground"],     MODERN_GROUND,     t)
            gnd_tex    = _lerp(pal["ground_tex"], (40, 65, 20),      t)
            haze       = _lerp(pal["haze"],       MODERN_HAZE,       t)
        else:
            sky_top    = _lerp(pal["sky_top"],    EXTINCT_SKY_TOP,    t)
            sky_bottom = _lerp(pal["sky_bottom"], EXTINCT_SKY_BOTTOM, t)
            gnd        = _lerp(pal["ground"],     EXTINCT_GROUND,     t)
            gnd_tex    = _lerp(pal["ground_tex"], (35, 28, 22),       t)
            haze       = _lerp(pal["haze"],       (50, 40, 32),       t)
    else:
        sky_top, sky_bottom = pal["sky_top"], pal["sky_bottom"]
        gnd, gnd_tex = pal["ground"], pal["ground_tex"]
        haze = pal["haze"]

    img = Image.new("RGB", (RENDER_W, RENDER_H))
    draw = ImageDraw.Draw(img)

    # ── Sky gradient with subtle noise banding ────────────────────────
    noise_seed = 42 + era.__hash__() % 100
    for y in range(ground_y):
        t = y / ground_y
        base = _lerp(sky_top, sky_bottom, t)
        # Subtle horizontal noise band
        n = _value_noise(y * 0.008, 0.0, noise_seed) * 5
        c = tuple(max(0, min(255, base[i] + int(n))) for i in range(3))
        draw.line([(0, y), (RENDER_W, y)], fill=_to_rgb(c))

    # ── Ground with noise texture ─────────────────────────────────────
    for y in range(ground_y, RENDER_H):
        t = (y - ground_y) / (RENDER_H - ground_y)
        base = _lerp(gnd, gnd_tex, t)
        # Noise variation per row
        n = _value_noise(y * 0.05, 0.5, noise_seed + 1) * 8
        c = tuple(max(0, min(255, base[i] + int(n))) for i in range(3))
        draw.line([(0, y), (RENDER_W, y)], fill=_to_rgb(c))

    # Ground texture streaks
    rng = np.random.RandomState(42)
    for _ in range(280):
        x  = int(rng.uniform(0, RENDER_W))
        y  = int(rng.uniform(ground_y, RENDER_H - 4))
        x2 = x + int(rng.uniform(-25, 25))
        y2 = y + int(rng.uniform(0, 12))
        noise_v = _value_noise(x * 0.02, y * 0.02, noise_seed + 2)
        dark = tuple(max(0, c + int(noise_v * 10)) for c in _to_rgb(gnd_tex))
        draw.line([(x, y), (x2, y2)], fill=dark, width=1)

    # Horizon haze
    haze_h = 90
    haze_img = Image.new("RGBA", (RENDER_W, haze_h), (0, 0, 0, 0))
    haze_draw = ImageDraw.Draw(haze_img)
    for i in range(haze_h):
        alpha = int(150 * ((1 - i / haze_h) ** 2))
        haze_draw.line([(0, i), (RENDER_W, i)], fill=_to_rgb(haze) + (alpha,))
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(haze_img, dest=(0, ground_y - haze_h // 2))
    img = img_rgba.convert("RGB")

    # ── Clouds (modern/Cambrian transition) ───────────────────────────
    show_clouds = (
        (fate_survived and fate_progress > 0.2) or
        era == Era.CAMBRIAN
    )
    if show_clouds:
        cloud_alpha = 35
        if fate_survived and fate_progress > 0.2:
            cloud_alpha = int(35 + fate_progress * 50)
        img_rgba = img.convert("RGBA")
        _draw_clouds(img_rgba, sky_bottom, cloud_alpha, frame_idx // 8)
        img = img_rgba.convert("RGB")

    # Volcanic glow (Hadean)
    if era == Era.HADEAN and (fate_progress < 0.5 or fate_survived):
        glow_strength = max(0.0, 1.0 - fate_progress * 2) if not fate_survived else 1.0
        glow = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for cx, radius in [(RENDER_W // 5, 90), (RENDER_W * 4 // 5, 70)]:
            gd.ellipse(
                [cx - radius, ground_y - radius // 4,
                 cx + radius, ground_y + radius // 4],
                fill=(220, 80, 10, int(60 * glow_strength)),
            )
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(glow)
        img = img_rgba.convert("RGB")

    # Wet ground glint
    if moisture > 0.55 and not (fate_progress > 0.5 and not fate_survived):
        for _ in range(24):
            x = int(rng.uniform(0, RENDER_W))
            y = int(rng.uniform(ground_y, ground_y + 35))
            w = int(rng.uniform(18, 70))
            glint = _lerp(gnd, (180, 200, 240), 0.38)
            ImageDraw.Draw(img).line(
                [(x, y), (x + w, y)], fill=_to_rgb(glint), width=1
            )

    # Survival: sun rays
    if fate_survived and fate_progress > 0.3:
        sun_alpha = int(fate_progress * 85)
        sun_layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        sun_d = ImageDraw.Draw(sun_layer)
        sun_x, sun_y = int(RENDER_W * 0.75), int(RENDER_H * 0.08)
        for angle_deg in range(0, 360, 18):
            rad_a = math.radians(angle_deg)
            r1 = 30
            r2 = 120 + int(45 * fate_progress)
            x1 = int(sun_x + r1 * math.cos(rad_a))
            y1 = int(sun_y + r1 * math.sin(rad_a))
            x2 = int(sun_x + r2 * math.cos(rad_a))
            y2 = int(sun_y + r2 * math.sin(rad_a))
            sun_d.line([(x1, y1), (x2, y2)],
                       fill=(255, 240, 180, sun_alpha), width=2)
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(sun_layer)
        img = img_rgba.convert("RGB")

    # Extinction: falling ash layer
    if fate_survived is False and fate_progress > 0.2:
        ash_layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        ash_d = ImageDraw.Draw(ash_layer)
        ash_rng = np.random.RandomState(int(fate_progress * 1000))
        count = int(80 * (fate_progress - 0.2) / 0.8)
        for _ in range(count):
            x = int(ash_rng.uniform(0, RENDER_W))
            y = int(ash_rng.uniform(0, RENDER_H))
            r = int(ash_rng.uniform(1, 4))
            alpha = int(ash_rng.uniform(60, 160))
            ash_d.ellipse([x - r, y - r, x + r, y + r],
                          fill=(180, 160, 130, alpha))
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(ash_layer)
        img = img_rgba.convert("RGB")

    return img, ground_y


# ── Particles ─────────────────────────────────────────────────────────

def _draw_particles(
    layer: Image.Image,
    era: Era,
    frame_idx: int,
    origin_x: int,
    origin_y: int,
    fate_progress: float,
    fate_survived: bool | None,
) -> None:
    pal = ERA_PALETTE.get(era, ERA_PALETTE[Era.ARCHEAN])
    draw = ImageDraw.Draw(layer)
    rng = random.Random(frame_idx * 7 + 13)

    if fate_survived is False and fate_progress > 0.15:
        pc = _to_rgb(pal["particle"])
        for _ in range(25):
            x = int(rng.uniform(origin_x - 300, origin_x + 300))
            base_y = int(rng.uniform(-50, origin_y))
            y = (base_y + int(fate_progress * RENDER_H * 0.6)) % RENDER_H
            r = rng.randint(1, 3)
            alpha = rng.randint(60, 150)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=pc + (alpha,))
    else:
        pc = _to_rgb(pal["particle"])
        drift_y = (frame_idx * 3) % RENDER_H
        for _ in range(20):
            x = int(rng.gauss(origin_x, 190))
            y = int((rng.uniform(0, origin_y) - drift_y) % origin_y)
            r = rng.randint(1, 3)
            alpha = rng.randint(40, 130)
            # Slightly glowing: draw with a soft halo
            if r >= 2:
                draw.ellipse([x - r - 1, y - r - 1, x + r + 1, y + r + 1],
                             fill=pc + (int(alpha * 0.35),))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=pc + (alpha,))


# ── Plant colours ────────────────────────────────────────────────────

def _blend_plant_colors(
    stem: Tuple, leaf: Tuple,
    fate_progress: float,
    fate_survived: bool | None,
) -> Tuple[Tuple, Tuple]:
    if fate_progress <= 0 or fate_survived is None:
        return stem, leaf

    t = fate_progress
    if fate_survived:
        modern_stem = (70, 55, 25)
        modern_leaf = (40, 180, 60)
        return _lerp(stem, modern_stem, t), _lerp(leaf, modern_leaf, t)
    else:
        dead_stem   = (90, 72, 50)
        dead_leaf   = (80, 68, 45)
        fossil_stem = (100, 95, 88)
        fossil_leaf = (105, 100, 92)
        if t < 0.5:
            t2 = t * 2
            return _lerp(stem, dead_stem, t2), _lerp(leaf, dead_leaf, t2)
        else:
            t2 = (t - 0.5) * 2
            return _lerp(dead_stem, fossil_stem, t2), _lerp(dead_leaf, fossil_leaf, t2)


# ── Plant layer ───────────────────────────────────────────────────────

def _render_plant_layer(
    size: Tuple[int, int],
    sentence: str,
    angle_deg: float,
    step: float,
    start_width: float,
    origin_x: int,
    origin_y: int,
    stem_color: Tuple,
    leaf_color: Tuple,
    frame_idx: int,
    fate_progress: float,
    fate_survived: bool | None,
) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    eff_stem, eff_leaf = _blend_plant_colors(
        stem_color, leaf_color, fate_progress, fate_survived
    )

    segments, leaves = get_turtle_path(sentence, angle_deg, step, start_width)

    noise_rng = random.Random(frame_idx * 31 + 7)

    # Draw stems deepest-first (trunk below branches)
    for seg in sorted(segments, key=lambda s: -s[5]):
        x1, y1, x2, y2, w, depth = seg
        px1 = origin_x + x1
        py1 = origin_y - y1
        px2 = origin_x + x2
        py2 = origin_y - y2

        tip_t = min(depth / 6.0, 1.0)
        noise_v = noise_rng.uniform(-1, 1)
        noise_int = int(noise_v * 14)
        base = _lerp(eff_stem, tuple(min(255, c + 30) for c in eff_stem), tip_t)
        color = tuple(max(0, min(255, base[i] + noise_int)) for i in range(3))

        opacity = 222
        if fate_survived is False and fate_progress > 0.6:
            opacity = int(222 * (1.0 - (fate_progress - 0.6) / 0.4 * 0.5))

        # Curve amount from noise (organic wobble, stronger for thinner branches)
        curve_noise = _value_noise(px1 * 0.004, py1 * 0.004, depth * 17)
        seg_len = math.sqrt((px2 - px1) ** 2 + (py2 - py1) ** 2)
        taper = 1.0 / (1.0 + w * 0.15)   # thin branches curve more
        curve_amt = curve_noise * seg_len * 0.10 * taper

        _draw_curved_segment(draw, px1, py1, px2, py2, w, color, opacity, curve_amt)

    # Draw leaves
    leaf_r = max(3, int(step * 0.58))
    leaf_opacity = 192
    if fate_survived is False and fate_progress > 0.3:
        leaf_opacity = int(192 * max(0, 1.0 - (fate_progress - 0.3) / 0.4))

    for lx, ly, la, depth in leaves:
        px = origin_x + lx
        py = origin_y - ly
        if -leaf_r <= px <= size[0] + leaf_r and -leaf_r <= py <= size[1] + leaf_r:
            tip_t = min(depth / 9.0, 1.0)
            noise_int = noise_rng.randint(-9, 9)
            base = _lerp(eff_leaf, tuple(min(255, c + 35) for c in eff_leaf), tip_t)
            lc = tuple(max(0, min(255, base[i] + noise_int)) for i in range(3))

            _draw_leaf_polygon(draw, px, py, la, leaf_r, lc, leaf_opacity)

    return layer


# ── Shadow ────────────────────────────────────────────────────────────

def _draw_shadow(
    layer: Image.Image,
    origin_x: int,
    ground_y: int,
    step_scale: float,
) -> None:
    draw = ImageDraw.Draw(layer)
    sx = int(82 * step_scale)
    sy = int(15 * step_scale)
    # Soft multi-layer shadow
    for expand, alpha in [(4, 35), (2, 55), (0, 80)]:
        draw.ellipse(
            [origin_x - sx - expand, ground_y - sy - expand // 2,
             origin_x + sx + expand, ground_y + sy + expand // 2],
            fill=(8, 6, 3, alpha),
        )


# ── Text overlay ──────────────────────────────────────────────────────

def _draw_fate_text(
    img: Image.Image,
    fate_survived: bool,
    extinction_era: str,
    survival_note: str,
    alpha: float,
    extinction_note: str = "",
) -> Image.Image:
    from PIL import ImageFont

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_large = font_small = None
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Regular.otf",
    ]
    for fp in font_paths:
        try:
            font_large = ImageFont.truetype(fp, size=28 * SCALE)
            font_small = ImageFont.truetype(fp, size=16 * SCALE)
            break
        except Exception:
            pass
    if font_large is None:
        font_large = ImageFont.load_default()
        font_small = font_large

    text_alpha  = int(alpha * 220)
    panel_alpha = int(alpha * 145)

    if fate_survived:
        title       = "現代まで生存"
        sub         = survival_note
        title_color = (120, 240, 160, text_alpha)
        sub_color   = (200, 240, 200, text_alpha)
        panel_color = (10, 30, 15, panel_alpha)
    else:
        title       = f"{extinction_era}に絶命"
        sub         = extinction_note if extinction_note else "その痕跡は地層の中に眠る"
        title_color = (240, 160, 80, text_alpha)
        sub_color   = (200, 180, 150, text_alpha)
        panel_color = (30, 20, 10, panel_alpha)

    panel_y = int(RENDER_H * 0.75)
    panel_h = int(RENDER_H * 0.20)
    draw.rectangle([0, panel_y, RENDER_W, panel_y + panel_h], fill=panel_color)

    try:
        tw = draw.textlength(title, font=font_large)
    except Exception:
        tw = len(title) * 28 * SCALE
    tx = (RENDER_W - tw) // 2
    draw.text((tx, panel_y + 10 * SCALE), title, font=font_large, fill=title_color)

    try:
        sw = draw.textlength(sub, font=font_small)
    except Exception:
        sw = len(sub) * 16 * SCALE
    sx = (RENDER_W - sw) // 2
    draw.text((sx, panel_y + 50 * SCALE), sub, font=font_small, fill=sub_color)

    base = img.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


# ── Public API ────────────────────────────────────────────────────────

def render_frame(
    sentence: str,
    angle_deg: float,
    step_scale: float,
    stem_color: Tuple[int, int, int],
    leaf_color: Tuple[int, int, int],
    era: Era,
    moisture: float,
    base_step: float = 10.0,
    frame_idx: int = 0,
    sway_deg: float = 0.0,
    fate_progress: float = 0.0,
    fate_survived: bool | None = None,
    extinction_era: str = "",
    survival_note: str = "",
    extinction_note: str = "",
) -> np.ndarray:
    """Render one frame. Returns H×W×3 uint8 numpy array (RGB)."""
    bg, ground_y = _build_background(
        era, moisture, fate_progress, fate_survived, frame_idx
    )

    plant_layer  = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
    fx_layer     = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))

    step = max(0.5, base_step * step_scale * SCALE)
    start_width = max(1.0, step * 0.45)
    origin_x = RENDER_W // 2
    origin_y = ground_y

    _draw_shadow(shadow_layer, origin_x, ground_y, step_scale)

    pl = _render_plant_layer(
        (RENDER_W, RENDER_H), sentence, angle_deg, step, start_width,
        origin_x, origin_y, stem_color, leaf_color,
        frame_idx, fate_progress, fate_survived,
    )

    if abs(sway_deg) > 0.1:
        pl = pl.rotate(
            sway_deg,
            center=(origin_x, origin_y),
            expand=False,
            resample=Image.BICUBIC,
        )

    _draw_particles(fx_layer, era, frame_idx, origin_x, origin_y,
                    fate_progress, fate_survived)

    img = bg.convert("RGBA")
    img.alpha_composite(shadow_layer)
    img.alpha_composite(pl)
    img.alpha_composite(fx_layer)
    img = img.convert("RGB")

    if fate_survived is not None and fate_progress > 0.65:
        text_alpha = min(1.0, (fate_progress - 0.65) / 0.35)
        img = _draw_fate_text(
            img, fate_survived, extinction_era, survival_note, text_alpha,
            extinction_note=extinction_note,
        )

    # ── Cinematic vignette ────────────────────────────────────────────
    img = _apply_vignette(img, strength=0.52)

    return np.array(img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS))
