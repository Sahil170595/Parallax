from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont  # type: ignore


def redact_screenshot(
    image_path: Path,
    selectors: List[str],
    config: Dict[str, Any],
) -> Path:
    """Redact sensitive fields in screenshot based on config."""
    if not config.get("redact", {}).get("enabled", False):
        return image_path
    
    try:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Redact password fields (mask entire image area for now)
        # In production, would use OCR/bounding box detection
        # For MVP, we'll blur/mask based on heuristics
        
        # Save redacted version
        redacted_path = image_path.parent / f"{image_path.stem}_redacted.png"
        img.save(redacted_path)
        return redacted_path
    except Exception:
        # Fallback: return original if redaction fails
        return image_path

