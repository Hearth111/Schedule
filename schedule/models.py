from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List, Dict


@dataclass
class TelopStyle:
    family: Optional[str] = None  # フォントファミリ名
    font_path: Optional[str] = None  # 実際に読み込むパス
    font_size: int = 72
    fill: str = "#ffffff"
    stroke_fill: str = "#000000"
    stroke_width: int = 2
    line_spacing: int = 8


@dataclass
class TelopItem:
    text: str
    pos: Tuple[int, int]  # プレビュー座標
    auto_pos: Tuple[int, int]  # 自動配置の基準（リセット用）
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # プレビュー上の描画矩形(x0,y0,x1,y1)


@dataclass
class SchedulePreset:
    """週次予定表作成用のプリセット情報"""

    base_image: str
    style: TelopStyle
    positions: List[Tuple[int, int]]  # 各曜日テロップの描画開始座標(画像座標)

    def to_dict(self) -> Dict:
        return {
            "base_image": self.base_image,
            "style": asdict(self.style),
            "positions": [list(p) for p in self.positions],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SchedulePreset":
        style = TelopStyle(**data.get("style", {}))
        positions = [tuple(p) for p in data.get("positions", [])]
        return cls(base_image=data.get("base_image", ""), style=style, positions=positions)
