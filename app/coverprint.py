#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, Gdk, GdkPixbuf, Adw, GLib
import cairo
import math
import os
import tempfile
import threading
from pathlib import Path
from translations import TRANSLATIONS


def system_language():
    # Honor standard Linux locale precedence, including Flatpak locale settings.
    raw = os.environ.get("LANGUAGE", "").split(":")[0] or os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "en"
    code = raw.split(".")[0].replace("-", "_")
    if code.lower().startswith("zh"):
        return "zh_TW" if any(part in code.lower() for part in ("tw", "hk", "hant")) else "zh_CN"
    if code.lower().startswith("pt"):
        return "pt_BR"
    return code.split("_")[0].lower()


_LANG = system_language()
def tr(message):
    return TRANSLATIONS.get(_LANG, {}).get(message, message)


PRESETS = {
    "DVD standard (273 × 183 mm)": (273, 183),
    "DVD slim (266 × 183 mm)": (266, 183),
    "Blu-ray 12 mm (264 × 148 mm)": (264, 148),
    "Blu-ray 14 mm (266 × 148 mm)": (266, 148),
    "Blu-ray 5 mm (257 × 148 mm)": (257, 148),
}
MM_TO_PT = 72 / 25.4
ABOUT_DESCRIPTION = "Prepare DVD and Blu-ray covers at accurate physical dimensions for A4 printing."
ABOUT_LICENSE = "CoverPrint is licensed under the GNU General Public License, version 3 only (GPL-3.0-only).\n\nThis program comes with absolutely no warranty, to the extent permitted by applicable law.\n\nSee the LICENSE file in the source repository for the complete license terms."

class CoverPrint(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.kennyl4d.CoverPrint")
        self.image_path = None
        self.image_bytes = None
        self.texture = None
        self.exporting = False
        self.render_source = None
        self.set_resource_base_path("/io/github/kennyl4d/CoverPrint")
        self.settings = Gio.Settings.new("io.github.kennyl4d.CoverPrint")
        self.style = Adw.StyleManager.get_default()
        self.apply_theme(self.settings.get_string("theme"))
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about)
        self.add_action(about_action)
        for value in ("system", "light", "dark"):
            action = Gio.SimpleAction.new("theme-" + value, None)
            action.connect("activate", self.set_theme_action, value)
            self.add_action(action)

    def apply_theme(self, value):
        schemes = {"system": Adw.ColorScheme.DEFAULT, "light": Adw.ColorScheme.FORCE_LIGHT, "dark": Adw.ColorScheme.FORCE_DARK}
        self.style.set_color_scheme(schemes.get(value, Adw.ColorScheme.DEFAULT))

    def set_theme_action(self, _action, _parameter, value):
        self.settings.set_string("theme", value)
        self.apply_theme(value)

    def show_about(self, *_):
        dialog = Adw.AlertDialog(heading=tr("About CoverPrint"))
        dialog.set_body("CoverPrint\n" + tr("Version") + " 1.2.0\n"
                        + tr("Developer") + " Kennyl4d\n\n"
                        + tr(ABOUT_DESCRIPTION) + "\n\n" + tr(ABOUT_LICENSE)
                        + "\n\nhttps://github.com/Kennyl4d/CoverPrint")
        dialog.add_response("close", tr("Close"))
        dialog.set_close_response("close")
        dialog.present(self.win)

    def do_activate(self):
        if hasattr(self, "win"):
            self.win.present()
            return
        self.win = Adw.ApplicationWindow(application=self, title="CoverPrint")
        self.win.set_default_size(680, 560)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20); box.set_margin_bottom(20)
        box.set_margin_start(20); box.set_margin_end(20)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        menu = Gio.Menu()
        appearance = Gio.Menu()
        appearance.append(tr("Follow system"), "app.theme-system")
        appearance.append(tr("Light"), "app.theme-light")
        appearance.append(tr("Dark"), "app.theme-dark")
        menu.append_submenu(tr("Appearance"), appearance)
        menu.append(tr("About CoverPrint"), "app.about")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text=tr("Menu"))
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)
        toolbar.add_top_bar(header)
        toolbar.set_content(box)
        self.win.set_content(toolbar)
        title = Gtk.Label(label="CoverPrint — " + tr("Print-ready covers"), xalign=0)
        title.add_css_class("title-2")
        box.append(title)
        open_btn = Gtk.Button(label=tr("Open cover (PNG or JPEG)"))
        open_btn.connect("clicked", self.open_image)
        box.append(open_btn)
        self.filename = Gtk.Label(label=tr("No image selected"), xalign=0)
        box.append(self.filename)
        self.picture = Gtk.Picture()
        self.picture.set_size_request(-1, 220)
        self.picture.set_can_shrink(True)
        box.append(self.picture)
        box.append(Gtk.Label(label=tr("Case format"), xalign=0))
        self.preset = Gtk.DropDown.new_from_strings(list(PRESETS))
        box.append(self.preset)
        box.append(Gtk.Label(label=tr("Image fitting"), xalign=0))
        self.fit_mode = Gtk.DropDown.new_from_strings([tr("Fit exactly (no cropping)"), tr("Keep aspect ratio (with margins)"), tr("Fill and crop")])
        box.append(self.fit_mode)
        self.marks = Gtk.CheckButton(label=tr("Add crop marks"))
        preset = self.settings.get_string("case-format")
        self.preset.set_selected(list(PRESETS).index(preset) if preset in PRESETS else 0)
        modes = ("exact", "contain", "cover")
        fitting = self.settings.get_string("image-fitting")
        self.fit_mode.set_selected(modes.index(fitting) if fitting in modes else 0)
        self.marks.set_active(self.settings.get_boolean("crop-marks"))
        self.preset.connect("notify::selected", self.save_preferences)
        self.fit_mode.connect("notify::selected", self.save_preferences)
        self.marks.connect("toggled", self.save_preferences)
        box.append(self.marks)
        self.status = Gtk.Label(label=tr("The PDF will be A4 landscape at actual size."), xalign=0)
        self.status.set_wrap(True)
        box.append(self.status)
        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        box.append(self.progress)
        save_btn = Gtk.Button(label=tr("Export A4 PDF"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self.save_pdf)
        box.append(save_btn)
        self.export_controls = (open_btn, self.preset, self.fit_mode, self.marks, save_btn)
        self.win.connect("close-request", lambda *_: self.exporting)
        self.win.present()

    def save_preferences(self, *_):
        self.settings.set_string("case-format", list(PRESETS)[self.preset.get_selected()])
        self.settings.set_string("image-fitting", ("exact", "contain", "cover")[self.fit_mode.get_selected()])
        self.settings.set_boolean("crop-marks", self.marks.get_active())

    def open_image(self, *_):
        dialog = Gtk.FileDialog(title=tr("Select a cover"))
        filt = Gtk.FileFilter()
        filt.set_name(tr("PNG and JPEG images"))
        for mime in ("image/png", "image/jpeg"):
            filt.add_mime_type(mime)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filt)
        dialog.set_filters(filters)
        dialog.open(self.win, None, self.on_image_open)

    def on_image_open(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            data = f.load_contents(None)[1]
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(data)
            loader.close()
            self.image_bytes = loader.get_pixbuf()
            self.render_source = None
            self.filename.set_text(f.get_basename())
            self.picture.set_file(f)
            self.status.set_text(tr("Cover loaded. Select a format and export."))
        except Exception as exc:
            self.status.set_text(tr("Unable to open image: {error}").format(error=exc))

    def save_pdf(self, *_):
        if self.image_bytes is None:
            self.status.set_text(tr("Select a cover first."))
            return
        dialog = Gtk.FileDialog(title=tr("Save PDF"))
        dialog.set_initial_name("copertina.pdf")
        dialog.save(self.win, None, self.on_pdf_save)

    def on_pdf_save(self, dialog, result):
        try:
            path = dialog.save_finish(result).get_path()
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            if self.exporting:
                return
            size = list(PRESETS.values())[self.preset.get_selected()]
            mode = self.fit_mode.get_selected()
            marks = self.marks.get_active()
            pixbuf = self.image_bytes
            self.exporting = True
            for control in self.export_controls:
                control.set_sensitive(False)
            self.status.set_text(tr("Exporting PDF…"))
            self.progress.set_visible(True)
            self.progress.pulse()
            self.pulse_source = GLib.timeout_add(100, self.pulse_progress)
            self.hold()
            threading.Thread(target=self.export_worker,
                             args=(path, pixbuf, size, mode, marks), daemon=True).start()
        except Exception as exc:
            self.status.set_text(tr("Export failed: {error}").format(error=exc))

    def pulse_progress(self):
        self.progress.pulse()
        return GLib.SOURCE_CONTINUE

    def export_worker(self, path, pixbuf, size, mode, marks):
        temporary = None
        error = None
        try:
            with tempfile.NamedTemporaryFile(dir=Path(path).parent,
                                             suffix=".pdf", delete=False) as handle:
                temporary = handle.name
            self.export(temporary, pixbuf, size, mode, marks)
            os.replace(temporary, path)
            temporary = None
        except Exception as exc:
            error = str(exc)
        finally:
            try:
                if temporary is not None:
                    Path(temporary).unlink(missing_ok=True)
            except OSError as exc:
                error = error or str(exc)
            GLib.idle_add(self.export_completed, path, error)

    def export_completed(self, path, error):
        GLib.source_remove(self.pulse_source)
        self.progress.set_visible(False)
        self.exporting = False
        for control in self.export_controls:
            control.set_sensitive(True)
        if error is not None:
            self.status.set_text(tr("Export failed: {error}").format(error=error))
        else:
            self.status.set_text(tr("PDF created. Print at 100%, without fitting to page.") + f" ({path})")
        self.release()
        return GLib.SOURCE_REMOVE

    def export(self, path, pixbuf=None, size=None, mode=None, marks=None):
        # Snapshot widgets on the UI thread before starting a worker.
        pixbuf = self.image_bytes if pixbuf is None else pixbuf
        wmm, hmm = size if size is not None else list(PRESETS.values())[self.preset.get_selected()]
        mode = self.fit_mode.get_selected() if mode is None else mode
        marks = self.marks.get_active() if marks is None else marks
        pw, ph = 297 * MM_TO_PT, 210 * MM_TO_PT
        w, h = wmm * MM_TO_PT, hmm * MM_TO_PT
        x, y = (pw - w)/2, (ph - h)/2
        surface = cairo.PDFSurface(path, pw, ph)
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 1, 1)
        ctx.paint()
        pixbuf = self.image_bytes
        iw, ih = pixbuf.get_width(), pixbuf.get_height()
        mode = self.fit_mode.get_selected()
        if mode == 0:
            dw, dh = w, h
        else:
            scale = min(w/iw, h/ih) if mode == 1 else max(w/iw, h/ih)
            dw, dh = iw*scale, ih*scale
        dx, dy = x+(w-dw)/2, y+(h-dh)/2
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        ctx.translate(dx, dy)
        ctx.scale(dw / iw, dh / ih)
        # Reuse the full-resolution Cairo source across repeated exports.
        if self.render_source is None or self.render_source[0] is not pixbuf:
            image_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, iw, ih)
            image_context = cairo.Context(image_surface)
            Gdk.cairo_set_source_pixbuf(image_context, pixbuf, 0, 0)
            image_context.paint()
            self.render_source = (pixbuf, image_surface)
        ctx.set_source_surface(self.render_source[1], 0, 0)
        ctx.paint()
        ctx.restore()
        if marks:
            ctx.set_source_rgb(0, 0, 0)
            ctx.set_line_width(.35)
            gap, length = 4 * MM_TO_PT, 5 * MM_TO_PT
            for cx in (x, x+w):
                for cy in (y, y+h):
                    sx = -1 if cx == x else 1
                    sy = -1 if cy == y else 1
                    ctx.move_to(cx+sx*gap, cy)
                    ctx.line_to(cx+sx*(gap+length), cy)
                    ctx.move_to(cx, cy+sy*gap)
                    ctx.line_to(cx, cy+sy*(gap+length))
            ctx.stroke()
        surface.finish()

if __name__ == "__main__":
    CoverPrint().run()
