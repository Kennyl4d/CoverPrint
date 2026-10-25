<h1 align="center">CoverPrint</h1>

<p align="center"><img width="112" height="112" alt="CoverPrint" src="app/io.github.kennyl4d.CoverPrint.svg" /></p>

<p align="center"><strong>A lightweight DVD and Blu-ray cover printing tool for Linux.</strong><br>Prepare print-ready covers at accurate physical dimensions with a clean GNOME interface.</p>

<p align="center">
<a href="../../releases"><img alt="Download for Linux" src="https://img.shields.io/badge/Download-Linux-0078D4?style=flat-square"></a>
<a href="../../actions/workflows/flatpak.yml"><img alt="Flatpak build" src="https://github.com/Kennyl4d/CoverPrint/actions/workflows/flatpak.yml/badge.svg?branch=main"></a>
<a href="LICENSE"><img alt="License: GPL v3.0" src="https://img.shields.io/badge/License-GPL--3.0-blue?style=flat-square"></a>
</p>

CoverPrint converts existing PNG and JPEG cover artwork into A4 landscape PDFs, centered and sized for DVD and Blu-ray cases.

<p align="center">
  <img width="730" height="748" alt="CoverPrint" src="https://github.com/user-attachments/assets/b81efea5-7bbf-43e5-be23-a0e2d7881800" />
</p>

## Downloads

Download `CoverPrint.flatpak` from the [Releases page](../../releases), or use a successful [GitHub Actions build](../../actions/workflows/flatpak.yml).

Install with a Flatpak-compatible software manager, or run:

```sh
flatpak install --user ./CoverPrint.flatpak
```

Requires Flatpak and the GNOME 51 runtime.

## Features

- Accurate DVD and Blu-ray cover size presets.
- Exact fit, preserve aspect ratio, and fill-and-crop modes.
- Optional crop marks and A4 landscape PDF export.
- Light, dark, and system appearance settings.
- Native GTK 4 and libadwaita interface.
- Automatic language detection; English fallback.
- Offline image processing.

## Supported case sizes

| Case | Cover dimensions |
|---|---|
| DVD standard | 273 × 183 mm |
| DVD slim | 266 × 183 mm |
| Blu-ray 12 mm | 264 × 148 mm |
| Blu-ray 14 mm | 266 × 148 mm |
| Blu-ray 5 mm | 257 × 148 mm |

Measure the physical case before printing. Exact fit may stretch images with mismatched proportions; preserve aspect ratio may add margins; fill and crop may cut off image edges.

## Languages

CoverPrint follows the system language automatically. Supported languages (14):

English, Italian, Czech, German, Spanish, French, Japanese, Korean, Polish, Brazilian Portuguese, Russian, Turkish, Simplified Chinese, and Traditional Chinese.

## Printing

Export the cover as an A4 landscape PDF. Print at **100% / actual size**, with fit-to-page and automatic scaling disabled. Check the dimensions with a ruler before cutting.

## Source code and builds

CoverPrint is written in Python with GTK 4, libadwaita, GdkPixbuf, and Cairo. GitHub Actions builds the Flatpak from [the manifest](io.github.kennyl4d.CoverPrint.yml). Application sources are in [app](app).

## Feedback

Found a problem? Open an [issue](../../issues) and include your Linux distribution, CoverPrint version, reproduction steps, and error messages.

## License

CoverPrint is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE). Third-party components retain their respective licenses.

## Author

**KENNY**
