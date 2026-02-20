from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

from PIL import Image


def nontransparent_bbox(img: Image.Image) -> Tuple[int, int, int, int] | None:
    rgba = img.convert("RGBA")
    alpha = rgba.split()[-1]
    return alpha.getbbox()


def stickerize(input_path: Path, output_path: Path, canvas_px: int = 5000, padding_pct: float = 0.08) -> None:
    with Image.open(input_path) as src:
        rgba = src.convert("RGBA")
        bbox = nontransparent_bbox(rgba)
        if bbox is None:
            # Keep transparent canvas if source is empty.
            out = Image.new("RGBA", (canvas_px, canvas_px), (0, 0, 0, 0))
            out.save(output_path, format="PNG")
            return

        cropped = rgba.crop(bbox)
        max_dim = max(cropped.width, cropped.height)
        pad = int(max_dim * max(0.0, padding_pct))
        side = max_dim + (pad * 2)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        offset = ((side - cropped.width) // 2, (side - cropped.height) // 2)
        square.alpha_composite(cropped, dest=offset)
        final = square.resize((canvas_px, canvas_px), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.save(output_path, format="PNG")


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert transparent artwork into sticker-friendly square PNG.")
    ap.add_argument("--input", required=True, help="Input PNG path.")
    ap.add_argument("--output", required=True, help="Output PNG path.")
    ap.add_argument("--canvas-px", type=int, default=5000)
    ap.add_argument("--padding-pct", type=float, default=0.08)
    args = ap.parse_args()

    stickerize(
        input_path=Path(args.input).resolve(),
        output_path=Path(args.output).resolve(),
        canvas_px=max(256, int(args.canvas_px)),
        padding_pct=max(0.0, float(args.padding_pct)),
    )
    print(f"Stickerized asset written: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
