"""
AI-powered narrative generator using Claude API (claude-opus-4-6).

Generates unique, scientifically-flavored survival/extinction descriptions
for each plant based on its parameters and environmental conditions.

Requires ANTHROPIC_API_KEY environment variable. Falls back gracefully
to the original rule-based text if the API is unavailable.
"""
from __future__ import annotations

import logging
import os

from .fate import PlantFate
from .parameters import Era, PlantJobRequest

logger = logging.getLogger(__name__)

_ERA_NAMES: dict[Era, str] = {
    Era.HADEAN:      "ハデアン代（46〜40億年前）",
    Era.ARCHEAN:     "太古代（40〜25億年前）",
    Era.PROTEROZOIC: "原生代（25〜5.4億年前）",
    Era.CAMBRIAN:    "カンブリア紀（5.4億年前）",
}

_PATTERN_NAMES: dict[str, str] = {
    "tree":   "樹木型",
    "bush":   "低木型",
    "fern":   "シダ型",
    "moss":   "コケ型",
    "spiral": "螺旋型",
}


def enhance_fate_narrative(params: PlantJobRequest, fate: PlantFate) -> PlantFate:
    """
    Use Claude to generate a unique narrative for this plant's fate.

    Returns an enhanced PlantFate with AI-generated text, or the original
    if ANTHROPIC_API_KEY is unset or the API call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return fate

    try:
        import anthropic  # optional dependency

        client = anthropic.Anthropic(api_key=api_key)

        era_name     = _ERA_NAMES.get(params.era, params.era.value)
        pattern_name = _PATTERN_NAMES.get(params.growth_pattern.value,
                                          params.growth_pattern.value)

        if fate.survived:
            prompt = (
                f"あなたは古植物学者です。{era_name}に生きた{pattern_name}の原始植物が"
                f"現代まで生存しました。\n"
                f"この植物の生存を讃える詩的かつ科学的なメッセージを"
                f"日本語で1文（35字以内）で書いてください。\n\n"
                f"環境条件: CO₂濃度 現代の{params.co2_level:.0f}倍、"
                f"UV強度 {params.uv_intensity:.1f}、"
                f"湿度 {params.moisture:.1f}、"
                f"温度 {params.temperature:.0f}°C\n"
                f"リスクスコア: {fate.risk_score:.2f}（低いほど適応力が高い）\n\n"
                f"メッセージのみを出力してください。"
            )
        else:
            prompt = (
                f"あなたは古植物学者です。{era_name}に生きた{pattern_name}の原始植物が"
                f"{fate.extinction_era}に絶命しました。\n"
                f"この絶命を詩的かつ科学的に表現するメッセージを"
                f"日本語で1文（35字以内）で書いてください。\n\n"
                f"絶命原因: {fate.extinction_reason}\n"
                f"リスクスコア: {fate.risk_score:.2f}\n\n"
                f"メッセージのみを出力してください。"
            )

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=150,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )

        ai_text = ""
        for block in response.content:
            if block.type == "text":
                ai_text = block.text.strip()
                break

        if not ai_text:
            return fate

        # Return fate with AI text replacing the narrative field
        if fate.survived:
            return PlantFate(
                survived=True,
                risk_score=fate.risk_score,
                extinction_era=fate.extinction_era,
                extinction_reason=fate.extinction_reason,
                survival_note=ai_text,
            )
        else:
            # For extinction, AI text goes into survival_note;
            # animator passes it as extinction_note to render_frame.
            return PlantFate(
                survived=False,
                risk_score=fate.risk_score,
                extinction_era=fate.extinction_era,
                extinction_reason=fate.extinction_reason,
                survival_note=ai_text,
            )

    except Exception as exc:
        logger.warning("AI narrator failed, using default text: %s", exc)
        return fate
