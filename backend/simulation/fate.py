"""
Determines whether a plant survives to modern times based on its parameters
and the environmental conditions it was adapted to.
"""
from __future__ import annotations

from dataclasses import dataclass
from .parameters import PlantJobRequest, Era


@dataclass
class PlantFate:
    survived: bool
    risk_score: float           # 0-1
    extinction_era: str         # e.g. "ペルム紀末" — empty if survived
    extinction_reason: str      # human-readable reason
    survival_note: str          # shown if survived


# When each era's plants were most vulnerable
_EXTINCTION_ERAS = [
    (0.90, "ハデアン末期の大衝突"),
    (0.78, "太古代末の全球凍結"),
    (0.66, "原生代末のスノーボールアース"),
    (0.55, "オルドビス紀末の大量絶滅"),
]

_ERA_CO2: dict[Era, float] = {
    Era.HADEAN:      1000.0,
    Era.ARCHEAN:     200.0,
    Era.PROTEROZOIC: 50.0,
    Era.CAMBRIAN:    15.0,
}

_MODERN_CO2 = 1.0  # baseline


def compute_fate(params: PlantJobRequest) -> PlantFate:
    """
    Heuristic fate calculation.
    Higher risk → more likely to go extinct before the modern era.
    """
    risk = 0.0
    reasons: list[str] = []

    # UV sensitivity: primordial plants exposed to extreme UV
    # have poor protective pigments for modern conditions
    uv_risk = params.uv_intensity * 0.30
    risk += uv_risk
    if uv_risk > 0.20:
        reasons.append("紫外線防御機構の未発達")

    # CO₂ dependency: high-CO₂ plants struggle as atmosphere changed
    co2_adapted = _ERA_CO2.get(params.era, 10.0)
    co2_gap = (params.co2_level - _MODERN_CO2) / max(1, co2_adapted)
    co2_risk = min(0.30, co2_gap * 0.30)
    risk += co2_risk
    if co2_risk > 0.12:
        reasons.append("CO₂濃度低下への適応失敗")

    # Extreme temperature: far from habitable range for modern life
    temp_risk = abs(params.temperature - 15.0) / 65.0 * 0.20
    risk += temp_risk
    if temp_risk > 0.10:
        reasons.append("気温変動への耐性不足")

    # Aridity: desert-adapted ancient plants often lost to wetter competition
    aridity_risk = (1.0 - params.moisture) * 0.20
    risk += aridity_risk
    if aridity_risk > 0.12:
        reasons.append("乾燥化への脆弱性")

    risk = min(risk, 1.0)

    if risk < 0.50:
        era_note = {
            Era.HADEAN:      "灼熱の地獄から生き延びた稀有な存在",
            Era.ARCHEAN:     "38億年の時を超えた適応の勝者",
            Era.PROTEROZOIC: "全球凍結を乗り越えた生命力",
            Era.CAMBRIAN:    "生命爆発の波に乗り現代まで繁栄",
        }.get(params.era, "現代まで生き延びた")

        return PlantFate(
            survived=True,
            risk_score=risk,
            extinction_era="",
            extinction_reason="",
            survival_note=era_note,
        )

    # Determine approximate extinction era
    ext_era = "白亜紀末の大量絶滅"
    for threshold, era_name in _EXTINCTION_ERAS:
        if risk >= threshold:
            ext_era = era_name
            break

    reason_str = "・".join(reasons) if reasons else "環境変化への適応失敗"

    return PlantFate(
        survived=False,
        risk_score=risk,
        extinction_era=ext_era,
        extinction_reason=reason_str,
        survival_note="",
    )
