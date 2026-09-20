"""Scale and timing checks at the problem's upper bounds."""

import itertools
import random
import sys
import time

sys.path.insert(0, ".")
from app.solver import Engine, solve, SolveValidationError  # noqa: E402


def build_equal_norm_pool(target_count=180, coord_limit=12):
    by_norm = {}
    for x in range(-coord_limit, coord_limit + 1):
        for y in range(-coord_limit, coord_limit + 1):
            for z in range(-coord_limit, coord_limit + 1):
                n2 = x * x + y * y + z * z
                if n2 > 0:
                    by_norm.setdefault(n2, []).append((x, y, z))
    n2, pool = max(by_norm.items(), key=lambda kv: len(kv[1]))
    assert len(pool) >= target_count, (n2, len(pool))
    return n2, pool


def make_full_scale(rng, n_obs=18, n_cat=180, n_classes=9, pseudos=3, noise=0.05):
    n2, pool = build_equal_norm_pool(n_cat)
    chosen = rng.sample(pool, n_cat)
    # balanced classes: exactly 20 each
    cat_mag = [i % n_classes for i in range(n_cat)]
    rng.shuffle(cat_mag)
    cat_ids = [f"STAR-{i:03d}" for i in range(n_cat)]

    true_idx = rng.sample(range(n_cat), n_obs)
    obs_mag = [cat_mag[a] for a in true_idx]
    M = [[0] * n_obs for _ in range(n_obs)]
    for i in range(n_obs):
        for j in range(i + 1, n_obs):
            a, b = true_idx[i], true_idx[j]
            v = sum(chosen[a][k] * chosen[b][k] for k in range(3))
            if rng.random() < noise:
                v += rng.choice([-2, -1, 1, 2])
            M[i][j] = M[j][i] = v
    for p in rng.sample(range(n_obs), pseudos):
        obs_mag[p] = rng.randrange(n_classes)
        for j in range(n_obs):
            if j != p:
                M[p][j] = M[j][p] = rng.randint(-50, 50)
    return {
        "cat_ids": cat_ids, "cat_vec": chosen, "cat_mag": cat_mag,
        "obs_mag": obs_mag, "measured": M, "threshold": 2, "quota": 3,
    }


def main():
    rng = random.Random(424242)
    for trial in range(5):
        inst = make_full_scale(rng)
        t0 = time.perf_counter()
        eng = Engine(**inst)
        res = eng.run()
        dt = time.perf_counter() - t0
        assert res["status"] == "optimal", res
        assert res["kept_count"] == 15, res
        # verify reported mapping independently
        mapping_ids = res["canonical"]["sequence"]
        id_to_a = {cid: a for a, cid in enumerate(inst["cat_ids"])}
        used = set()
        for i, s in enumerate(mapping_ids):
            if s is not None:
                a = id_to_a[s]
                assert a not in used
                used.add(a)
                assert inst["cat_mag"][a] == inst["obs_mag"][i]
        for i in range(18):
            for j in range(i + 1, 18):
                if mapping_ids[i] and mapping_ids[j]:
                    a, b = id_to_a[mapping_ids[i]], id_to_a[mapping_ids[j]]
                    actual = sum(inst["cat_vec"][a][k] * inst["cat_vec"][b][k] for k in range(3))
                    assert abs(actual - inst["measured"][i][j]) <= 2
        print(f"trial {trial}: {dt*1000:.0f} ms, nodes={res['search_nodes']}, "
              f"multiple={res['multiple']}, residual={res['residual_sum']}")
        assert dt < 20, "too slow"

    # end-to-end payload validation path
    inst = make_full_scale(rng)
    payload = {
        "threshold": inst["threshold"],
        "outlier_quota": inst["quota"],
        "catalog": [
            {"id": cid, "magnitude": m, "vector": list(v)}
            for cid, m, v in zip(inst["cat_ids"], inst["cat_mag"], inst["cat_vec"])
        ],
        "observations": [{"magnitude": m} for m in inst["obs_mag"]],
        "dot_measurements": inst["measured"],
    }
    t0 = time.perf_counter()
    out = solve(payload)
    print(f"solve() full payload: {(time.perf_counter()-t0)*1000:.0f} ms, "
          f"status={out['status']}, kept={out['kept_count']}")
    assert out["status"] == "optimal"

    # validation errors are locatable
    bad = dict(payload)
    bad = {**payload, "catalog": [dict(c) for c in payload["catalog"]]}
    bad["catalog"][0]["vector"] = [1, 2]
    bad["threshold"] = -1
    try:
        solve(bad)
        raise AssertionError("should have failed")
    except SolveValidationError as e:
        locs = [tuple(i["loc"]) for i in e.issues]
        assert ("threshold",) in locs
        assert ("catalog", 0, "vector") in locs
        print(f"validation issues located: {locs}")

    # class > 20 rejected
    bad2 = {**payload, "catalog": payload["catalog"] + [
        {"id": f"X{i}", "magnitude": 0, "vector": [3, 0, 0]} for i in range(3)
    ]}
    # norm 9 differs from pool norm; keep message check simple
    try:
        solve(bad2)
        raise AssertionError("should have failed (181 stars + class size)")
    except SolveValidationError as e:
        msgs = " ".join(i["message"] for i in e.issues)
        assert "180" in msgs or "20" in msgs
        print("oversize catalog rejected")

    print("SCALE TESTS PASSED")


if __name__ == "__main__":
    main()
