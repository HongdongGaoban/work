from pydantic import BaseModel, Field
from typing import Tuple
from enum import Enum


class GrowthPattern(str, Enum):
    TREE = "tree"
    BUSH = "bush"
    FERN = "fern"
    MOSS = "moss"
    SPIRAL = "spiral"


class Era(str, Enum):
    HADEAN = "hadean"            # 46-40億年前: 灼熱・溶岩
    ARCHEAN = "archean"          # 40-25億年前: メタン大気・最初の生命
    PROTEROZOIC = "proterozoic"  # 25-5.4億年前: 酸素蓄積
    CAMBRIAN = "cambrian"        # 5.4億年前: 生命爆発


class PlantJobRequest(BaseModel):
    name: str = Field(default="謎の原始植物")
    description: str = Field(default="")
    growth_pattern: GrowthPattern = GrowthPattern.FERN
    branch_angle: float = Field(default=25.0, ge=5.0, le=60.0)
    iterations: int = Field(default=4, ge=1, le=6)
    stem_color: Tuple[int, int, int] = Field(default=(90, 55, 20))   # RGB 0-255
    leaf_color: Tuple[int, int, int] = Field(default=(25, 130, 50))  # RGB 0-255
    era: Era = Era.ARCHEAN
    co2_level: float = Field(default=10.0, ge=1.0, le=100.0)
    uv_intensity: float = Field(default=0.8, ge=0.0, le=1.0)
    moisture: float = Field(default=0.5, ge=0.0, le=1.0)
    temperature: float = Field(default=40.0, ge=0.0, le=80.0)
    duration: int = Field(default=10, ge=5, le=30)
    fps: int = Field(default=24, ge=12, le=30)
