import pytest

from parallax.runner.cli import _slugify


@pytest.mark.skip(reason="Requires live network and credentials; smoke placeholder")
def test_linear_smoke():
    # Placeholder to assert slug consistency for dataset placement
    assert _slugify("Create a project in Linear") == "create-a-project-in-linear"


