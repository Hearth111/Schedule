from dataclasses import dataclass
from typing import Optional, Tuple


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
