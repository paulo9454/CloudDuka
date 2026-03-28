#!/usr/bin/env python3
"""Generate CloudDuka icons from a source logo image.

This keeps binary assets out of git history when PR tooling cannot process binary diffs.
"""
from pathlib import Path
import argparse
import csv
from io import StringIO

from PIL import Image, ImageOps, ImageDraw
import numpy as np

APP_SIZES = [48, 72, 96, 144, 192, 512]
FAVICON_SIZES = [16, 32, 48, 64]
PWA_SIZES = [120, 152, 180, 192, 512]


def find_foreground_bbox(image: Image.Image):
    arr = np.array(image.convert("RGBA"))
    corners = np.array([arr[0, 0, :3], arr[0, -1, :3], arr[-1, 0, :3], arr[-1, -1, :3]], dtype=np.int16)
    bg = corners.mean(axis=0)
    diff = np.abs(arr[:, :, :3].astype(np.int16) - bg).sum(axis=2)
    mask = diff > 30
    ys, xs = np.where(mask)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1), mask


def extract_emblem(image: Image.Image):
    _, mask = find_foreground_bbox(image)
    row_counts = mask.sum(axis=1)
    nonempty = np.where(row_counts > 10)[0]
    start, end = nonempty.min(), nonempty.max()
    search_start = start + (end - start) // 3
    search_end = max(search_start + 1, end - 20)
    cut = search_start + int(np.argmin(row_counts[search_start:search_end]))

    top_mask = mask.copy()
    top_mask[cut:, :] = False
    ys, xs = np.where(top_mask)
    return image.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def compose_icon(mark: Image.Image, size: int, padding_ratio: float, opaque_round: bool = False):
    base = Image.new("RGBA", (size, size), (255, 255, 255, 255 if opaque_round else 0))
    fit = ImageOps.contain(mark, (int(size * (1 - 2 * padding_ratio)), int(size * (1 - 2 * padding_ratio))), method=Image.Resampling.LANCZOS)
    base.alpha_composite(fit, ((size - fit.width) // 2, (size - fit.height) // 2))
    if opaque_round:
        radius = int(size * 0.22)
        m = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(m)
        d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
        base.putalpha(m)
    return base


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="/tmp/user_uploaded_attachments/image_1.png", help="Path to source logo image")
    parser.add_argument("--out", default="frontend/public/icons", help="Output directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated assets if present")
    args = parser.parse_args()

    src = Path(args.source)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not args.force:
        existing = list(out.glob("app-icon-*.png")) + list(out.glob("favicon-*.png")) + list(out.glob("pwa-icon-*.png"))
        if existing:
            raise SystemExit(
                "Generated icon files already exist. Re-run with --force to overwrite."
            )

    if src.exists():
        logo = Image.open(src).convert("RGBA")
    else:
        logo = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
        draw = ImageDraw.Draw(logo)
        draw.rounded_rectangle((170, 170, 854, 854), radius=220, fill=(10, 102, 194, 255))
        draw.text((430, 430), "CD", fill=(255, 165, 0, 255))
    emblem = extract_emblem(logo)

    for s in APP_SIZES:
        compose_icon(emblem, s, padding_ratio=0.08).save(out / f"app-icon-{s}x{s}.png")
    for s in PWA_SIZES:
        compose_icon(emblem, s, padding_ratio=0.09, opaque_round=True).save(out / f"pwa-icon-{s}x{s}.png")

    favs = []
    for s in FAVICON_SIZES:
        fav = compose_icon(emblem, s, padding_ratio=0.02)
        fav.save(out / f"favicon-{s}x{s}.png")
        favs.append(fav)
    favs[0].save(out / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    print(f"Generated icons in {out}")


if __name__ == "__main__":
    main()
