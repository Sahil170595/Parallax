from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from PIL import Image, ImageDraw  # type: ignore


def redact_screenshot(
    image_path: Path,
    regions: Iterable[Dict[str, Any]],
    config: Dict[str, Any],
) -> Path:
    """Redact sensitive fields in screenshot based on bounding-box regions."""

    redact_cfg = config.get("redact", {})
    if not redact_cfg.get("enabled", False):
        return image_path

    regions = list(regions)
    if not regions:
        return image_path

    fill_color = redact_cfg.get("fill_color", (0, 0, 0, 230))
    if isinstance(fill_color, str):  # Allow hex strings like "#000000"
        fill_color = _hex_to_rgba(fill_color)

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")

        for region in regions:
            x = max(0, int(region.get("x", 0)))
            y = max(0, int(region.get("y", 0)))
            width = int(max(0, region.get("width", 0)))
            height = int(max(0, region.get("height", 0)))
            if width == 0 or height == 0:
                continue
            draw.rectangle(
                [x, y, x + width, y + height],
                fill=fill_color,
            )

        img.save(image_path)
        return image_path
    except Exception:
        return image_path


def _hex_to_rgba(color: str) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    if len(color) == 6:
        r, g, b = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
        return r, g, b, 230
    if len(color) == 8:
        r, g, b, a = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4, 6))
        return r, g, b, a
    return 0, 0, 0, 230

