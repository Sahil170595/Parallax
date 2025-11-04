from __future__ import annotations

from typing import List

from parallax.core.schemas import RoleNode


def jaccard_similarity(a: List[RoleNode], b: List[RoleNode]) -> float:
    set_a = set((n.role, n.name) for n in a)
    set_b = set((n.role, n.name) for n in b)
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


