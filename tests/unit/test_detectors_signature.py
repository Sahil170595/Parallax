import pytest

from parallax.observer.detectors import Detectors


def test_hash_signature_stable(monkeypatch):
    d = Detectors({})
    roles = []
    # Access private for unit stability
    sig1 = d._hash_signature("https://example.com", roles)
    sig2 = d._hash_signature("https://example.com", roles)
    assert sig1 == sig2


class DummyPage:
    def __init__(self, initial_viewport):
        self.viewport_size = initial_viewport
        self.set_calls = []
        self.screenshot_calls = []

    async def set_viewport_size(self, size):
        self.set_calls.append(dict(size))
        self.viewport_size = dict(size)

    async def screenshot(self, *_, **kwargs):
        self.screenshot_calls.append(kwargs)


@pytest.mark.asyncio
async def test_screenshot_tablet_restores_original_viewport(tmp_path):
    page = DummyPage({"width": 1200, "height": 900})
    detectors = Detectors(
        {
            "capture": {
                "desktop_viewport": {"width": 1366, "height": 832},
                "tablet_viewport": {"width": 834, "height": 1112},
            }
        }
    )

    await detectors._screenshot_tablet(page, tmp_path, 1)

    assert page.set_calls[0] == {"width": 834, "height": 1112}
    assert page.set_calls[-1] == {"width": 1200, "height": 900}
    assert page.viewport_size == {"width": 1200, "height": 900}


@pytest.mark.asyncio
async def test_screenshot_mobile_restores_or_falls_back(tmp_path):
    page = DummyPage(None)
    detectors = Detectors(
        {
            "capture": {
                "desktop_viewport": {"width": 1366, "height": 832},
                "mobile_viewport": {"width": 390, "height": 844},
            }
        }
    )

    await detectors._screenshot_mobile(page, tmp_path, 2)

    assert page.set_calls[0] == {"width": 390, "height": 844}
    assert page.set_calls[-1] == {"width": 1366, "height": 832}
    assert page.viewport_size == {"width": 1366, "height": 832}
