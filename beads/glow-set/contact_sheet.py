"""Tile the two-colour renders into one labelled contact sheet.

Plain PIL on purpose: this box has no ImageMagick. `convert` IS on PATH at
C:\\WINDOWS\\system32\\convert.exe, but that is the Windows FAT-to-NTFS
filesystem converter, not ImageMagick - do not call it.

    python beads/glow-set/contact_sheet.py tmp/set_*.png -o tmp/sheet.png
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageFont

BG = (28, 28, 32)
FG = (232, 232, 236)


def font(size):
    for p in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("patterns", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--label-h", type=int, default=30)
    ap.add_argument("--title", default="")
    a = ap.parse_args()

    files = sorted({f for p in a.patterns for f in glob.glob(p)})
    if not files:
        raise SystemExit("no images matched %s" % a.patterns)

    tiles = [(os.path.basename(f).replace("set_", "").rsplit(".", 1)[0],
              Image.open(f).convert("RGB")) for f in files]
    tw, th = tiles[0][1].size
    cols = min(a.cols, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    title_h = 44 if a.title else 0

    sheet = Image.new("RGB", (cols * tw, title_h + rows * (th + a.label_h)), BG)
    d = ImageDraw.Draw(sheet)
    if a.title:
        d.text((14, 12), a.title, fill=FG, font=font(24))

    f = font(19)
    for i, (name, im) in enumerate(tiles):
        x = (i % cols) * tw
        y = title_h + (i // cols) * (th + a.label_h)
        sheet.paste(im, (x, y))
        d.text((x + 10, y + th + 5), name, fill=FG, font=f)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print("wrote %s (%dx%d, %d tiles)" % (a.out, sheet.width, sheet.height,
                                          len(tiles)))


if __name__ == "__main__":
    main()
