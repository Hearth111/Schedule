import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox, ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk
from typing import Optional, Tuple, List
import os
import datetime as dt
import json

from .models import TelopStyle, TelopItem, SchedulePreset
from .fontdb import FontDB

class TelopEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Schedule Image Builder — Rev2")
        try:
            # Tkの内部スケーリングを1.0に固定（DPIぼけ軽減）
            self.tk.call('tk', 'scaling', 1.0)
        except Exception:
            pass
        self.geometry("1220x760")
        self.minsize(1080, 680)

        # 状態
        self.base_image: Optional[Image.Image] = None
        self.base_image_path: Optional[str] = None
        self.preview_image: Optional[ImageTk.PhotoImage] = None
        self.preview_scale: float = 1.0
        self.style = TelopStyle()
        self.fontdb = FontDB()

        # モード: single / weekly
        self.mode_var = tk.StringVar(value="single")

        # 単一テロップ
        self.single_text = tk.StringVar(value="ここにテロップ\n(複数行可)")
        self.single_item: Optional[TelopItem] = None

        # 週次
        self.week_items: List[TelopItem] = []
        self.week_text_lines: List[str] = ["" for _ in range(7)]  # 一括入力(7行)
        today = dt.date.today()
        self.week_start = self._closest_monday(today)
        self.orientation_var = tk.StringVar(value="horizontal")  # horizontal / vertical
        self.margin_var = tk.IntVar(value=24)  # セル内余白

        # 選択中インデックス（ドラッグ対象）
        self.active_index: Optional[int] = None

        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # 左: キャンバス
        left = tk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(left, bg="#2f2f2f", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # 右: コントロール
        right = tk.Frame(self, padx=10, pady=10)
        right.grid(row=0, column=1, sticky="ns")

        # 画像
        tk.Label(right, text="画像").pack(anchor=tk.W)
        tk.Button(right, text="画像を開く…", command=self._open_image).pack(fill=tk.X)
        self.image_info = tk.Label(right, text="(未読み込み)", fg="#666")
        self.image_info.pack(anchor=tk.W, pady=(4, 10))

        # モード切替
        mode_row = tk.Frame(right)
        mode_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(mode_row, text="モード").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_row, text="単一", value="single", variable=self.mode_var, command=self._mode_changed).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(mode_row, text="週次(7)", value="weekly", variable=self.mode_var, command=self._mode_changed).pack(side=tk.LEFT)

        # テキスト（単一）
        self.single_box = tk.Text(right, width=36, height=7)
        self.single_box.insert("1.0", self.single_text.get())
        self.single_box.bind("<<Modified>>", self._on_single_modified)
        self.single_box.pack(fill=tk.X)

        # 週次パネル
        self.week_frame = tk.LabelFrame(right, text="週次設定")
        # 起点日付
        drow = tk.Frame(self.week_frame)
        drow.pack(fill=tk.X, pady=(6, 0))
        tk.Label(drow, text="起点(週の月曜日)").pack(side=tk.LEFT)
        self.y_var = tk.IntVar(value=self.week_start.year)
        self.m_var = tk.IntVar(value=self.week_start.month)
        self.d_var = tk.IntVar(value=self.week_start.day)
        tk.Spinbox(drow, from_=2000, to=2100, width=5, textvariable=self.y_var, command=self._week_date_changed).pack(side=tk.LEFT, padx=4)
        tk.Spinbox(drow, from_=1, to=12, width=3, textvariable=self.m_var, command=self._week_date_changed).pack(side=tk.LEFT)
        tk.Spinbox(drow, from_=1, to=31, width=3, textvariable=self.d_var, command=self._week_date_changed).pack(side=tk.LEFT)
        tk.Button(drow, text="直近の月曜", command=self._set_recent_monday).pack(side=tk.LEFT, padx=6)

        # 一括テキスト入力(7行)
        tk.Label(self.week_frame, text="各曜日の本文（上から月〜日、空欄は曜日+日付のみ）").pack(anchor=tk.W, pady=(6, 0))
        self.week_box = tk.Text(self.week_frame, width=36, height=7)
        self.week_box.bind("<<Modified>>", self._on_week_modified)
        self.week_box.pack(fill=tk.X)

        # レイアウト
        lrow = tk.Frame(self.week_frame)
        lrow.pack(fill=tk.X, pady=(6, 0))
        tk.Label(lrow, text="レイアウト").pack(side=tk.LEFT)
        ttk.Combobox(lrow, state="readonly", values=["横7列", "縦7行"], width=8,
                     textvariable=self.orientation_var,
                     postcommand=lambda: None).pack(side=tk.LEFT, padx=4)
        tk.Label(lrow, text="余白").pack(side=tk.LEFT)
        tk.Spinbox(lrow, from_=0, to=200, width=4, textvariable=self.margin_var, command=self._auto_layout_week).pack(side=tk.LEFT, padx=4)
        tk.Button(lrow, text="自動配置を再実行", command=self._auto_layout_week).pack(side=tk.LEFT, padx=6)

        # 週次パネルは初期は非表示（単一モード）
        # -> _mode_changedで切替

        # フォント周り
        tk.Label(right, text="フォント").pack(anchor=tk.W, pady=(10, 0))
        frow = tk.Frame(right)
        frow.pack(fill=tk.X)
        self.family_var = tk.StringVar(value=self.style.family or "")
        fams = self.fontdb.families() or ["(フォントを検出できません)"]
        self.family_box = ttk.Combobox(frow, values=fams, textvariable=self.family_var, state="readonly", width=26)
        self.family_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(frow, text="更新", command=self._refresh_font_list).pack(side=tk.LEFT, padx=4)

        # サイズ/色/縁/行間
        srow = tk.Frame(right)
        srow.pack(fill=tk.X, pady=(6, 0))
        tk.Label(srow, text="サイズ").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=self.style.font_size)
        tk.Spinbox(srow, from_=8, to=400, textvariable=self.size_var, width=6, command=self._refresh).pack(side=tk.LEFT, padx=6)

        crow = tk.Frame(right)
        crow.pack(fill=tk.X, pady=(4, 0))
        tk.Button(crow, text="テキスト色", command=self._choose_fill).pack(side=tk.LEFT)
        tk.Button(crow, text="縁色", command=self._choose_stroke).pack(side=tk.LEFT, padx=4)

        arow = tk.Frame(right)
        arow.pack(fill=tk.X, pady=(4, 0))
        tk.Label(arow, text="縁幅").pack(side=tk.LEFT)
        self.stroke_width_var = tk.IntVar(value=self.style.stroke_width)
        tk.Spinbox(arow, from_=0, to=32, width=4, textvariable=self.stroke_width_var, command=self._refresh).pack(side=tk.LEFT, padx=4)
        tk.Label(arow, text="行間").pack(side=tk.LEFT, padx=(6,0))
        self.ls_var = tk.IntVar(value=self.style.line_spacing)
        tk.Spinbox(arow, from_=0, to=200, width=5, textvariable=self.ls_var, command=self._refresh).pack(side=tk.LEFT, padx=4)

        # 位置リセット/保存
        tk.Button(right, text="位置を初期化", command=self._reset_positions).pack(fill=tk.X, pady=(10, 4))
        tk.Button(right, text="画像として保存…", command=self._export_image).pack(fill=tk.X)
        tk.Button(right, text="プリセット保存…", command=self._save_preset).pack(fill=tk.X, pady=(4,0))

        # ヒント
        hint = (
            "◆ 操作\n"
            "・キャンバス上でクリックすると対象テロップが選択され、ドラッグで移動できます。\n"
            "・週次モードは起点日(週の月曜)から日付/曜日を自動付与し、一括テキスト(7行)で内容を差し込みます。\n"
            "・プレビューは実描画と同品質（縁取り/行間反映）。"
        )
        tk.Label(right, text=hint, justify=tk.LEFT, fg="#666").pack(anchor=tk.W, pady=(8, 0))

        # 初期表示
        self._mode_changed()

    # ---------------- 画像入出力 ----------------
    def _open_image(self):
        path = filedialog.askopenfilename(
            title="ベース画像を選択",
            filetypes=[("Image", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All", "*.*")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("読み込みエラー", f"画像を開けませんでした\n{e}")
            return
        self.base_image = img
        self.base_image_path = path
        self.image_info.config(text=f"{os.path.basename(path)}  {img.width}×{img.height}")
        self._fit_preview()
        self._init_items_if_needed()
        self._refresh()

    def _export_image(self):
        if self.base_image is None:
            messagebox.showwarning("未読み込み", "まずベース画像を開いてください。")
            return
        if not self._ensure_font_path():
            messagebox.showwarning("フォント未選択", "フォントを選択してください。")
            return

        out = self.base_image.copy()
        draw = ImageDraw.Draw(out)
        font = ImageFont.truetype(self.style.font_path, size=int(self.size_var.get()))
        spacing = int(self.ls_var.get())
        stroke_w = int(self.stroke_width_var.get())

        items = self._get_items()
        for it in items:
            # プレビュー座標→実寸へ
            ox, oy = self._preview_to_image_xy(it.pos)
            draw.multiline_text(
                (ox, oy),
                it.text,
                font=font,
                fill=self.style.fill,
                spacing=spacing,
                align="left",
                stroke_width=stroke_w,
                stroke_fill=self.style.stroke_fill,
                anchor="nw",
            )

        suggested = self._suggest_filename()
        save_path = filedialog.asksaveasfilename(
            title="画像として保存",
            defaultextension=".png",
            initialfile=suggested,
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg"), ("WEBP", "*.webp"), ("All", "*.*")]
        )
        if not save_path:
            return
        try:
            out.save(save_path)
        except Exception as e:
            messagebox.showerror("保存エラー", f"保存に失敗しました\n{e}")
            return
        messagebox.showinfo("完了", "画像を保存しました。")

    def _save_preset(self):
        if self.base_image is None:
            messagebox.showwarning("未読み込み", "まずベース画像を開いてください。")
            return
        if self.mode_var.get() != "weekly":
            messagebox.showwarning("週次モードのみ", "プリセット保存は週次モードで使用します。")
            return
        if not self._ensure_font_path():
            messagebox.showwarning("フォント未選択", "フォントを選択してください。")
            return

        positions = [self._preview_to_image_xy(it.pos) for it in self.week_items]
        preset = SchedulePreset(
            base_image=self.base_image_path or "",
            style=TelopStyle(
                family=self.style.family,
                font_path=self.style.font_path,
                font_size=int(self.size_var.get()),
                fill=self.style.fill,
                stroke_fill=self.style.stroke_fill,
                stroke_width=int(self.stroke_width_var.get()),
                line_spacing=int(self.ls_var.get()),
            ),
            positions=positions,
        )
        save_path = filedialog.asksaveasfilename(
            title="プリセット保存",
            defaultextension=".vsc",
            filetypes=[("Preset", "*.vsc"), ("All", "*.*")],
        )
        if not save_path:
            return
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(preset.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存エラー", f"保存に失敗しました\n{e}")
            return
        messagebox.showinfo("完了", "プリセットを保存しました。")

    # ---------------- モード/テキスト ----------------
    def _mode_changed(self):
        if self.mode_var.get() == "single":
            self.week_frame.pack_forget()
            self.single_box.pack(fill=tk.X)
        else:
            self.single_box.pack_forget()
            self.week_frame.pack(fill=tk.X, pady=(4, 0))
        self._init_items_if_needed()
        self._refresh()

    def _on_single_modified(self, _evt=None):
        self.single_box.edit_modified(False)
        self.single_text.set(self.single_box.get("1.0", tk.END).rstrip("\n"))
        if self.single_item:
            self.single_item.text = self.single_text.get()
        self._refresh()

    def _on_week_modified(self, _evt=None):
        self.week_box.edit_modified(False)
        lines = self.week_box.get("1.0", tk.END).splitlines()
        self.week_text_lines = (lines + [""] * 7)[:7]
        self._regen_week_texts()
        self._refresh()

    # ---------------- フォント/色 ----------------
    def _refresh_font_list(self):
        self.fontdb = FontDB()
        fams = self.fontdb.families() or ["(なし)"]
        self.family_box["values"] = fams
        if fams and fams[0] != "(なし)":
            self.family_var.set(fams[0])
        self._ensure_font_path()
        self._refresh()

    def _ensure_font_path(self) -> bool:
        fam = self.family_var.get().strip()
        if not fam or fam.startswith("("):
            return False
        path = self.fontdb.get_path(fam)
        if not path:
            return False
        self.style.family = fam
        self.style.font_path = path
        return True

    def _choose_fill(self):
        c = colorchooser.askcolor(color=self.style.fill)[1]
        if c:
            self.style.fill = c
            self._refresh()

    def _choose_stroke(self):
        c = colorchooser.askcolor(color=self.style.stroke_fill)[1]
        if c:
            self.style.stroke_fill = c
            self._refresh()

    # ---------------- キャンバス関連 ----------------
    def _on_canvas_resize(self, _evt=None):
        self._fit_preview()
        self._auto_layout_week()  # サイズ変化時に再配置（週次）
        self._refresh()

    def _fit_preview(self):
        self.canvas.delete("all")
        if self.base_image is None:
            return
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        iw, ih = self.base_image.size
        scale = min(cw / iw, ch / ih)
        scale = max(0.01, min(1.0, scale))
        self.preview_scale = scale
        pw, ph = int(iw * scale), int(ih * scale)
        preview = self.base_image.resize((pw, ph), Image.LANCZOS)
        self._bgphoto = ImageTk.PhotoImage(preview)
        ox = (cw - pw) // 2
        oy = (ch - ph) // 2
        self.canvas.create_image(ox, oy, image=self._bgphoto, anchor="nw", tags=("img",))

    def _preview_to_image_xy(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        # 背景画像の左上オフセットを考慮し、プレビュー→実寸へ
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.base_image.size
        pw, ph = int(iw * self.preview_scale), int(ih * self.preview_scale)
        ox = (cw - pw) // 2
        oy = (ch - ph) // 2
        x = int((pos[0] - ox) / self.preview_scale)
        y = int((pos[1] - oy) / self.preview_scale)
        return x, y

    def _image_to_preview_xy(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.base_image.size
        pw, ph = int(iw * self.preview_scale), int(ih * self.preview_scale)
        ox = (cw - pw) // 2
        oy = (ch - ph) // 2
        x = int(pos[0] * self.preview_scale + ox)
        y = int(pos[1] * self.preview_scale + oy)
        return x, y

    def _refresh(self):
        if self.base_image is None:
            return
        # 既存テロップ描画をクリア
        self.canvas.delete("telop")

        # 各アイテムをPILで描いてからCanvasに貼る（品質重視）
        items = self._get_items()
        if not items:
            return
        # 準備: フォント
        if not self._ensure_font_path():
            # フォント未選択時はTk描画の簡易フォールバック
            for it in items:
                x, y = it.pos
                self.canvas.create_text(x, y, text=it.text or " ", fill=self.style.fill,
                                        font=("", max(8, int(self.size_var.get()*self.preview_scale))),
                                        anchor="nw", tags=("telop",))
            return

        try:
            psize = max(8, int(self.size_var.get() * self.preview_scale))
            font = ImageFont.truetype(self.style.font_path, size=psize)
        except Exception:
            # 失敗時は簡易フォールバック
            for it in items:
                x, y = it.pos
                self.canvas.create_text(x, y, text=it.text or " ", fill=self.style.fill,
                                        font=("", max(8, int(self.size_var.get()*self.preview_scale))),
                                        anchor="nw", tags=("telop",))
            return

        spacing = max(0, int(self.ls_var.get() * self.preview_scale))
        stroke_w = max(0, int(self.stroke_width_var.get() * self.preview_scale))

        for idx, it in enumerate(items):
            # テキストのサイズを取得
            text = it.text if it.text else " "
            bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).multiline_textbbox(
                (0, 0), text, font=font, spacing=spacing, align="left", stroke_width=stroke_w, anchor="nw")
            w = max(1, bbox[2] - bbox[0])
            h = max(1, bbox[3] - bbox[1])
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.multiline_text((0, 0), text, font=font, fill=self.style.fill, spacing=spacing,
                             align="left", stroke_width=stroke_w, stroke_fill=self.style.stroke_fill, anchor="nw")
            ph = ImageTk.PhotoImage(img)
            x, y = it.pos
            self.canvas.create_image(x, y, image=ph, anchor="nw", tags=("telop", f"telop_{idx}"))
            # 参照保持＆矩形更新
            setattr(self, f"_telop_photo_{idx}", ph)
            it.bbox = (x, y, x + w, y + h)

    # ------------- ドラッグ/選択 -------------
    def _hit_test(self, x: int, y: int) -> Optional[int]:
        items = self._get_items()
        for i, it in enumerate(items):
            x0, y0, x1, y1 = it.bbox
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        # 近い中心のもの
        best, bestd = None, 1e9
        for i, it in enumerate(items):
            cx = (it.bbox[0] + it.bbox[2]) / 2
            cy = (it.bbox[1] + it.bbox[3]) / 2
            d = (cx - x) ** 2 + (cy - y) ** 2
            if d < bestd:
                best, bestd = i, d
        return best

    def _on_mouse_down(self, evt):
        if not self.base_image:
            return
        self.active_index = self._hit_test(evt.x, evt.y)
        self._drag_offset = None
        if self.active_index is not None:
            it = self._get_items()[self.active_index]
            self._drag_offset = (evt.x - it.pos[0], evt.y - it.pos[1])

    def _on_mouse_drag(self, evt):
        if self.active_index is None or self._drag_offset is None:
            return
        dx, dy = self._drag_offset
        items = self._get_items()
        it = items[self.active_index]
        it.pos = (evt.x - dx, evt.y - dy)
        self._refresh()

    def _on_mouse_up(self, _evt):
        self._drag_offset = None

    # ------------- 週次レイアウト/日付 -------------
    def _closest_monday(self, day: dt.date) -> dt.date:
        return day - dt.timedelta(days=(day.weekday()))  # weekday: Mon=0

    def _set_recent_monday(self):
        self.week_start = self._closest_monday(dt.date.today())
        self.y_var.set(self.week_start.year)
        self.m_var.set(self.week_start.month)
        self.d_var.set(self.week_start.day)
        self._regen_week_texts()
        self._auto_layout_week()
        self._refresh()

    def _week_date_changed(self):
        try:
            self.week_start = dt.date(self.y_var.get(), self.m_var.get(), self.d_var.get())
        except Exception:
            return
        self._regen_week_texts()
        self._auto_layout_week()
        self._refresh()

    def _regen_week_texts(self):
        # 空欄なら「日付+曜日」を自動生成
        ja = ["月", "火", "水", "木", "金", "土", "日"]
        lines = self.week_text_lines
        items = self.week_items
        if not items:
            return
        for i in range(7):
            d = self.week_start + dt.timedelta(days=i)
            auto = f"{d.month}/{d.day}（{ja[i]}）"
            body = (lines[i] if i < len(lines) and lines[i].strip() else "")
            txt = auto if not body else f"{auto}\n{body}"
            items[i].text = txt

    def _auto_layout_week(self):
        if self.mode_var.get() != "weekly" or self.base_image is None:
            return
        # プレビュー上の画像矩形
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.base_image.size
        pw, ph = int(iw * self.preview_scale), int(ih * self.preview_scale)
        ox = (cw - pw) // 2
        oy = (ch - ph) // 2
        margin = int(self.margin_var.get())

        horiz = (self.orientation_var.get() == "horizontal")
        if horiz:
            cell_w = pw / 7
            y = oy + margin
            for i, it in enumerate(self.week_items):
                x = ox + int(i * cell_w) + margin
                it.pos = (x, y)
                it.auto_pos = it.pos
        else:
            cell_h = ph / 7
            x = ox + margin
            for i, it in enumerate(self.week_items):
                y = oy + int(i * cell_h) + margin
                it.pos = (x, y)
                it.auto_pos = it.pos

    # ------------- 共通ユーティリティ -------------
    def _reset_positions(self):
        if self.mode_var.get() == "single":
            if self.single_item:
                self.single_item.pos = self.single_item.auto_pos
        else:
            for it in self.week_items:
                it.pos = it.auto_pos
        self._refresh()

    def _init_items_if_needed(self):
        if self.base_image is None:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.base_image.size
        pw, ph = int(iw * self.preview_scale), int(ih * self.preview_scale)
        ox = (cw - pw) // 2
        oy = (ch - ph) // 2
        if self.mode_var.get() == "single":
            if not self.single_item:
                p = (ox + 24, oy + 24)
                self.single_item = TelopItem(text=self.single_text.get(), pos=p, auto_pos=p)
        else:
            if not self.week_items:
                ja = ["月", "火", "水", "木", "金", "土", "日"]
                today = self.week_start
                for i in range(7):
                    d = today + dt.timedelta(days=i)
                    txt = f"{d.month}/{d.day}（{ja[i]}）"
                    p = (ox + 24, oy + 24 + i * 40)
                    self.week_items.append(TelopItem(text=txt, pos=p, auto_pos=p))
                self._auto_layout_week()

    def _get_items(self) -> List[TelopItem]:
        return [self.single_item] if self.mode_var.get() == "single" and self.single_item else self.week_items

    def _suggest_filename(self) -> str:
        base = "output"
        if self.base_image_path:
            base = os.path.splitext(os.path.basename(self.base_image_path))[0]
        mode = self.mode_var.get()
        return f"{base}_{mode}.png"

