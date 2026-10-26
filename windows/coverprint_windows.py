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
from PySide6.QtGui import QAction, QIcon, QPalette, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
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
    raw = os.environ.get("LANGUAGE", "").split(":")[0] or os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
    if not raw:
        raw = locale.getlocale()[0] or "en"
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
        self.preset = QComboBox()
        self.preset.addItems(PRESETS)
        layout.addWidget(self.preset)
        layout.addWidget(QLabel(tr("Image fitting")))
        self.fit_mode = QComboBox()
        self.fit_mode.addItems([tr("Fit exactly (no cropping)"), tr("Keep aspect ratio (with margins)"), tr("Fill and crop")])
        layout.addWidget(self.fit_mode)
        self.marks = QCheckBox(tr("Add crop marks"))
        self.marks.setChecked(True)
        layout.addWidget(self.marks)
        self.status = QLabel(tr("The PDF will be A4 landscape at actual size."))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        save_btn = QPushButton(tr("Export A4 PDF"))
        save_btn.clicked.connect(self.save_pdf)
        layout.addWidget(save_btn)
        self.apply_theme(self.settings.value("theme", "system"), save=False)

    def apply_theme(self, value, save=True):
        app = QApplication.instance()
        if value == "system":
            app.setPalette(app.style().standardPalette())
        elif value == "dark":
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#222226"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#f6f6f6"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#303034"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#38383c"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#f6f6f6"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#38383c"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f6f6f6"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#35884a"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            app.setPalette(palette)
        else:
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#f6f6f6"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#202020"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#202020"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#ededed"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#202020"))
            app.setPalette(palette)
        if save:
            self.settings.setValue("theme", value)

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
