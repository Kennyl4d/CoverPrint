#!/usr/bin/env python3
"""CoverPrint for Windows — feature parity with the GTK/Flatpak edition."""
import importlib.util
import locale
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QIcon, QPalette, QColor, QPixmap, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QPushButton, QListView, QAbstractItemView, QScrollArea, QVBoxLayout,
    QWidget, QStyleFactory,
)

VERSION = "1.1.0"
MM_TO_PT = 72.0 / 25.4
PRESETS = {
    "DVD standard (273 × 183 mm)": (273, 183),
    "DVD slim (266 × 183 mm)": (266, 183),
    "Blu-ray 12 mm (264 × 148 mm)": (264, 148),
    "Blu-ray 14 mm (266 × 148 mm)": (266, 148),
    "Blu-ray 5 mm (257 × 148 mm)": (257, 148),
}

def resource_path(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name

def load_translations():
    path = resource_path("translations.py")
    spec = importlib.util.spec_from_file_location("coverprint_translations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TRANSLATIONS

TRANSLATIONS = load_translations()

def system_language():
    # Windows has its own per-user display language preferences. Python's
    # locale.getlocale() may report the regional format rather than the UI
    # language (or fall back to en_US in frozen applications).
    raw = ""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_languages = kernel32.GetUserPreferredUILanguages
            get_languages.argtypes = [
                wintypes.DWORD, ctypes.POINTER(wintypes.ULONG),
                wintypes.LPWSTR, ctypes.POINTER(wintypes.ULONG),
            ]
            get_languages.restype = wintypes.BOOL
            count = wintypes.ULONG(0)
            length = wintypes.ULONG(0)
            # MUI_LANGUAGE_NAME = 0x8: return BCP-47 names, ordered by preference.
            if get_languages(0x8, ctypes.byref(count), None, ctypes.byref(length)) and length.value:
                buffer = ctypes.create_unicode_buffer(length.value)
                if get_languages(0x8, ctypes.byref(count), buffer, ctypes.byref(length)):
                    raw = buffer.value
        except (OSError, AttributeError, ValueError):
            pass
        if not raw:
            try:
                buffer = ctypes.create_unicode_buffer(85)
                if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
                    raw = buffer.value
            except (OSError, AttributeError, ValueError, NameError):
                pass
    if not raw:
        raw = (os.environ.get("LANGUAGE", "").split(":")[0]
               or os.environ.get("LC_ALL")
               or os.environ.get("LC_MESSAGES")
               or locale.getlocale()[0]
               or "en")
    code = raw.split(".")[0].replace("-", "_").lower()
    if code.startswith("zh"):
        return "zh_TW" if any(p in code for p in ("tw", "hk", "hant")) else "zh_CN"
    if code.startswith("pt"):
        return "pt_BR"
    return code.split("_")[0]

LANGUAGE = system_language()

def tr(message):
    return TRANSLATIONS.get(LANGUAGE, {}).get(message, message)

def export_pdf(image_path, output_path, size, fit_mode, crop_marks):
    wmm, hmm = size
    pw, ph = 297 * MM_TO_PT, 210 * MM_TO_PT
    w, h = wmm * MM_TO_PT, hmm * MM_TO_PT
    x, y = (pw - w) / 2, (ph - h) / 2
    with Image.open(image_path) as original:
        # Respect JPEG EXIF orientation; normalize modes for PDF.
        img = ImageOps.exif_transpose(original).convert("RGB")
        iw, ih = img.size
        if not iw or not ih:
            raise ValueError("Invalid image dimensions")
        if fit_mode == 0:
            dw, dh = w, h
        else:
            scale = min(w / iw, h / ih) if fit_mode == 1 else max(w / iw, h / ih)
            dw, dh = iw * scale, ih * scale
        dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
        pdf = canvas.Canvas(str(output_path), pagesize=(pw, ph), pageCompression=1)
        pdf.setTitle("CoverPrint")
        pdf.setFillColorRGB(1, 1, 1)
        pdf.rect(0, 0, pw, ph, stroke=0, fill=1)
        pdf.saveState()
        clip = pdf.beginPath()
        clip.rect(x, y, w, h)
        pdf.clipPath(clip, stroke=0, fill=0)
        pdf.drawImage(ImageReader(img), dx, dy, dw, dh)
        pdf.restoreState()
        if crop_marks:
            pdf.setStrokeColorRGB(0, 0, 0)
            pdf.setLineWidth(.35)
            gap, length = 4 * MM_TO_PT, 5 * MM_TO_PT
            for cx in (x, x + w):
                for cy in (y, y + h):
                    sx = -1 if cx == x else 1
                    sy = -1 if cy == y else 1
                    pdf.line(cx + sx * gap, cy, cx + sx * (gap + length), cy)
                    pdf.line(cx, cy + sy * gap, cx, cy + sy * (gap + length))
        pdf.showPage()
        pdf.save()


class ModernComboBox(QComboBox):
    """Paint a crisp chevron instead of the platform's small arrow glyph."""
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        if not self.isEnabled():
            color.setAlpha(100)
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx, cy = self.width() - 18, self.height() / 2
        from PySide6.QtCore import QPointF
        painter.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        painter.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))
        painter.end()


class VisibleCheckBox(QCheckBox):
    """Render an unambiguous tick on top of the styled checkbox indicator."""
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return
        from PySide6.QtWidgets import QStyle, QStyleOptionButton
        from PySide6.QtCore import QPointF
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#ffffff"), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx, cy = rect.center().x(), rect.center().y()
        painter.drawLine(QPointF(cx - 5, cy), QPointF(cx - 1.5, cy + 3.5))
        painter.drawLine(QPointF(cx - 1.5, cy + 3.5), QPointF(cx + 5.5, cy - 4))
        painter.end()


class CoverPrintWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.settings = QSettings("Kennyl4d", "CoverPrint")
        self.setWindowTitle("CoverPrint")
        self.resize(680, 720)
        icon_path = resource_path("coverprint.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("CoverPrint — " + tr("Print-ready covers"))
        font = title.font()
        font.setPointSize(15)
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)
        title_row.addStretch()
        menu_button = QPushButton("☰")
        menu_button.setFixedWidth(44)
        menu = QMenu(self)
        appearance = menu.addMenu(tr("Appearance"))
        for value, label in (("system", "Follow system"), ("light", "Light"), ("dark", "Dark")):
            action = appearance.addAction(tr(label))
            action.triggered.connect(lambda checked=False, v=value: self.apply_theme(v))
        menu.addAction(tr("About CoverPrint"), self.show_about)
        menu_button.setMenu(menu)
        title_row.addWidget(menu_button)
        layout.addLayout(title_row)

        open_btn = QPushButton(tr("Open cover (PNG or JPEG)"))
        open_btn.clicked.connect(self.open_image)
        layout.addWidget(open_btn)
        self.filename = QLabel(tr("No image selected"))
        layout.addWidget(self.filename)
        self.picture = QLabel()
        self.picture.setMinimumHeight(210)
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.picture, 1)

        layout.addWidget(QLabel(tr("Case format")))
        self.preset = ModernComboBox()
        self.preset.setView(QListView())
        self.preset.view().setMouseTracking(True)
        self.preset.addItems(PRESETS)
        layout.addWidget(self.preset)
        layout.addWidget(QLabel(tr("Image fitting")))
        self.fit_mode = ModernComboBox()
        self.fit_mode.setView(QListView())
        self.fit_mode.view().setMouseTracking(True)
        self.fit_mode.addItems([tr("Fit exactly (no cropping)"), tr("Keep aspect ratio (with margins)"), tr("Fill and crop")])
        layout.addWidget(self.fit_mode)
        self.marks = VisibleCheckBox(tr("Add crop marks"))
        self.marks.setChecked(True)
        layout.addWidget(self.marks)
        self.status = QLabel(tr("The PDF will be A4 landscape at actual size."))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        save_btn = QPushButton(tr("Export A4 PDF"))
        save_btn.clicked.connect(self.save_pdf)
        layout.addWidget(save_btn)
        self.apply_theme(self.settings.value("theme", "system"), save=False)

    def windows_prefers_dark(self):
        """Read the Windows 10/11 *app* theme, not the taskbar theme."""
        if sys.platform == "win32":
            try:
                import winreg
                key = r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                    return winreg.QueryValueEx(handle, "AppsUseLightTheme")[0] == 0
            except (OSError, ValueError):
                pass
        return QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark

    def apply_theme(self, value, save=True):
        app = QApplication.instance()
        self.theme_choice = value if value in ("system", "light", "dark") else "system"
        dark = self.windows_prefers_dark() if self.theme_choice == "system" else self.theme_choice == "dark"
        self._last_system_dark = dark if self.theme_choice == "system" else None
        # Fusion respects QPalette for controls, including drop-downs and checkboxes.
        app.setStyle(QStyleFactory.create("Fusion"))
        palette = QPalette()
        if dark:
            colors = {
                "Window": "#242428", "WindowText": "#f1f1f2",
                "Base": "#303035", "AlternateBase": "#38383d",
                "Text": "#f1f1f2", "Button": "#39393e",
                "ButtonText": "#f1f1f2", "Highlight": "#438e61",
                "HighlightedText": "#ffffff", "ToolTipBase": "#303035",
                "ToolTipText": "#f1f1f2", "PlaceholderText": "#b4b4ba",
                "Light": "#55555b", "Midlight": "#45454a",
                "Mid": "#66666d", "Dark": "#171719", "Shadow": "#101012",
                "BrightText": "#ffffff", "Link": "#8bc7a2",
            }
            border, field, hover, fg = "#77777f", "#303035", "#45454b", "#f1f1f2"
        else:
            # A soft light theme with visible field borders (not pure white).
            colors = {
                "Window": "#e9e9ed", "WindowText": "#242428",
                "Base": "#f7f7f9", "AlternateBase": "#ececf0",
                "Text": "#242428", "Button": "#dedee4",
                "ButtonText": "#242428", "Highlight": "#397f56",
                "HighlightedText": "#ffffff", "ToolTipBase": "#f7f7f9",
                "ToolTipText": "#242428", "PlaceholderText": "#686872",
                "Light": "#ffffff", "Midlight": "#ededf0",
                "Mid": "#a0a0aa", "Dark": "#777782", "Shadow": "#565660",
                "BrightText": "#000000", "Link": "#25693e",
            }
            border, field, hover, fg = "#888893", "#f7f7f9", "#d4d4dc", "#242428"
        for role, color in colors.items():
            palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
        app.setPalette(palette)
        # Explicit borders keep controls distinguishable on Windows 10 and 11.
        app.setStyleSheet(f"""
            QComboBox, QPushButton {{
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
                background-color: {field};
                color: {fg};
                min-height: 22px;
            }}
            QPushButton:hover, QComboBox:hover {{ background-color: {hover}; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 36px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {field};
                color: {fg};
                border: 1px solid {border};
                outline: 0;
                selection-background-color: {hover};
                selection-color: {fg};
            }}
            QComboBox QListView::item {{
                background-color: {field};
                color: {fg};
                border: none;
                outline: none;
                padding: 7px 10px;
                min-height: 23px;
            }}
            QComboBox QListView::item:hover,
            QComboBox QListView::item:selected {{
                background-color: {hover};
                color: {fg};
                border: none;
                outline: none;
            }}
            QCheckBox {{ color: {fg}; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1.5px solid {border};
                border-radius: 5px;
                background-color: {field};
            }}
            QCheckBox::indicator:checked {{
                border: 1.5px solid #397f56;
                background-color: #397f56;
            }}
        """)
        if save:
            self.settings.setValue("theme", self.theme_choice)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if getattr(self, "theme_choice", None) == "system":
            dark = self.windows_prefers_dark()
            if dark != getattr(self, "_last_system_dark", None):
                self._last_system_dark = dark
                self.apply_theme("system", save=False)

    def show_about(self):
        QMessageBox.about(
            self, tr("About CoverPrint"),
            "CoverPrint " + VERSION + "\nKennyl4d\n\n"
            "Prepare DVD and Blu-ray covers at accurate physical dimensions for A4 printing.\n\n"
            "GPL-3.0-only. This program comes with absolutely no warranty.\n"
            "https://github.com/Kennyl4d/CoverPrint",
        )

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Select a cover"), "", "PNG and JPEG (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            with Image.open(path) as img:
                img.verify()
            pixmap = QPixmap(path)
            if pixmap.isNull():
                raise ValueError("Unable to decode image")
            self.image_path = path
            self.filename.setText(Path(path).name)
            self.picture.setPixmap(pixmap.scaled(620, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.status.setText(tr("Cover loaded. Select a format and export."))
        except Exception as exc:
            self.status.setText(tr("Unable to open image: {error}").format(error=exc))

    def save_pdf(self):
        if not self.image_path:
            self.status.setText(tr("Select a cover first."))
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Save PDF"), "copertina.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_pdf(self.image_path, path, list(PRESETS.values())[self.preset.currentIndex()], self.fit_mode.currentIndex(), self.marks.isChecked())
            self.status.setText(tr("PDF created. Print at 100%, without fitting to page.") + " (" + path + ")")
        except Exception as exc:
            self.status.setText(tr("Export failed: {error}").format(error=exc))

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CoverPrint")
    app.setApplicationVersion(VERSION)
    window = CoverPrintWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
