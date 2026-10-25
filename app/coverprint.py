#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, Gdk, GdkPixbuf, Adw
import cairo
import math

PRESETS = {
    "DVD standard (273 × 183 mm)": (273, 183),
    "DVD slim (266 × 183 mm)": (266, 183),
    "Blu-ray 12 mm (264 × 148 mm)": (264, 148),
    "Blu-ray 14 mm (266 × 148 mm)": (266, 148),
    "Blu-ray 5 mm (257 × 148 mm)": (257, 148),
}
MM_TO_PT = 72 / 25.4

class CoverPrint(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.kennyl4d.CoverPrint")
        self.image_path = None
        self.image_bytes = None
        self.texture = None
        self.settings = Gio.Settings.new("io.github.kennyl4d.CoverPrint")
        self.style = Adw.StyleManager.get_default()
        self.apply_theme(self.settings.get_string("theme"))

    def apply_theme(self, value):
        schemes = {"system": Adw.ColorScheme.DEFAULT, "light": Adw.ColorScheme.FORCE_LIGHT, "dark": Adw.ColorScheme.FORCE_DARK}
        self.style.set_color_scheme(schemes.get(value, Adw.ColorScheme.DEFAULT))

    def on_theme_changed(self, dropdown, _param):
        value = ("system", "light", "dark")[dropdown.get_selected()]
        self.settings.set_string("theme", value)
        self.apply_theme(value)

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self, title="CoverPrint")
        self.win.set_default_size(680, 560)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20); box.set_margin_bottom(20)
        box.set_margin_start(20); box.set_margin_end(20)
        self.win.set_child(box)
        title = Gtk.Label(label="CoverPrint — Copertine pronte da stampare", xalign=0)
        title.add_css_class("title-2")
        box.append(title)
        theme_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        theme_row.append(Gtk.Label(label="Aspetto", xalign=0, hexpand=True))
        theme = Gtk.DropDown.new_from_strings(["Sistema", "Chiaro", "Scuro"])
        current = self.settings.get_string("theme")
        theme.set_selected({"system": 0, "light": 1, "dark": 2}.get(current, 0))
        theme.connect("notify::selected", self.on_theme_changed)
        theme_row.append(theme)
        box.append(theme_row)
        open_btn = Gtk.Button(label="Apri copertina (PNG o JPEG)")
        open_btn.connect("clicked", self.open_image)
        box.append(open_btn)
        self.filename = Gtk.Label(label="Nessuna immagine selezionata", xalign=0)
        box.append(self.filename)
        self.picture = Gtk.Picture()
        self.picture.set_size_request(-1, 220)
        self.picture.set_can_shrink(True)
        box.append(self.picture)
        box.append(Gtk.Label(label="Formato custodia", xalign=0))
        self.preset = Gtk.DropDown.new_from_strings(list(PRESETS))
        box.append(self.preset)
        self.crop = Gtk.CheckButton(label="Riempi e ritaglia (anziché adattare con margini)")
        box.append(self.crop)
        self.marks = Gtk.CheckButton(label="Aggiungi segni di taglio")
        self.marks.set_active(True)
        box.append(self.marks)
        self.status = Gtk.Label(label="Il PDF sarà su A4 orizzontale, in dimensioni reali.", xalign=0)
        self.status.set_wrap(True)
        box.append(self.status)
        save_btn = Gtk.Button(label="Esporta PDF A4")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self.save_pdf)
        box.append(save_btn)
        self.win.present()

    def open_image(self, *_):
        dialog = Gtk.FileDialog(title="Seleziona una copertina")
        filt = Gtk.FileFilter()
        filt.set_name("Immagini PNG e JPEG")
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
            self.filename.set_text(f.get_basename())
            self.picture.set_file(f)
            self.status.set_text("Copertina caricata. Seleziona il formato ed esporta.")
        except Exception as exc:
            self.status.set_text(f"Impossibile aprire l'immagine: {exc}")

    def save_pdf(self, *_):
        if self.image_bytes is None:
            self.status.set_text("Prima seleziona una copertina.")
            return
        dialog = Gtk.FileDialog(title="Salva PDF")
        dialog.set_initial_name("copertina.pdf")
        dialog.save(self.win, None, self.on_pdf_save)

    def on_pdf_save(self, dialog, result):
        try:
            path = dialog.save_finish(result).get_path()
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            self.export(path)
            self.status.set_text(f"PDF creato: {path}. Stampa al 100%, senza adattare alla pagina.")
        except Exception as exc:
            self.status.set_text(f"Esportazione non riuscita: {exc}")

    def export(self, path):
        wmm, hmm = list(PRESETS.values())[self.preset.get_selected()]
        pw, ph = 297 * MM_TO_PT, 210 * MM_TO_PT
        w, h = wmm * MM_TO_PT, hmm * MM_TO_PT
        x, y = (pw - w)/2, (ph - h)/2
        surface = cairo.PDFSurface(path, pw, ph)
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 1, 1)
        ctx.paint()
        pixbuf = self.image_bytes
        iw, ih = pixbuf.get_width(), pixbuf.get_height()
        scale = max(w/iw, h/ih) if self.crop.get_active() else min(w/iw, h/ih)
        dw, dh = iw*scale, ih*scale
        dx, dy = x+(w-dw)/2, y+(h-dh)/2
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        ctx.translate(dx, dy)
        ctx.scale(dw / iw, dh / ih)
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
        ctx.paint()
        ctx.restore()
        if self.marks.get_active():
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
