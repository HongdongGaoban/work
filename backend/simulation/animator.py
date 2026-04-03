"""
Three-phase animation:
  Phase 1 (0 → 65%): Plant grows from seedling to full size
  Phase 2 (65 → 78%): Mature plant sways gently
  Phase 3 (78 → 100%): Fate reveal (extinction or survival)
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import imageio.v2 as imageio

from .parameters import PlantJobRequest
from .lsystem import generate_sentences
from .renderer import render_frame, CANVAS_W, CANVAS_H
from .fate import compute_fate


def _compute_base_step(max_iter: int) -> float:
    target_h = 380.0
    approx = max(1, 2 ** max_iter)
    return max(4.0, min(22.0, target_h / (approx ** 0.65)))


def generate_video(
    params: PlantJobRequest,
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    total_frames = params.duration * params.fps

    sentences, angle = generate_sentences(
        params.growth_pattern,
        params.iterations,
        params.branch_angle,
    )
    max_iter = len(sentences) - 1
    base_step = _compute_base_step(max_iter)

    stem_color = tuple(params.stem_color)
    leaf_color = tuple(params.leaf_color)

    fate = compute_fate(params)

    # ── Phase boundaries ────────────────────────────────────────────
    PHASE1_END = 0.65   # growth
    PHASE2_END = 0.78   # mature sway
    # phase 3 is PHASE2_END → 1.0: fate reveal

    writer = imageio.get_writer(
        output_path,
        fps=params.fps,
        codec="libx264",
        quality=7,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )

    try:
        for i in range(total_frames):
            global_t = i / total_frames  # 0 → 1

            # ── Phase 1: Growth ──────────────────────────────────────
            if global_t <= PHASE1_END:
                phase_t = global_t / PHASE1_END        # 0 → 1

                eased = math.pow(phase_t, 0.65)
                iter_f = eased * max_iter
                iter_idx = min(int(iter_f), max_iter)
                sub = iter_f - iter_idx

                sentence = sentences[iter_idx]

                if max_iter > 0:
                    coarse = iter_idx / max_iter
                    fine = sub / max_iter if iter_idx < max_iter else 1.0
                    step_scale = max(0.05, coarse * 0.85 + fine * 0.15)
                else:
                    step_scale = max(0.05, phase_t)

                frame = render_frame(
                    sentence=sentence,
                    angle_deg=angle,
                    step_scale=step_scale,
                    stem_color=stem_color,
                    leaf_color=leaf_color,
                    era=params.era,
                    moisture=params.moisture,
                    base_step=base_step,
                    frame_idx=i,
                    sway_deg=0.0,
                    fate_progress=0.0,
                    fate_survived=None,
                )

            # ── Phase 2: Mature sway ─────────────────────────────────
            elif global_t <= PHASE2_END:
                sentence = sentences[max_iter]
                # Sway: ±2.5° sine wave, 2-second period
                t_sec = i / params.fps
                sway = 2.5 * math.sin(t_sec * math.pi)

                frame = render_frame(
                    sentence=sentence,
                    angle_deg=angle,
                    step_scale=1.0,
                    stem_color=stem_color,
                    leaf_color=leaf_color,
                    era=params.era,
                    moisture=params.moisture,
                    base_step=base_step,
                    frame_idx=i,
                    sway_deg=sway,
                    fate_progress=0.0,
                    fate_survived=None,
                )

            # ── Phase 3: Fate reveal ─────────────────────────────────
            else:
                sentence = sentences[max_iter]
                phase_t = (global_t - PHASE2_END) / (1.0 - PHASE2_END)  # 0 → 1

                # Sway fades out as fate takes over
                t_sec = i / params.fps
                sway = 2.5 * math.sin(t_sec * math.pi) * max(0, 1.0 - phase_t * 2)

                frame = render_frame(
                    sentence=sentence,
                    angle_deg=angle,
                    step_scale=1.0,
                    stem_color=stem_color,
                    leaf_color=leaf_color,
                    era=params.era,
                    moisture=params.moisture,
                    base_step=base_step,
                    frame_idx=i,
                    sway_deg=sway,
                    fate_progress=phase_t,
                    fate_survived=fate.survived,
                    extinction_era=fate.extinction_era,
                    survival_note=fate.survival_note,
                )

            writer.append_data(frame)

            if progress_callback:
                progress_callback(global_t * 0.95)

    finally:
        writer.close()

    if progress_callback:
        progress_callback(1.0)

    return output_path
