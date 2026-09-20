"""Executable acceptance suite for the ``verify`` Compose service.

Usage::

    python -m app.verify [base_url]

Exit code 0 means every acceptance check passed.  The suite exercises the
real HTTP API (never the solver in-process): health, all built-in
scenarios, a 422 validation case with locatable reasons, and randomly
generated instances whose reported optimum is independently recomputed by
an exhaustive oracle running inside this service.
"""

from __future__ import annotations

import itertools
import random
import sys
import time

import httpx

from .scenarios import SCENARIOS


def _brute_oracle(catalog, observations, dots, threshold, quota):
    n = len(observations)
    by_class: dict[int, list[tuple[str, tuple]]] = {}
    for s in catalog:
        by_class.setdefault(s["magnitude"], []).append((s["id"], tuple(s["vector"])))
    for g in by_class.values():
        g.sort()
    cdp = {}
    for i, s1 in enumerate(catalog):
        va = s1["vector"]
        for j in range(i + 1, len(catalog)):
            vb = catalog[j]["vector"]
            cdp[(s1["id"], catalog[j]["id"])] = (
                va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]
            )

    best = {"kept": -1, "cost": None, "seq": None}

    # Tie-break convention (must match the solver exactly): a rejected
    # observation sorts before every catalog identifier in the sequence.
    def key(seq):
        return tuple((0, "") if x is None else (1, x) for x in seq)

    def rec(i, used, seq, rejects, cost):
        if rejects > quota:
            return
        if i == n:
            kept = n - rejects
            if (
                kept > best["kept"]
                or (kept == best["kept"] and cost < (best["cost"] if best["cost"] is not None else 1 << 60))
                or (
                    kept == best["kept"]
                    and cost == best["cost"]
                    and (best["seq"] is None or key(seq) < key(best["seq"]))
                )
            ):
                best["kept"] = kept
                best["cost"] = cost
                best["seq"] = list(seq)
            return
        seq.append(None)
        rec(i + 1, used, seq, rejects + 1, cost)
        seq.pop()
        for sid, vec in by_class.get(observations[i]["magnitude"], []):
            if sid in used:
                continue
            inc = 0
            for j, prior in enumerate(seq):
                if prior is not None:
                    a, b = sorted((sid, prior))
                    r = abs(cdp[(a, b)] - dots[i][j])
                    if r > threshold:
                        break
                    inc += r
            else:
                seq.append(sid)
                used.add(sid)
                rec(i + 1, used, seq, rejects, cost + inc)
                used.discard(sid)
                seq.pop()

    rec(0, set(), [], 0, 0)
    return None if best["seq"] is None else (best["kept"], best["cost"], best["seq"])


def _random_case(rng):
    bases = [(2, 2, 1), (3, 0, 0), (2, -1, 2), (1, 2, -2)]
    pool = set()
    for (x, y, z) in bases:
        for perm in set(itertools.permutations((x, y, z))):
            for signs in itertools.product((1, -1), repeat=3):
                pool.add(tuple(perm[k] * signs[k] for k in range(3)))
    pool = sorted(pool)
    n_cat = rng.randint(8, 12)
    chosen = rng.sample(pool, n_cat)
    mags = [rng.randint(0, 2) for _ in chosen]
    catalog = [
        {"id": f"C{i:02d}", "magnitude": mags[i], "vector": list(chosen[i])}
        for i in range(n_cat)
    ]
    n = rng.randint(6, min(8, n_cat))
    true_idx = rng.sample(range(n_cat), n)
    obs_mag = [mags[a] for a in true_idx]
    dots = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = chosen[true_idx[i]], chosen[true_idx[j]]
            v = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
            if rng.random() < 0.15:
                v += rng.choice([-1, 1])
            dots[i][j] = dots[j][i] = v
    pseudo = rng.randint(0, min(2, n - 6))
    for p in rng.sample(range(n), pseudo):
        obs_mag[p] = rng.randint(0, 2)
        for j in range(n):
            if j != p:
                dots[p][j] = dots[j][p] = rng.randint(-9, 9)
    return {
        "threshold": rng.choice([0, 1, 2]),
        "outlier_quota": rng.randint(pseudo, 3),
        "catalog": catalog,
        "observations": [{"magnitude": m} for m in obs_mag],
        "dot_measurements": dots,
    }


class Checker:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=30)
        self.passed = 0
        self.failed: list[str] = []

    def check(self, name: str, cond: bool, detail: str = ""):
        if cond:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed.append(f"{name}: {detail}")
            print(f"  FAIL  {name}  {detail}")

    def health(self):
        print("[health]")
        r = self.client.get("/api/health")
        self.check("GET /api/health 200", r.status_code == 200, str(r.status_code))
        self.check("health.status == ok", r.json().get("status") == "ok", r.text)

    def scenarios(self):
        print("[built-in scenarios]")
        for key, sc in SCENARIOS.items():
            exp = sc["expect"]
            payload = {
                "threshold": sc["threshold"],
                "outlier_quota": sc["outlier_quota"],
                "catalog": sc["catalog"],
                "observations": sc["observations"],
                "dot_measurements": sc["dot_measurements"],
            }
            r = self.client.post("/api/solve", json=payload)
            self.check(f"{key}: HTTP 200", r.status_code == 200, f"{r.status_code} {r.text}")
            if r.status_code != 200:
                continue
            data = r.json()
            self.check(f"{key}: status {exp['status']}", data["status"] == exp["status"],
                       f"got {data['status']}")
            if exp["status"] != "optimal":
                self.check(f"{key}: incompatible message shown",
                           bool(data.get("message")), str(data)[:200])
                continue
            self.check(f"{key}: kept_count {exp['kept_count']}",
                       data["kept_count"] == exp["kept_count"], str(data["kept_count"]))
            self.check(f"{key}: residual_sum {exp['residual_sum']}",
                       data["residual_sum"] == exp["residual_sum"], str(data["residual_sum"]))
            self.check(f"{key}: multiple flag {exp['multiple']}",
                       data["multiple"] == exp["multiple"], str(data["multiple"]))
            seq = data["canonical"]["sequence"]
            self.check(f"{key}: canonical sequence", seq == exp["canonical_sequence"],
                       f"got {seq}")
            self.check(f"{key}: rejected indices",
                       data["canonical"]["rejected"] == exp.get("rejected", []),
                       str(data["canonical"]["rejected"]))
            if "witness_sequence" in exp:
                w = data["witness"]["sequence"]
                self.check(f"{key}: genuine second witness",
                           w == exp["witness_sequence"] and w != seq, f"got {w}")
                self.check(f"{key}: witness same kept count",
                           len(data["witness"]["assignments"]) == data["kept_count"], "")
                self.check(f"{key}: witness same residual sum",
                           data["witness"]["residual_sum"] == data["residual_sum"],
                           str(data["witness"]["residual_sum"]))
            else:
                self.check(f"{key}: no witness when unique", data["witness"] is None, "")
            # residual pairs internally consistent
            for p in data["canonical"]["residual_pairs"]:
                self.check(
                    f"{key}: pair {p['i']}-{p['j']} within threshold",
                    p["residual"] <= payload["threshold"], str(p),
                )

    def validation(self):
        print("[validation 422 + locatable reasons]")
        sc = SCENARIOS["unique"]
        bad = {
            "threshold": -3,
            "outlier_quota": 9,
            "catalog": [dict(s) for s in sc["catalog"]],
            "observations": sc["observations"] + [{"magnitude": "x"}],
            "dot_measurements": sc["dot_measurements"],
        }
        bad["catalog"][2] = dict(bad["catalog"][2])
        bad["catalog"][2]["vector"] = [1, 2]
        r = self.client.post("/api/solve", json=bad)
        self.check("bad payload -> 422", r.status_code == 422, f"{r.status_code} {r.text}")
        if r.status_code == 422:
            issues = r.json().get("issues", [])
            locs = {tuple(i["loc"]) for i in issues}
            for want in [("threshold",), ("outlier_quota",),
                         ("catalog", 2, "vector"), ("observations", 6, "magnitude")]:
                self.check(f"issue located at {want}", want in locs, str(sorted(map(str, locs))))

    def random_oracle(self, trials=20):
        print(f"[random instances vs exhaustive oracle x{trials}]")
        rng = random.Random(int(time.time()))
        for t in range(trials):
            case = _random_case(rng)
            r = self.client.post("/api/solve", json=case)
            self.check(f"rand{t}: 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
            if r.status_code != 200:
                continue
            data = r.json()
            oracle = _brute_oracle(
                case["catalog"], case["observations"],
                case["dot_measurements"], case["threshold"], case["outlier_quota"],
            )
            name = f"rand{t}"
            if oracle is None:
                self.check(f"{name}: incompatible agrees", data["status"] == "incompatible",
                           data.get("status"))
                continue
            k, cost, seq = oracle
            self.check(f"{name}: status optimal", data["status"] == "optimal", data.get("status"))
            self.check(f"{name}: kept {k}", data["kept_count"] == k,
                       f"{data['kept_count']} != {k}")
            self.check(f"{name}: residual {cost}", data["residual_sum"] == cost,
                       f"{data['residual_sum']} != {cost}")
            self.check(f"{name}: canonical lex-min",
                       data["canonical"]["sequence"] == seq,
                       f"{data['canonical']['sequence']} != {seq}")

    def run(self) -> int:
        self.health()
        self.scenarios()
        self.validation()
        self.random_oracle()
        print("\n========================================")
        print(f"PASSED {self.passed}  FAILED {len(self.failed)}")
        if self.failed:
            print("FAILED CHECKS:")
            for f in self.failed:
                print(" -", f)
            return 1
        print("ALL ACCEPTANCE CHECKS PASSED")
        return 0


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://api:8000"
    for attempt in range(30):
        try:
            return Checker(base).run()
        except httpx.HTTPError as e:
            print(f"waiting for API ({attempt}): {e}")
            time.sleep(2)
    print("API unreachable")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
