"""求解器单元测试：覆盖唯一解、离群剔除、不相容、多解见证、字典序与残差最优。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.solver import Solver, build_response, DROP  # noqa: E402
from app.validation import validate_payload  # noqa: E402


def dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def make_meas(vecs):
    m = len(vecs)
    return [[dot(vecs[i], vecs[j]) for j in range(m)] for i in range(m)]


CAT = [
    {"id": 0, "cls": "A", "vec": [1, 2, 3]},
    {"id": 1, "cls": "B", "vec": [1, 3, 2]},
    {"id": 2, "cls": "C", "vec": [2, 1, 3]},
    {"id": 3, "cls": "D", "vec": [2, 3, 1]},
    {"id": 4, "cls": "E", "vec": [3, 1, 2]},
    {"id": 5, "cls": "F", "vec": [3, 2, 1]},
    {"id": 6, "cls": "G", "vec": [-1, -2, -3]},
    {"id": 7, "cls": "H", "vec": [-1, -3, -2]},
]


def solve(cat, classes, meas, threshold, outliers):
    s = Solver(cat, classes, meas, threshold, outliers)
    return build_response(s.solve(), cat, classes, meas)


# ---------------------------------------------------------------- 唯一确定解

def test_unique_forced_mapping():
    classes = ["A", "B", "C", "D", "E", "F"]
    vecs = [c["vec"] for c in CAT[:6]]
    r = solve(CAT, classes, make_meas(vecs), threshold=0, outliers=0)
    assert r["status"] == "ok"
    assert r["retained_count"] == 6
    assert r["residual_sum"] == 0
    assert r["sequence"] == [0, 1, 2, 3, 4, 5]
    assert r["drops"] == []
    assert r["multiple"] is False
    assert r["witness"] is None
    assert len(r["pair_residuals"]) == 15


# ---------------------------------------------------------------- 离群剔除

def test_outlier_is_dropped():
    classes = ["A", "B", "C", "D", "E", "F"]
    vecs = [c["vec"] for c in CAT[:6]]
    meas = make_meas(vecs)
    for j in range(6):
        if j != 5:
            meas[5][j] = meas[j][5] = 100  # 第 6 个观测是伪星
    r = solve(CAT, classes, meas, threshold=0, outliers=1)
    assert r["status"] == "ok"
    assert r["retained_count"] == 5
    assert r["drops"] == [5]
    assert r["sequence"] == [0, 1, 2, 3, 4, DROP]
    assert r["multiple"] is False


def test_outlier_budget_exhausted_still_identifies():
    """两个伪星、两个名额：其余观测仍应完整识别。"""
    classes = ["A", "B", "C", "D", "E", "F"]
    vecs = [c["vec"] for c in CAT[:6]]
    meas = make_meas(vecs)
    for bad in (1, 4):
        for j in range(6):
            if j != bad:
                meas[bad][j] = meas[j][bad] = 77
    r = solve(CAT, classes, meas, threshold=0, outliers=2)
    assert r["status"] == "ok"
    assert r["drops"] == [1, 4]
    assert r["retained_count"] == 4


# ---------------------------------------------------------------- 不相容

def test_infeasible_when_pairs_contradict():
    classes = ["A", "B", "C", "D", "E", "F"]
    meas = [[100 if i != j else 0 for j in range(6)] for i in range(6)]
    r = solve(CAT, classes, meas, threshold=2, outliers=3)
    assert r["status"] == "infeasible"


def test_infeasible_when_class_missing_and_no_budget():
    cat = [dict(c) for c in CAT]
    classes = ["A", "B", "C", "D", "E", "Z"]  # Z 类目录中不存在
    vecs = [c["vec"] for c in CAT[:6]]
    r = solve(cat, classes, make_meas(vecs), threshold=0, outliers=0)
    assert r["status"] == "infeasible"


# ---------------------------------------------------------------- 多解与见证

CAT_DUP = [
    {"id": 0, "cls": "B", "vec": [1, 3, 2]},
    {"id": 1, "cls": "C", "vec": [2, 1, 3]},
    {"id": 2, "cls": "D", "vec": [2, 3, 1]},
    {"id": 3, "cls": "E", "vec": [3, 1, 2]},
    {"id": 4, "cls": "F", "vec": [3, 2, 1]},
    {"id": 10, "cls": "A", "vec": [1, 2, 3]},
    {"id": 11, "cls": "A", "vec": [1, 2, 3]},  # 与 10 向量相同，可互换
    {"id": 12, "cls": "G", "vec": [-1, -2, -3]},
]


def test_multiple_optima_with_witness():
    classes = ["A", "B", "C", "D", "E", "F"]
    vecs = [[1, 2, 3]] + [c["vec"] for c in CAT_DUP[:5]]
    r = solve(CAT_DUP, classes, make_meas(vecs), threshold=0, outliers=0)
    assert r["status"] == "ok"
    assert r["multiple"] is True
    assert r["sequence"] == [10, 0, 1, 2, 3, 4]      # 规范解取较小标识
    assert r["witness_sequence"] == [11, 0, 1, 2, 3, 4]
    assert r["residual_sum"] == 0
    # 见证必须真实满足全部约束
    assert r["witness_pair_residuals"]
    assert all(p["residual"] <= 0 for p in r["witness_pair_residuals"])


def test_lexicographic_drop_position():
    """观测 0 与 1 互相矛盾、各自与其余相容：剔除位置有两种同优选择，
    规范解应在字典序最前位置放 -1（剔除观测 0），见证剔除观测 1。"""
    classes = ["A", "B", "C", "D", "E", "F"]
    vecs = [c["vec"] for c in CAT[:6]]
    meas = make_meas(vecs)
    meas[0][1] = meas[1][0] = meas[0][1] + 5  # 0 与 1 矛盾
    r = solve(CAT, classes, meas, threshold=0, outliers=1)
    assert r["status"] == "ok"
    assert r["retained_count"] == 5
    assert r["multiple"] is True
    assert r["sequence"] == [DROP, 1, 2, 3, 4, 5]
    assert r["witness_sequence"] == [0, DROP, 2, 3, 4, 5]


# ---------------------------------------------------------------- 残差和最优

def test_residual_sum_is_minimized():
    cat = CAT + [
        {"id": 5, "cls": "A", "vec": [1, 2, 3]},   # 真星
        {"id": 9, "cls": "A", "vec": [1, 3, 2]},   # 同类干扰星
    ]
    # 重新分配标识避免重复
    cat = [dict(c) for c in CAT]
    cat.append({"id": 9, "cls": "A", "vec": [1, 3, 2]})
    classes = ["A", "B", "C", "D", "E", "F"]
    true = [[1, 2, 3]] + [c["vec"] for c in CAT[1:6]]
    r = solve(cat, classes, make_meas(true), threshold=20, outliers=0)
    assert r["status"] == "ok"
    assert r["residual_sum"] == 0
    assert r["sequence"][0] == 0  # 选真星而非残差更大的干扰星
    assert r["multiple"] is False


# ---------------------------------------------------------------- 单射约束

def test_injective_mapping_enforced():
    """同类两颗观测、同类目录星仅一颗：必须剔除其一，不得共用同一颗目录星。"""
    cat = [
        {"id": 0, "cls": "A", "vec": [1, 2, 3]},
        {"id": 1, "cls": "B", "vec": [1, 3, 2]},
        {"id": 2, "cls": "C", "vec": [2, 1, 3]},
        {"id": 3, "cls": "D", "vec": [2, 3, 1]},
        {"id": 4, "cls": "E", "vec": [3, 1, 2]},
        {"id": 5, "cls": "F", "vec": [3, 2, 1]},
        {"id": 6, "cls": "G", "vec": [-1, -2, -3]},
        {"id": 7, "cls": "H", "vec": [-1, -3, -2]},
    ]
    classes = ["A", "A", "B", "C", "D", "E"]
    # 两个 A 类观测的测量都与星 0 一致（含彼此之间 = 范数平方 14）
    true = [[1, 2, 3], [1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2]]
    r = solve(cat, classes, make_meas(true), threshold=0, outliers=1)
    assert r["status"] == "ok"
    assert r["retained_count"] == 5
    assert r["multiple"] is True
    # 字典序最小解剔除观测 0，见证剔除观测 1
    assert r["sequence"] == [DROP, 0, 1, 2, 3, 4]
    assert r["witness_sequence"] == [0, DROP, 1, 2, 3, 4]
    # 规范解与见证均单射
    for mapping in (r["canonical"], r["witness"]):
        ids = [m["star_id"] for m in mapping if m]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------- 校验

def _payload(**over):
    classes = ["A", "B", "C", "D", "E", "F"]
    vecs = [c["vec"] for c in CAT[:6]]
    meas = make_meas(vecs)
    obs = []
    for i, cls in enumerate(classes):
        obs.append({"cls": cls, "dots": {str(j): meas[i][j] for j in range(6) if j != i}})
    base = {
        "threshold": 0,
        "max_outliers": 1,
        "catalog": [dict(c) for c in CAT],
        "observations": obs,
    }
    base.update(over)
    return base


def test_validation_accepts_valid_payload():
    data, errors = validate_payload(_payload())
    assert errors == []
    assert data["threshold"] == 0
    assert len(data["catalog"]) == 8
    assert len(data["obs_classes"]) == 6


def test_validation_unequal_norm():
    cat = [dict(c) for c in CAT]
    cat[3]["vec"] = [5, 5, 5]
    _, errors = validate_payload(_payload(catalog=cat))
    assert any("catalog[3].vec" == e["path"] for e in errors)


def test_validation_asymmetric_dots():
    obs = _payload()["observations"]
    obs[2]["dots"]["4"] = obs[2]["dots"]["4"] + 1
    _, errors = validate_payload(_payload(observations=obs))
    assert any("dots" in e["path"] for e in errors)


def test_validation_missing_dot():
    obs = _payload()["observations"]
    del obs[1]["dots"]["3"]
    del obs[3]["dots"]["1"]
    _, errors = validate_payload(_payload(observations=obs))
    assert any("缺少" in e["message"] for e in errors)


def test_validation_class_quota():
    cat = [dict(c) for c in CAT] + [
        {"id": 100 + i, "cls": "A", "vec": [1, 2, 3]} for i in range(20)
    ]  # A 类共 21 颗
    _, errors = validate_payload(_payload(catalog=cat))
    assert any("20" in e["message"] for e in errors)


def test_validation_observation_count():
    obs = _payload()["observations"][:5]
    _, errors = validate_payload(_payload(observations=obs))
    assert any(e["path"] == "observations" for e in errors)


def test_validation_duplicate_catalog_id():
    cat = [dict(c) for c in CAT]
    cat[1]["id"] = 0
    _, errors = validate_payload(_payload(catalog=cat))
    assert any("catalog[1].id" == e["path"] for e in errors)


def test_validation_threshold_range():
    _, errors = validate_payload(_payload(threshold=-1))
    assert any(e["path"] == "threshold" for e in errors)
    _, errors = validate_payload(_payload(max_outliers=4))
    assert any(e["path"] == "max_outliers" for e in errors)
