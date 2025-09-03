import json
import argparse
import datetime as dt
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from schedule.models import SchedulePreset

def load_preset(path: str) -> SchedulePreset:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SchedulePreset.from_dict(data)

def main():
    parser = argparse.ArgumentParser(description="7つのテキストを入力して予定表画像を生成")
    parser.add_argument("preset", help=".vscプリセットファイル")
    parser.add_argument("output", help="出力画像パス")
    args = parser.parse_args()

    preset = load_preset(args.preset)
    lines = []
    print("各曜日の本文を入力してください（空欄可）:")
    for i in range(7):
        line = input(f"{i+1}: ")
        lines.append(line.rstrip("\n"))

    tz = ZoneInfo("Asia/Tokyo")
    today = dt.datetime.now(tz).date()
    monday = today - dt.timedelta(days=today.weekday())
    ja = ["月", "火", "水", "木", "金", "土", "日"]

    base = Image.open(preset.base_image).convert("RGBA")
    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype(preset.style.font_path, preset.style.font_size)
    for i, pos in enumerate(preset.positions):
        d = monday + dt.timedelta(days=i)
        auto = f"{d.month}/{d.day}（{ja[i]}）"
        body = lines[i].strip()
        text = auto if not body else f"{auto}\n{body}"
        draw.multiline_text(
            pos,
            text,
            font=font,
            fill=preset.style.fill,
            spacing=preset.style.line_spacing,
            stroke_width=preset.style.stroke_width,
            stroke_fill=preset.style.stroke_fill,
            align="left",
            anchor="nw",
        )
    base.save(args.output)
    print("saved", args.output)

if __name__ == "__main__":
    main()
