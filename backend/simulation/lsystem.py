import math
import random
from typing import Dict, List, Tuple
from .parameters import GrowthPattern


# -------------------------------------------------------------------
# L-System production rules
# -------------------------------------------------------------------
PRESETS: Dict[GrowthPattern, dict] = {
    GrowthPattern.TREE: {
        "axiom": "FX",
        "rules": {"X": "[-FX][+FX]FX", "F": "FF"},
        "default_angle": 25.0,
        "max_iterations": 5,
    },
    GrowthPattern.BUSH: {
        "axiom": "F",
        "rules": {"F": "FF+[+F-F-F]-[-F+F+F]"},
        "default_angle": 22.5,
        "max_iterations": 4,
    },
    GrowthPattern.FERN: {
        "axiom": "X",
        "rules": {"X": "F+[[X]-X]-F[-FX]+X", "F": "FF"},
        "default_angle": 25.0,
        "max_iterations": 5,
    },
    GrowthPattern.MOSS: {
        "axiom": "F",
        "rules": {"F": "FF-[-F+F+F]+[+F-F-F]"},
        "default_angle": 22.5,
        "max_iterations": 3,
    },
    GrowthPattern.SPIRAL: {
        "axiom": "F",
        "rules": {"F": "F[+FF][-FF]F[-F][+F]F"},
        "default_angle": 20.0,
        "max_iterations": 4,
    },
}


def _apply_rules(sentence: str, rules: Dict[str, str]) -> str:
    return "".join(rules.get(ch, ch) for ch in sentence)


def generate_sentences(
    pattern: GrowthPattern,
    iterations: int,
    branch_angle: float,
) -> Tuple[List[str], float]:
    """
    Iteratively apply L-System rules up to `iterations` times.
    Returns list of sentences [iter0, iter1, ... iterN] and the effective angle.
    """
    preset = PRESETS[pattern]
    max_iter = min(iterations, preset["max_iterations"])
    angle = branch_angle if branch_angle > 0 else preset["default_angle"]

    sentences = [preset["axiom"]]
    sentence = preset["axiom"]
    for _ in range(max_iter):
        sentence = _apply_rules(sentence, preset["rules"])
        sentences.append(sentence)

    return sentences, angle


def get_turtle_path(
    sentence: str,
    angle_deg: float,
    step: float,
    start_width: float,
    angle_noise: float = 0.0,
    seed: int = 0,
) -> Tuple[List[Tuple], List[Tuple]]:
    """
    Interpret L-System sentence as turtle graphics.

    Returns:
        segments : list of (x1, y1, x2, y2, width, depth)
        leaves   : list of (x, y, angle_deg, depth)

    angle_noise adds organic randomness (±degrees) to each branch rotation.
    seed makes the noise reproducible per plant.
    """
    stack = []
    x, y = 0.0, 0.0
    direction = 90.0  # pointing upward
    width = start_width
    depth = 0
    _rng = random.Random(seed)

    segments: List[Tuple] = []
    leaves: List[Tuple] = []

    for ch in sentence:
        if ch == "F":
            nx = x + step * math.cos(math.radians(direction))
            ny = y + step * math.sin(math.radians(direction))
            segments.append((x, y, nx, ny, max(0.5, width), depth))
            x, y = nx, ny
        elif ch == "f":
            x += step * math.cos(math.radians(direction))
            y += step * math.sin(math.radians(direction))
        elif ch == "+":
            jitter = _rng.uniform(-angle_noise, angle_noise) if angle_noise > 0 else 0.0
            direction += angle_deg + jitter
        elif ch == "-":
            jitter = _rng.uniform(-angle_noise, angle_noise) if angle_noise > 0 else 0.0
            direction -= angle_deg + jitter
        elif ch == "[":
            stack.append((x, y, direction, width, depth))
            width = max(0.5, width * 0.65)
            depth += 1
        elif ch == "]":
            if stack:
                leaves.append((x, y, direction, depth))
                x, y, direction, width, depth = stack.pop()

    return segments, leaves
