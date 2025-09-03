import platform

# --- DPIぼけ対策（Windows優先） ---
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from .fontdb import FontDB
from .models import TelopStyle, TelopItem, SchedulePreset
from .editor import TelopEditor

__all__ = ["FontDB", "TelopStyle", "TelopItem", "SchedulePreset", "TelopEditor"]
