"""Built-in audit scenarios.

Single source of truth shared by the web console (``GET /api/scenarios``)
and by the Docker ``verify`` acceptance service.  Each catalog uses
equal-norm integer vectors (norm^2 is noted in the scenario comments).
"""

from __future__ import annotations


def _star(sid: str, mag: int, v: tuple[int, int, int]) -> dict:
    return {"id": sid, "magnitude": mag, "vector": list(v)}


def _matrix(rows: list[list[int]]) -> list[list[int]]:
    n = len(rows)
    m = [row[:] for row in rows]
    for i in range(n):
        for j in range(n):
            if i == j:
                m[i][j] = 0
            else:
                m[i][j] = rows[i][j] if i < j else rows[j][i]
    return m


# Catalog A (all vectors have norm^2 = 161).  Geometry is deliberately
# asymmetric so that the unique scenario has a single optimal injection.
CATALOG_A = [
    _star("STAR-01", 0, (-8, -4, 9)),
    _star("STAR-02", 0, (5, 10, 6)),
    _star("STAR-03", 1, (-2, -6, 11)),
    _star("STAR-04", 1, (4, -1, 12)),
    _star("STAR-05", 1, (1, -4, 12)),
    _star("STAR-06", 1, (-10, -6, -5)),
    _star("STAR-07", 2, (2, -6, 11)),
    _star("STAR-08", 2, (6, -10, -5)),
    _star("STAR-09", 2, (6, -2, -11)),
    _star("STAR-10", 2, (-11, -6, -2)),
]


def _scenario_unique() -> dict:
    """Five true stars plus one class-0 pseudostar; unique optimum."""
    observations = [
        {"magnitude": 1},  # 0 -> STAR-06
        {"magnitude": 2},  # 1 -> STAR-08
        {"magnitude": 1},  # 2 -> STAR-03
        {"magnitude": 2},  # 3 -> STAR-09
        {"magnitude": 0},  # 4 -> STAR-02
        {"magnitude": 0},  # 5: pseudostar (999 measures fit nothing)
    ]
    dots = _matrix(
        [
            [0, 25, 1, 7, -140, 999],
            [25, 0, -7, 111, -100, 999],
            [1, -7, 0, -121, -4, 999],
            [7, 111, -121, 0, -56, 999],
            [-140, -100, -4, -56, 0, 999],
            [999, 999, 999, 999, 999, 0],
        ]
    )
    return {
        "key": "unique",
        "title": "唯一最优映射（含 1 颗伪星）",
        "description": (
            "6 个有序观测，前 5 颗为真实星（点积为精确整数测量，"
            "目录向量平方范数均为 161），第 6 颗是亮度 0 类伪星，"
            "其 999 的测量值不可能与任何目录点积相容。"
            "阈值 1、离群名额 2：最优解保留 5 颗、残差和 0、剔除 [5]，"
            "且前两级最优的字典序解唯一（无第二见证）。"
        ),
        "threshold": 1,
        "outlier_quota": 2,
        "catalog": [dict(s) for s in CATALOG_A],
        "observations": observations,
        "dot_measurements": dots,
        "expect": {
            "status": "optimal",
            "kept_count": 5,
            "residual_sum": 0,
            "multiple": False,
            "canonical_sequence": [
                "STAR-06", "STAR-08", "STAR-03", "STAR-09", "STAR-02", None,
            ],
            "rejected": [5],
        },
    }


# Catalog B (norm^2 == 9).  The four class-2 stars lie in the y==z plane,
# so STAR-B3 (+y axis) and STAR-B4 (+z axis) are twins against the field.
CATALOG_B = [
    _star("STAR-B1", 0, (3, 0, 0)),
    _star("STAR-B2", 0, (-3, 0, 0)),
    _star("STAR-B3", 1, (0, 3, 0)),
    _star("STAR-B4", 1, (0, 0, 3)),
    _star("STAR-B5", 1, (0, -3, 0)),
    _star("STAR-B6", 1, (0, 0, -3)),
    _star("STAR-B7", 2, (1, 2, 2)),
    _star("STAR-B8", 2, (-1, 2, 2)),
    _star("STAR-B9", 2, (1, -2, -2)),
    _star("STAR-B10", 2, (-1, -2, -2)),
]


def _scenario_multiple() -> dict:
    """STAR-B3 and STAR-B4 are geometric twins w.r.t. the whole field."""
    observations = [
        {"magnitude": 0},  # 0 -> STAR-B1
        {"magnitude": 1},  # 1 -> STAR-B3 or STAR-B4 (twins)
        {"magnitude": 1},  # 2 -> STAR-B4 or STAR-B3 (twins)
        {"magnitude": 2},  # 3 -> STAR-B7
        {"magnitude": 2},  # 4 -> STAR-B8
        {"magnitude": 2},  # 5 -> STAR-B9
    ]
    dots = _matrix(
        [
            [0, 0, 0, 3, -3, 3],
            [0, 0, 0, 6, 6, -6],
            [0, 0, 0, 6, 6, -6],
            [3, 6, 6, 0, 7, -7],
            [-3, 6, 6, 7, 0, -9],
            [3, -6, -6, -7, -9, 0],
        ]
    )
    return {
        "key": "multiple",
        "title": "多解：孪生星导致两份同优注入",
        "description": (
            "STAR-B3=(0,3,0) 与 STAR-B4=(0,0,3) 相对整片星场几何等价"
            "（其余保留星均位于 y=z 平面），观测 1、2 互换后保留数（6）与"
            "残差和（0）完全相同。阈值 0、离群名额 0：服务返回多解标志、"
            "字典序规范映射，以及另一份真实见证映射。"
        ),
        "threshold": 0,
        "outlier_quota": 0,
        "catalog": [dict(s) for s in CATALOG_B],
        "observations": observations,
        "dot_measurements": dots,
        "expect": {
            "status": "optimal",
            "kept_count": 6,
            "residual_sum": 0,
            "multiple": True,
            "canonical_sequence": [
                "STAR-B1", "STAR-B3", "STAR-B4", "STAR-B7", "STAR-B8", "STAR-B9",
            ],
            "witness_sequence": [
                "STAR-B1", "STAR-B4", "STAR-B3", "STAR-B7", "STAR-B8", "STAR-B9",
            ],
            "rejected": [],
        },
    }


def _scenario_incompatible() -> dict:
    """Six class-0 observations but only two class-0 catalog stars."""
    observations = [{"magnitude": 0} for _ in range(6)]
    dots = _matrix([[0] * 6 for _ in range(6)])
    return {
        "key": "incompatible",
        "title": "不相容：同类候选星不足",
        "description": (
            "6 个观测全部为亮度 0 类，但星表中只有 2 颗 0 类星；"
            "注入映射至多保留 2 颗观测，至少需剔除 4 颗，超过 2 个离群名额。"
            "阈值 0：不存在可行映射，页面须明确报不相容。"
        ),
        "threshold": 0,
        "outlier_quota": 2,
        "catalog": [dict(s) for s in CATALOG_A],
        "observations": observations,
        "dot_measurements": dots,
        "expect": {"status": "incompatible"},
    }


SCENARIOS = {
    "unique": _scenario_unique(),
    "multiple": _scenario_multiple(),
    "incompatible": _scenario_incompatible(),
}


def list_scenarios() -> list[dict]:
    out = []
    for key, sc in SCENARIOS.items():
        out.append(
            {
                "key": key,
                "title": sc["title"],
                "description": sc["description"],
                "threshold": sc["threshold"],
                "outlier_quota": sc["outlier_quota"],
                "catalog": sc["catalog"],
                "observations": sc["observations"],
                "dot_measurements": sc["dot_measurements"],
            }
        )
    return out
