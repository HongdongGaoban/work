"""
Generates an MP4 video of plant growth by:
  1. Pre-computing L-System sentences per iteration stage.
  2. Rendering frames via PIL renderer.
  3. Encoding to MP4 via imageio + imageio-ffmpeg (bundled ffmpeg).
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import imageio.v2 as imageio

from .parameters import PlantJobRequest
from .lsystem import generate_sentences
from .renderer import render_frame, CANVAS_W, CANVAS_H


def _compute_base_step(max_iter: int) -> float:
    """Heuristic step size so the tallest plant fits in ~380px."""
    target_h = 380.0
    # Each F-iteration roughly doubles tree height
    approx_segments = max(1, 2 ** max_iter)
    step = target_h / (approx_segments ** 0.65)
    return max(4.0, min(22.0, step))


def generate_video(
    params: PlantJobRequest,
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """
    Render all frames and encode to MP4 at `output_path`.
    Returns `output_path` when done.
    """
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
            progress = i / total_frames  # 0 → 1

            # -----------------------------------------------------------
            # Map progress → iteration index + within-iter scale
            # Use eased progress so early growth is slower (more organic)
            # -----------------------------------------------------------
            eased = math.pow(progress, 0.65)
            iter_f = eased * max_iter
            iter_idx = min(int(iter_f), max_iter)
            sub = iter_f - iter_idx  # 0..1 within this iteration

            sentence = sentences[iter_idx]

            # Step scale: tiny seedling → full size
            if max_iter > 0:
                coarse = iter_idx / max_iter
                fine = sub / max_iter if iter_idx < max_iter else 1.0
                step_scale = max(0.05, coarse * 0.85 + fine * 0.15)
            else:
                step_scale = max(0.05, progress)

            frame = render_frame(
                sentence=sentence,
                angle_deg=angle,
                step_scale=step_scale,
                stem_color=stem_color,
                leaf_color=leaf_color,
                era=params.era,
                moisture=params.moisture,
                base_step=base_step,
            )

            writer.append_data(frame)

            if progress_callback:
                progress_callback(i / total_frames * 0.95)

    finally:
        writer.close()

    if progress_callback:
        progress_callback(1.0)

    return output_path
