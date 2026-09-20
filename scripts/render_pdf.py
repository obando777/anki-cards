#!/usr/bin/env python3
"""Render a scanned PDF to PNG pages so its contents can be read and transcribed.

    uv run --group extract scripts/render_pdf.py raw_input/colombia/scan.pdf -o /tmp/pages
    uv run --group extract scripts/render_pdf.py scan.pdf --pages 7,11-13 --dpi 220
    uv run --group extract scripts/render_pdf.py scan.pdf --pages 3 --crop 0.55,0.05,1.0,0.35

Scans have no text layer, so nothing here extracts text — it produces images to read.
--crop takes page fractions (x0,y0,x1,y1 from the top-left) and is useful for zooming
into a handwritten margin.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf


def parse_pages(spec: str, total: int) -> list[int]:
    """'7,11-13' -> [7, 11, 12, 13] (1-based, clamped to the document)."""
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
        else:
            start = end = int(part)
        pages.extend(range(max(1, start), min(total, end) + 1))
    return sorted(set(pages))


def parse_crop(spec: str) -> tuple[float, float, float, float]:
    values = tuple(float(x) for x in spec.split(","))
    if len(values) != 4:
        raise argparse.ArgumentTypeError("--crop needs 4 comma-separated fractions: x0,y0,x1,y1")
    x0, y0, x1, y1 = values
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise argparse.ArgumentTypeError("--crop fractions must satisfy 0 <= x0 < x1 <= 1 (same for y)")
    return x0, y0, x1, y1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("-o", "--out", type=Path, required=True, help="output directory")
    parser.add_argument("--dpi", type=int, default=110, help="render resolution (default: 110)")
    parser.add_argument("--pages", help="pages to render, e.g. '7,11-13' (default: all)")
    parser.add_argument(
        "--crop",
        type=parse_crop,
        help="crop to a region given as page fractions x0,y0,x1,y1 from the top-left",
    )
    parser.add_argument("--suffix", default="", help="appended to each output filename")
    args = parser.parse_args()

    doc = pymupdf.open(args.pdf)
    pages = parse_pages(args.pages, len(doc)) if args.pages else range(1, len(doc) + 1)

    args.out.mkdir(parents=True, exist_ok=True)
    for number in pages:
        page = doc[number - 1]
        clip = None
        if args.crop:
            x0, y0, x1, y1 = args.crop
            r = page.rect
            clip = pymupdf.Rect(
                r.x0 + x0 * r.width,
                r.y0 + y0 * r.height,
                r.x0 + x1 * r.width,
                r.y0 + y1 * r.height,
            )
        pix = page.get_pixmap(dpi=args.dpi, clip=clip)
        out_path = args.out / f"p{number:02d}{args.suffix}.png"
        pix.save(out_path)
        print(f"  p{number:02d}  {pix.width}x{pix.height}  ->  {out_path}")

    print(f"\nRendered {len(list(pages))} page(s) at {args.dpi} dpi into {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
