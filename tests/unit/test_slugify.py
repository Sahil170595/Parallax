from parallax.runner.cli import _slugify


def test_slugify():
    assert _slugify("Create a project in Linear") == "create-a-project-in-linear"
    assert _slugify("  Weird__Chars!!  ") == "weird-chars"


