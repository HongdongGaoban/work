"""
PIL-based 2D renderer.

Renders at 2× resolution then LANCZOS-downsamples for smooth anti-aliasing.
Supports:
  - Era-specific primordial backgrounds with atmospheric haze
  - Tapering branch rendering with color variation
  - Floating particle effects (spores / volcanic ash)
  - Shadow at plant base
  - Fate overlay (extinction desaturation / survival brightening)
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
        "particle":   (200, 120, 40),   # volcanic ash
    },
    Era.ARCHEAN: {
        "sky_top":    ( 6, 16,  6),
        "sky_bottom": (16, 32, 16),
        "ground":     (42, 30, 13),
        "ground_tex": (25, 17,  7),
        "haze":       (28, 52, 28),
        "particle":   (180, 160, 60),   # organic spores
    },
    Era.PROTEROZOIC: {
        "sky_top":    ( 8,  8, 28),
        "sky_bottom": (20, 20, 52),
        "ground":     (36, 36, 20),
        "ground_tex": (20, 20, 10),
        "haze":       (42, 42, 88),
        "particle":   (160, 140, 200),  # purple spores
    },
    Era.CAMBRIAN: {
        "sky_top":    (12, 28, 52),
        "sky_bottom": (26, 52, 88),
        "ground":     (44, 50, 26),
        "ground_tex": (26, 30, 14),
        "haze":       (60, 88, 130),
        "particle":   (220, 200, 100),  # golden pollen
    },
}

# Modern sky for survival
MODERN_SKY_TOP    = (100, 160, 220)
MODERN_SKY_BOTTOM = (160, 210, 250)
MODERN_GROUND     = (60, 90, 40)
MODERN_HAZE       = (140, 190, 230)

# Extinction colours (desaturated, ashy)
EXTINCT_SKY_TOP    = (25, 20, 18)
EXTINCT_SKY_BOTTOM = (45, 35, 28)
EXTINCT_GROUND     = (55, 45, 35)


def _lerp(c1: Tuple, c2: Tuple, t: float) -> Tuple[int, ...]:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def _to_rgb(c: Tuple[int, ...]) -> Tuple[int, int, int]:
    return (int(c[0]), int(c[1]), int(c[2]))


# ── Background ────────────────────────────────────────────────────────

def _build_background(
    era: Era,
    moisture: float,
    fate_progress: float = 0.0,
    fate_survived: bool | None = None,
) -> Tuple[Image.Image, int]:
    """Return (RGB background image at RENDER size, ground_y)."""
    pal = ERA_PALETTE.get(era, ERA_PALETTE[Era.ARCHEAN])
    ground_y = int(RENDER_H * (1 - GROUND_RATIO))

    # Choose blended palette based on fate
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

    # Sky gradient
    for y in range(ground_y):
        t = y / ground_y
        draw.line([(0, y), (RENDER_W, y)], fill=_to_rgb(_lerp(sky_top, sky_bottom, t)))

    # Ground gradient
    for y in range(ground_y, RENDER_H):
        t = (y - ground_y) / (RENDER_H - ground_y)
        draw.line([(0, y), (RENDER_W, y)], fill=_to_rgb(_lerp(gnd, gnd_tex, t)))

    # Ground texture streaks
    rng = np.random.RandomState(42)
    for _ in range(200):
        x  = int(rng.uniform(0, RENDER_W))
        y  = int(rng.uniform(ground_y, RENDER_H - 4))
        x2 = x + int(rng.uniform(-20, 20))
        y2 = y + int(rng.uniform(0, 10))
        draw.line([(x, y), (x2, y2)], fill=_to_rgb(gnd_tex), width=1)

    # Horizon haze
    haze_h = 80
    haze_img = Image.new("RGBA", (RENDER_W, haze_h), (0, 0, 0, 0))
    haze_draw = ImageDraw.Draw(haze_img)
    for i in range(haze_h):
        alpha = int(140 * ((1 - i / haze_h) ** 2))
        haze_draw.line([(0, i), (RENDER_W, i)], fill=_to_rgb(haze) + (alpha,))
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(haze_img, dest=(0, ground_y - haze_h // 2))
    img = img_rgba.convert("RGB")

    # Volcanic glow (Hadean only, before extinction)
    if era == Era.HADEAN and (fate_progress < 0.5 or fate_survived):
        glow_strength = max(0, 1.0 - fate_progress * 2) if not fate_survived else 1.0
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
        for _ in range(20):
            x = int(rng.uniform(0, RENDER_W))
            y = int(rng.uniform(ground_y, ground_y + 30))
            w = int(rng.uniform(15, 60))
            glint = _lerp(gnd, (180, 200, 240), 0.35)
            ImageDraw.Draw(img).line(
                [(x, y), (x + w, y)], fill=_to_rgb(glint), width=1
            )

    # Survival: sun rays
    if fate_survived and fate_progress > 0.3:
        sun_alpha = int(fate_progress * 80)
        sun_layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        sun_d = ImageDraw.Draw(sun_layer)
        sun_x, sun_y = int(RENDER_W * 0.75), int(RENDER_H * 0.08)
        for angle_deg in range(0, 360, 18):
            rad = math.radians(angle_deg)
            r1, r2 = 30, 120 + int(40 * fate_progress)
            x1 = int(sun_x + r1 * math.cos(rad))
            y1 = int(sun_y + r1 * math.sin(rad))
            x2 = int(sun_x + r2 * math.cos(rad))
            y2 = int(sun_y + r2 * math.sin(rad))
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
        # Extinction: falling ash / sparks
        pc = _to_rgb(pal["particle"])
        for _ in range(25):
            x = int(rng.uniform(origin_x - 300, origin_x + 300))
            # Ash falls: starts high, moves down over time
            base_y = int(rng.uniform(-50, origin_y))
            y = (base_y + int(fate_progress * RENDER_H * 0.6)) % RENDER_H
            r = rng.randint(1, 3)
            alpha = rng.randint(60, 150)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=pc + (alpha,))
    else:
        # Normal: spores / pollen drifting upward
        pc = _to_rgb(pal["particle"])
        drift_y = (frame_idx * 3) % RENDER_H
        for _ in range(18):
            x = int(rng.gauss(origin_x, 180))
            y = int((rng.uniform(0, origin_y) - drift_y) % origin_y)
            r = rng.randint(1, 3)
            alpha = rng.randint(40, 120)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=pc + (alpha,))


# ── Plant ─────────────────────────────────────────────────────────────

def _blend_plant_colors(
    stem: Tuple, leaf: Tuple,
    fate_progress: float,
    fate_survived: bool | None,
) -> Tuple[Tuple, Tuple]:
    """Shift plant colours toward fate palette."""
    if fate_progress <= 0 or fate_survived is None:
        return stem, leaf

    t = fate_progress
    if fate_survived:
        # Brighter / greener modern plant
        modern_stem = (70, 55, 25)
        modern_leaf = (40, 180, 60)
        return _lerp(stem, modern_stem, t), _lerp(leaf, modern_leaf, t)
    else:
        # Dry / dead / fossilised
        dead_stem = (90, 72, 50)
        dead_leaf  = (80, 68, 45)
        fossil_stem = (100, 95, 88)
        fossil_leaf  = (105, 100, 92)
        if t < 0.5:
            # Drying out
            t2 = t * 2
            return _lerp(stem, dead_stem, t2), _lerp(leaf, dead_leaf, t2)
        else:
            # Fossilising
            t2 = (t - 0.5) * 2
            return _lerp(dead_stem, fossil_stem, t2), _lerp(dead_leaf, fossil_leaf, t2)


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
    """Render stems + leaves onto a transparent RGBA layer."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    eff_stem, eff_leaf = _blend_plant_colors(
        stem_color, leaf_color, fate_progress, fate_survived
    )

    segments, leaves = get_turtle_path(sentence, angle_deg, step, start_width)

    # Colour noise seed per frame (but consistent within one frame)
    noise_rng = random.Random(frame_idx * 31 + 7)

    # Draw stems (deepest first so trunk is below branches)
    for seg in sorted(segments, key=lambda s: -s[5]):
        x1, y1, x2, y2, w, depth = seg
        px1, py1 = int(origin_x + x1), int(origin_y - y1)
        px2, py2 = int(origin_x + x2), int(origin_y - y2)

        # Colour: slightly brighter toward tips + random noise
        tip_t = min(depth / 6.0, 1.0)
        noise = noise_rng.randint(-12, 12)
        base = _lerp(eff_stem, tuple(min(255, c + 30) for c in eff_stem), tip_t)
        color = tuple(max(0, min(255, base[i] + noise)) for i in range(3))

        # Opacity reduces as plant fossilises
        opacity = 220
        if fate_survived is False and fate_progress > 0.6:
            opacity = int(220 * (1.0 - (fate_progress - 0.6) / 0.4 * 0.5))

        lw = max(1, int(w))
        draw.line([(px1, py1), (px2, py2)], fill=color + (opacity,), width=lw)

        # Bark texture: secondary thin line slightly offset for thick segments
        if lw >= 4:
            off = max(1, lw // 3)
            dark = tuple(max(0, c - 20) for c in color)
            draw.line(
                [(px1 + off, py1), (px2 + off, py2)],
                fill=dark + (int(opacity * 0.5),), width=1
            )

    # Draw leaves
    leaf_r = max(3, int(step * 0.55))
    leaf_opacity = 190
    if fate_survived is False and fate_progress > 0.3:
        leaf_opacity = int(190 * max(0, 1.0 - (fate_progress - 0.3) / 0.4))

    for lx, ly, la, depth in leaves:
        px = int(origin_x + lx)
        py = int(origin_y - ly)
        if -leaf_r <= px <= size[0] + leaf_r and -leaf_r <= py <= size[1] + leaf_r:
            tip_t = min(depth / 9.0, 1.0)
            noise = noise_rng.randint(-8, 8)
            base = _lerp(eff_leaf, tuple(min(255, c + 35) for c in eff_leaf), tip_t)
            lc = tuple(max(0, min(255, base[i] + noise)) for i in range(3))

            # Slightly elongated ellipse
            rx, ry = leaf_r, max(2, int(leaf_r * 0.55))
            draw.ellipse([px - rx, py - ry, px + rx, py + ry],
                         fill=lc + (leaf_opacity,))

    return layer


# ── Shadow ────────────────────────────────────────────────────────────

def _draw_shadow(
    layer: Image.Image,
    origin_x: int,
    ground_y: int,
    step_scale: float,
) -> None:
    draw = ImageDraw.Draw(layer)
    sx = int(80 * step_scale)
    sy = int(14 * step_scale)
    draw.ellipse(
        [origin_x - sx, ground_y - sy, origin_x + sx, ground_y + sy],
        fill=(10, 8, 4, 80),
    )


# ── Text overlay ──────────────────────────────────────────────────────

def _draw_fate_text(
    img: Image.Image,
    fate_survived: bool,
    extinction_era: str,
    survival_note: str,
    alpha: float,
) -> Image.Image:
    """Draw fate message in the lower portion of the image."""
    from PIL import ImageFont

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Try to load a CJK font; fall back to default
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

    text_alpha = int(alpha * 220)
    panel_alpha = int(alpha * 140)

    if fate_survived:
        title = "現代まで生存"
        sub   = survival_note
        title_color = (120, 240, 160, text_alpha)
        sub_color   = (200, 240, 200, text_alpha)
        panel_color = (10, 30, 15, panel_alpha)
    else:
        title = f"{extinction_era}に絶命"
        sub   = "その痕跡は地層の中に眠る"
        title_color = (240, 160, 80, text_alpha)
        sub_color   = (200, 180, 150, text_alpha)
        panel_color = (30, 20, 10, panel_alpha)

    # Background panel
    panel_y = int(RENDER_H * 0.75)
    panel_h = int(RENDER_H * 0.20)
    draw.rectangle([0, panel_y, RENDER_W, panel_y + panel_h], fill=panel_color)

    # Title
    try:
        tw = draw.textlength(title, font=font_large)
    except Exception:
        tw = len(title) * 28 * SCALE
    tx = (RENDER_W - tw) // 2
    draw.text((tx, panel_y + 10 * SCALE), title, font=font_large, fill=title_color)

    # Sub
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
) -> np.ndarray:
    """
    Render one frame. Returns H×W×3 uint8 numpy array (RGB).
    """
    bg, ground_y = _build_background(era, moisture, fate_progress, fate_survived)

    plant_layer  = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
    fx_layer     = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))

    step = max(0.5, base_step * step_scale * SCALE)
    start_width = max(1.0, step * 0.45)
    origin_x = RENDER_W // 2
    origin_y = ground_y

    # Shadow
    _draw_shadow(shadow_layer, origin_x, ground_y, step_scale)

    # Plant
    pl = _render_plant_layer(
        (RENDER_W, RENDER_H), sentence, angle_deg, step, start_width,
        origin_x, origin_y, stem_color, leaf_color,
        frame_idx, fate_progress, fate_survived,
    )

    # Sway: rotate plant layer around base point
    if abs(sway_deg) > 0.1:
        pl = pl.rotate(
            sway_deg,
            center=(origin_x, origin_y),
            expand=False,
            resample=Image.BICUBIC,
        )

    # Particles
    _draw_particles(fx_layer, era, frame_idx, origin_x, origin_y,
                    fate_progress, fate_survived)

    # Composite
    img = bg.convert("RGBA")
    img.alpha_composite(shadow_layer)
    img.alpha_composite(pl)
    img.alpha_composite(fx_layer)
    img = img.convert("RGB")

    # Fate text overlay (fade in during last quarter of fate phase)
    if fate_survived is not None and fate_progress > 0.65:
        text_alpha = min(1.0, (fate_progress - 0.65) / 0.35)
        img = _draw_fate_text(
            img, fate_survived, extinction_era, survival_note, text_alpha
        )

    # Downscale with anti-aliasing
    return np.array(img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS))
