from typing import Optional, List, Dict
import os
import platform


class FontDB:
    """フォントファミリ名とファイルパスの対応を構築する簡易DB"""

    def __init__(self) -> None:
        self.family_to_paths: Dict[str, List[str]] = {}
        self._build()

    def _build(self) -> None:
        # 1) matplotlib の FontManager があれば使う（推奨）
        try:
            from matplotlib import font_manager as fm  # type: ignore
            fmgr = fm.fontManager
            for fe in fmgr.ttflist:
                name = getattr(fe, "name", None) or getattr(fe, "family", None)
                path = getattr(fe, "fname", None)
                if not name or not path:
                    continue
                self.family_to_paths.setdefault(name, []).append(path)
            if self.family_to_paths:
                return
        except Exception:
            pass
        # 2) フォールバック: 代表的なフォントディレクトリを走査
        search_dirs = []
        sysname = platform.system()
        if sysname == "Windows":
            windir = os.environ.get("WINDIR", r"C:\\Windows")
            search_dirs.append(os.path.join(windir, "Fonts"))
        elif sysname == "Darwin":
            search_dirs += [
                "/System/Library/Fonts",
                "/Library/Fonts",
                os.path.expanduser("~/Library/Fonts"),
            ]
        else:
            search_dirs += [
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.local/share/fonts"),
                os.path.expanduser("~/.fonts"),
            ]
        exts = {".ttf", ".otf", ".ttc"}
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for root, _dirs, files in os.walk(d):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in exts:
                        path = os.path.join(root, f)
                        # 簡易的にファイル名から推定
                        family = os.path.splitext(f)[0]
                        self.family_to_paths.setdefault(family, []).append(path)

    def families(self) -> List[str]:
        return sorted(self.family_to_paths.keys(), key=str.casefold)

    def get_path(self, family: str) -> Optional[str]:
        # Regular/Book/Medium 優先
        prefs = ["Regular", "Book", "Medium", "Normal", "400", "Demilight", "Roman"]
        paths = self.family_to_paths.get(family, [])
        if not paths:
            return None
        for p in paths:
            base = os.path.basename(p)
            if any(tag.lower() in base.lower() for tag in prefs):
                return p
        return paths[0]
