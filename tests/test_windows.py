import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("coverprint_windows", ROOT / "windows/coverprint_windows.py")
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)
from PIL import Image
from pypdf import PdfReader
from PySide6.QtCore import QSettings

app = cp.QApplication.instance() or cp.QApplication([])
settings_directory = tempfile.TemporaryDirectory()
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_directory.name)


class WindowsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / "image.jpg"
        Image.new("RGB", (120, 80), "#3477aa").save(self.image, quality=95)

    def test_preferences_survive_window_recreation(self):
        first = cp.CoverPrintWindow()
        first.preset.setCurrentIndex(2)
        first.fit_mode.setCurrentIndex(2)
        first.marks.setChecked(False)
        first.close()
        second = cp.CoverPrintWindow()
        self.assertEqual(second.preset.currentIndex(), 2)
        self.assertEqual(second.fit_mode.currentIndex(), 2)
        self.assertFalse(second.marks.isChecked())
        second.close()

    def test_invalid_preferences_fall_back(self):
        settings = QSettings("Kennyl4d", "CoverPrint")
        settings.setValue("case-format", "obsolete")
        settings.setValue("image-fitting", "obsolete")
        window = cp.CoverPrintWindow()
        self.assertEqual(window.preset.currentIndex(), 0)
        self.assertEqual(window.fit_mode.currentIndex(), 0)
        window.close()

    def test_pdf_geometry_and_jpeg_bytes(self):
        for size in cp.PRESETS.values():
            for mode in range(3):
                for marks in (False, True):
                    with self.subTest(size=size, mode=mode, marks=marks):
                        output = Path(self.directory.name) / "cover.pdf"
                        cp.export_pdf(self.image, output, size, mode, marks)
                        page = PdfReader(output).pages[0]
                        self.assertAlmostEqual(float(page.mediabox.width), 297 * cp.MM_TO_PT, places=3)
                        self.assertAlmostEqual(float(page.mediabox.height), 210 * cp.MM_TO_PT, places=3)
                        image = next(iter(page["/Resources"]["/XObject"].values())).get_object()
                        self.assertEqual(image["/Width"], 120)
                        self.assertEqual(image["/Height"], 80)
                        self.assertEqual(image.get_data(), self.image.read_bytes())
                        operations = page.get_contents().operations
                        clip = next(args for args, operator in operations if operator == b"re" and len(args) == 4 and abs(float(args[2]) - size[0] * cp.MM_TO_PT) < .01)
                        self.assertAlmostEqual(float(clip[3]), size[1] * cp.MM_TO_PT, places=3)

    def test_exif_and_png_keep_full_resolution(self):
        for name, mode, size, orientation, expected in (
            ("rotated.jpg", "RGB", (120, 80), 6, (80, 120)),
            ("alpha.png", "RGBA", (120, 80), 1, (120, 80)),
            ("gray.png", "L", (120, 80), 1, (120, 80)),
            ("cmyk.jpg", "CMYK", (120, 80), 1, (120, 80)),
        ):
            image = Image.new(mode, size)
            exif = Image.Exif()
            exif[274] = orientation
            source = Path(self.directory.name) / name
            image.save(source, exif=exif)
            output = Path(self.directory.name) / "cover.pdf"
            cp.export_pdf(source, output, (264, 148), 0, True)
            page = PdfReader(output).pages[0]
            embedded = next(iter(page["/Resources"]["/XObject"].values())).get_object()
            self.assertEqual((embedded["/Width"], embedded["/Height"]), expected)

    def wait_worker(self, window):
        deadline = time.monotonic() + 15
        ticks = 0
        while window.worker is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
            ticks += 1
        self.assertIsNone(window.worker)
        return ticks

    def test_async_export_and_atomic_failure(self):
        window = cp.CoverPrintWindow()
        window.image_path = str(self.image)
        output = Path(self.directory.name) / "cover.pdf"
        original_export = cp.export_pdf

        def delayed_export(*args):
            time.sleep(.2)
            original_export(*args)

        with patch.object(cp.QFileDialog, "getSaveFileName", return_value=(str(output), "")):
            with patch.object(cp, "export_pdf", side_effect=delayed_export):
                window.save_pdf()
                self.assertIsNotNone(window.worker)
                self.assertFalse(window.export_controls[-1].isEnabled())
                self.assertGreater(self.wait_worker(window), 3)
            previous = output.read_bytes()
            with patch.object(cp, "export_pdf", side_effect=OSError("test failure")):
                window.save_pdf()
                self.wait_worker(window)
            self.assertEqual(output.read_bytes(), previous)
            self.assertIn("test failure", window.status.text())
            self.assertTrue(window.export_controls[-1].isEnabled())
            self.assertEqual(list(Path(self.directory.name).glob("tmp*.pdf")), [])
        window.close()

    def test_english_fallback(self):
        with patch.object(cp, "LANGUAGE", "unknown"):
            self.assertEqual(cp.tr(cp.ABOUT_DESCRIPTION), cp.ABOUT_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
