from pathlib import Path

from PIL import Image

from parallax.core.capture import redact_screenshot


def test_redact_screenshot_masks_regions(tmp_path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (50, 50), color="white").save(image_path)

    config = {"redact": {"enabled": True, "fill_color": "#000000"}}
    regions = [{"x": 5, "y": 5, "width": 10, "height": 10}]

    redacted_path = redact_screenshot(image_path, regions, config)

    assert redacted_path == image_path
    img = Image.open(redacted_path)
    # Pixel inside the redaction region should be dark after masking
    assert img.getpixel((7, 7))[:3] != (255, 255, 255)
    # Pixel outside should remain unaffected
    assert img.getpixel((30, 30))[:3] == (255, 255, 255)
