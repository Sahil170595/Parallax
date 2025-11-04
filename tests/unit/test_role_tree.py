from parallax.observer.role_tree import jaccard_similarity
from parallax.core.schemas import RoleNode


def test_jaccard_similarity_basic():
    a = [RoleNode(role="button", name="Create"), RoleNode(role="dialog", name=None)]
    b = [RoleNode(role="button", name="Create"), RoleNode(role="textbox", name="Name")]
    sim = jaccard_similarity(a, b)
    assert 0 < sim < 1


