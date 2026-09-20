"""Differential tests: hand-written exhaustive oracle vs Engine search."""

import itertools
import random
import sys
import time

sys.path.insert(0, ".")
from app.solver import UNDECIDED, Engine  # noqa: E402


def brute_force(cat_ids, cat_vec, cat_mag, obs_mag, measured, threshold, quota):
    n = len(obs_mag)
    m = len(cat_ids)
    cdp = {}
    for a in range(m):
        for b in range(a + 1, m):
            cdp[(a, b)] = sum(cat_vec[a][k] * cat_vec[b][k] for k in range(3))
    cand = []
    for mg in obs_mag:
        g = sorted((a for a, cm in enumerate(cat_mag) if cm == mg),
                   key=lambda a: cat_ids[a])
        cand.append(g)

    opt = []  # (kept, cost, seq-tuple-with-(-1-before-id))

    def seq_key(mapping):
        return tuple((-1, "") if a < 0 else (0, cat_ids[a]) for a in mapping)

    def rec(i, used, mapping, rejects, cost):
        if rejects > quota:
            return
        if i == n:
            kept = sum(1 for v in mapping if v >= 0)
            opt.append((kept, cost, tuple(mapping)))
            return
        # reject
        mapping.append(-1)
        rec(i + 1, used, mapping, rejects + 1, cost)
        mapping.pop()
        for a in cand[i]:
            if a in used:
                continue
            inc = 0
            for j, b in enumerate(mapping):
                if b >= 0:
                    actual = cdp[(min(a, b), max(a, b))]
                    r = abs(actual - measured[i][j])
                    if r > threshold:
                        break
                    inc += r
            else:
                mapping.append(a)
                used.add(a)
                rec(i + 1, used, mapping, rejects, cost + inc)
                used.discard(a)
                mapping.pop()

    rec(0, set(), [], 0, 0)
    if not opt:
        return None
    k = max(t[0] for t in opt)
    tier = [t for t in opt if t[0] == k]
    r = min(t[1] for t in tier)
    winners = sorted((t for t in tier if t[1] == r), key=lambda t: seq_key(t[2]))
    return k, r, winners[0][2], (winners[1][2] if len(winners) > 1 else None)


def make_instance(rng, n_obs=None, n_cat=None, noise=0.0, bad_quota=None):
    # integer vectors of equal squared norm: use all permutations/signs of
    # a few base triples so many distinct equal-norm vectors exist
    bases = [
        (2, 2, 1),   # norm2 9
        (3, 0, 0),
    ]
    pool = set()
    for (x, y, z) in bases:
        for perm in set(itertools.permutations((x, y, z))):
            for signs in itertools.product((1, -1), repeat=3):
                pool.add(tuple(perm[k] * signs[k] for k in range(3)))
    pool = sorted(pool)  # norm2 == 9 for all
    n_cat = n_cat or rng.randint(8, 24)
    chosen = rng.sample(pool, n_cat)
    mags = [rng.randint(0, 2) for _ in chosen]
    # enforce <=20 per class automatically (n_cat <= 24)
    cat_ids = [f"C{idx:03d}" for idx in range(n_cat)]
    cat_vec = chosen
    cat_mag = mags

    n_obs = n_obs or rng.randint(6, min(10, n_cat))
    true_idx = rng.sample(range(n_cat), n_obs)
    # magnitudes must match the chosen catalog stars (true stars keep class)
    obs_mag = [cat_mag[a] for a in true_idx]
    measured = [[0] * n_obs for _ in range(n_obs)]
    for i in range(n_obs):
        for j in range(i + 1, n_obs):
            a, b = true_idx[i], true_idx[j]
            v = sum(cat_vec[a][k] * cat_vec[b][k] for k in range(3))
            if rng.random() < noise:
                v += rng.choice([-1, 1])
            measured[i][j] = measured[j][i] = v

    # inject pseudostars: replace some tail observations with bogus class
    n_pseudo = rng.randint(0, min(3, n_obs - 6 if n_obs > 6 else 0))
    pseudo_pos = rng.sample(range(n_obs), n_pseudo) if n_pseudo else []
    for p in pseudo_pos:
        obs_mag[p] = rng.randint(0, 2)
        for j in range(n_obs):
            if j != p:
                measured[p][j] = measured[j][p] = rng.randint(-9, 9)

    quota = bad_quota if bad_quota is not None else max(n_pseudo, rng.randint(0, 3))
    threshold = rng.choice([0, 1, 2])
    return {
        "cat_ids": cat_ids, "cat_vec": cat_vec, "cat_mag": cat_mag,
        "obs_mag": obs_mag, "measured": measured,
        "threshold": threshold, "quota": quota,
    }


def run_one(inst):
    oracle = brute_force(**inst)
    eng = Engine(
        inst["cat_ids"], inst["cat_vec"], inst["cat_mag"], inst["obs_mag"],
        inst["measured"], inst["threshold"], inst["quota"],
    )
    res = eng.run()
    if oracle is None:
        assert res["status"] == "incompatible", res
        return res
    k, r, canon, witness = oracle
    assert res["status"] == "optimal", res
    assert res["kept_count"] == k, (k, res)
    assert res["residual_sum"] == r, (r, res)
    got_canon = tuple(
        next(idx for idx, cid in enumerate(inst["cat_ids"]) if cid == s)
        if s is not None else -1
        for s in res["canonical"]["sequence"]
    )
    assert got_canon == canon, (canon, got_canon)
    if witness is None:
        assert res["multiple"] is False and res["witness"] is None
    else:
        assert res["multiple"] is True
        got_w = tuple(
            next(idx for idx, cid in enumerate(inst["cat_ids"]) if cid == s)
            if s is not None else -1
            for s in res["witness"]["sequence"]
        )
        assert got_w == witness, (witness, got_w)
        assert got_w != got_canon
    return res


def test_random_against_bruteforce():
    rng = random.Random(20260920)
    t0 = time.time()
    for trial in range(250):
        inst = make_instance(rng, noise=rng.choice([0.0, 0.1, 0.3]))
        run_one(inst)
    print(f"250 random trials OK in {time.time()-t0:.1f}s")


def test_deliberately_incompatible():
    rng = random.Random(7)
    for _ in range(20):
        inst = make_instance(rng)
        inst["quota"] = 0
        # corrupt every observation's class so no pairing exists
        inst["obs_mag"] = [m + 100 for m in inst["obs_mag"]]
        # validator would reject unknown classes only beyond quota; bypass
        # Engine directly (it knows nothing of class-count validation)
        with_quota = dict(inst)
        # give quota 3 but 6 unknown-class observations -> still incompatible
        with_quota["quota"] = 3
        res = Engine(
            with_quota["cat_ids"], with_quota["cat_vec"], with_quota["cat_mag"],
            with_quota["obs_mag"], with_quota["measured"],
            with_quota["threshold"], with_quota["quota"],
        ).run()
        assert res["status"] == "incompatible", res
    print("incompatible cases OK")


def test_tight_quota_incompatible():
    rng = random.Random(11)
    # 4 pseudostars but only 3 slots -> incompatible
    for _ in range(10):
        inst = make_instance(rng, n_obs=10)
        # scramble all measurements so almost nothing fits, quota 3
        for i in range(len(inst["measured"])):
            for j in range(len(inst["measured"])):
                if i != j:
                    inst["measured"][i][j] = rng.choice([40, 50, -40])
        inst["threshold"] = 0
        inst["quota"] = 3
        run_one(inst)  # brute force decides compatible or not; engine must agree
    print("tight-quota agreement OK")


if __name__ == "__main__":
    test_random_against_bruteforce()
    test_deliberately_incompatible()
    test_tight_quota_incompatible()
    print("ALL TESTS PASSED")
