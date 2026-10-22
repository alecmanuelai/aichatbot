"""Shared colors and native desktop fonts for StudyBuddy."""

import sys

FONT = "Segoe UI" if sys.platform == "win32" else "Arial"
BG = "#0C121C"
SIDEBAR = "#111B28"
SURFACE = "#172332"
BORDER = "#29394B"
TEXT = "#E8EFF6"
MUTED = "#9AAFC2"
ACCENT = "#70DEC1"
ACCENT_HOVER = "#95E9D2"
INK = "#102C29"


def font(size=13, bold=False):
    return (FONT, size, "bold") if bold else (FONT, size)


PRIMARY = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=INK,
               text_color_disabled="#7C9296")
