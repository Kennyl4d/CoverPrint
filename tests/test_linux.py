import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["GSETTINGS_BACKEND"] = "memory"
ROOT = Path(__file__).resolve().parents[1]
os.environ["GSETTINGS_SCHEMA_DIR"] = str(ROOT / "app")
sys.path.insert(0, str(ROOT / "app"))
import coverprint as cp
from pypdf import PdfReader

cp.Adw.init()


class LinuxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.application = cp.CoverPrint()
        self.application.set_application_id("io.github.kennyl4d.CoverPrint.Test" + self._testMethodName.replace("_", ""))
        self.application.set_flags(cp.Gio.ApplicationFlags.NON_UNIQUE)
        self.application.register(None)
        self.application.activate()
        self.addCleanup(lambda: self.application.win.destroy())
        self.application.image_bytes = cp.GdkPixbuf.Pixbuf.new(
            cp.GdkPixbuf.Colorspace.RGB, False, 8, 120, 80)
        self.application.image_bytes.fill(0x3477aaff)

    def test_preferences_survive_application_recreation(self):
        first = self.application
        first.preset.set_selected(2)
        first.fit_mode.set_selected(2)
        first.marks.set_active(False)
        first.win.destroy()
        del first.win
        first.activate()
        self.assertEqual(first.preset.get_selected(), 2)
        self.assertEqual(first.fit_mode.get_selected(), 2)
        self.assertFalse(first.marks.get_active())

    def test_invalid_preferences_fall_back(self):
        app = self.application
        app.settings.set_string("case-format", "obsolete")
        app.settings.set_string("image-fitting", "obsolete")
        app.win.destroy()
        del app.win
        app.activate()
        self.assertEqual(app.preset.get_selected(), 0)
        self.assertEqual(app.fit_mode.get_selected(), 0)

    def test_pdf_geometry_and_cache(self):
        app = self.application
        source = None
        for size in cp.PRESETS.values():
            for mode in range(3):
                for marks in (False, True):
                    output = Path(self.directory.name) / "cover.pdf"
                    app.export(str(output), app.image_bytes, size, mode, marks)
                    page = PdfReader(output).pages[0]
                    self.assertAlmostEqual(float(page.mediabox.width), 297 * cp.MM_TO_PT, places=3)
                    self.assertAlmostEqual(float(page.mediabox.height), 210 * cp.MM_TO_PT, places=3)
                    image = next(iter(page["/Resources"]["/XObject"].values())).get_object()
                    self.assertEqual((image["/Width"], image["/Height"]), (120, 80))
                    if source is not None:
                        self.assertIs(app.render_source[1], source)
                    source = app.render_source[1]

    def test_async_export_and_atomic_failure(self):
        app = self.application
        output = Path(self.directory.name) / "cover.pdf"

        class File:
            def get_path(self):
                return str(output)

        class Dialog:
            def save_finish(self, _):
                return File()

        original = app.export

        def delayed_export(*args):
            time.sleep(.2)
            original(*args)

        def wait():
            deadline = time.monotonic() + 15
            ticks = 0
            context = cp.GLib.MainContext.default()
            while app.exporting and time.monotonic() < deadline:
                while context.pending():
                    context.iteration(False)
                time.sleep(.01)
                ticks += 1
            self.assertFalse(app.exporting)
            return ticks

        with patch.object(app, "export", side_effect=delayed_export):
            app.on_pdf_save(Dialog(), None)
            self.assertTrue(app.exporting)
            self.assertFalse(app.export_controls[-1].get_sensitive())
            self.assertGreaterEqual(wait(), 1)
        previous = output.read_bytes()
        with patch.object(app, "export", side_effect=OSError("test failure")):
            app.on_pdf_save(Dialog(), None)
            wait()
        self.assertEqual(output.read_bytes(), previous)
        self.assertIn("test failure", app.status.get_text())
        self.assertTrue(app.export_controls[-1].get_sensitive())
        self.assertEqual(list(Path(self.directory.name).glob("tmp*.pdf")), [])

    def test_about_uses_current_language(self):
        def inspect_dialog(dialog, parent):
            self.assertIn(cp.tr(cp.ABOUT_DESCRIPTION), dialog.get_body())
            self.assertIn(cp.tr(cp.ABOUT_LICENSE), dialog.get_body())
            self.assertEqual(dialog.get_heading(), cp.tr("About CoverPrint"))
            self.assertEqual(dialog.get_response_label("close"), cp.tr("Close"))

        for language in ("en", *cp.TRANSLATIONS, "unsupported"):
            with patch.object(cp, "_LANG", language):
                with patch.object(cp.Adw.AlertDialog, "present", new=inspect_dialog):
                    self.application.show_about()

    def test_english_fallback(self):
        with patch.object(cp, "_LANG", "unknown"):
            self.assertEqual(cp.tr(cp.ABOUT_DESCRIPTION), cp.ABOUT_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
