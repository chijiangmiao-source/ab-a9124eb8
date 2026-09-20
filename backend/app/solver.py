"""Exact integer search for star-tracker field identification.

The problem solved here is an injective *injection mapping* from an ordered
list of observed stars (which may contain a bounded number of pseudostars)
onto a catalog of equal-norm integer 3-vectors:

* an observation may only be paired with a catalog star of the same
  brightness category,
* every catalog star is used at most once,
* for every pair of kept observations (i, j) paired with catalog stars
  (a, b) the integer angular residual |<v_a, v_b> - m_ij| must not exceed a
  given threshold, where m_ij is the measured integer dot product,
* at most ``outlier_quota`` observations may be rejected as pseudostars.

The objective has strict-lexicographic priority:

  1. maximize the number of kept observations,
  2. minimize the residual sum over all kept/kept pairs,
  3. minimize the catalog-identifier sequence in observation order, where a
     rejection (-1) sorts before every catalog identifier.

No general-purpose constraint / SAT / MIP solver is used.  The whole
computation is a hand-written branch-and-bound over partial injections with:

  * forced rejection of observations whose candidate set became empty,
  * MRV (minimum remaining values) variable selection,
  * memoized boolean feasibility of partial states,
  * a relaxed integer lower bound for the residual-sum stage,
  * ordered lexicographic enumeration for the canonical solution and a
    second, genuinely distinct witness mapping.

Every arithmetic value involved in the search is an ``int``; floats are not
used anywhere in the optimization.
"""

from __future__ import annotations

from typing import Optional

UNDECIDED = -2
REJECT = -1
INF = 10**30


class SolveValidationError(ValueError):
    """Business-level validation failure with locatable reasons."""

    def __init__(self, issues: list[dict]):
        super().__init__("; ".join(i["message"] for i in issues))
        self.issues = issues


def _issue(loc: list, message: str) -> dict:
    return {"loc": loc, "message": message}


def solve(payload: dict) -> dict:
    """Validate a request payload and run the exact search.

    Returns a JSON-serializable result document.  Raises
    SolveValidationError with a list of ``{loc, message}`` issues on bad
    input so the frontend can keep the draft and point at the cause.
    """

    issues: list[dict] = []

    if not isinstance(payload, dict):
        raise SolveValidationError(
            [_issue([], "请求体必须是包含 threshold/catalog/observations 等字段的对象")]
        )

    threshold = payload.get("threshold")
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 0:
        issues.append(_issue(["threshold"], "残差阈值必须是非负整数"))

    quota = payload.get("outlier_quota")
    if (
        not isinstance(quota, int)
        or isinstance(quota, bool)
        or not (0 <= quota <= 3)
    ):
        issues.append(_issue(["outlier_quota"], "离群名额必须是 0 到 3 的整数"))

    catalog = payload.get("catalog")
    observations = payload.get("observations")
    dots = payload.get("dot_measurements")

    cat_ids: list[str] = []
    cat_vec: list[tuple[int, int, int]] = []
    cat_mag: list[int] = []
    obs_mag: list[int] = []
    matrix: list[list[int]] = []

    # ---- catalog -----------------------------------------------------------
    if not isinstance(catalog, list):
        issues.append(_issue(["catalog"], "星表必须是数组"))
        catalog = []
    if not (8 <= len(catalog) <= 180):
        issues.append(_issue(["catalog"], f"目录星数量须在 8 到 180 之间，当前 {len(catalog)}"))

    seen_ids: set[str] = set()
    norms: set[int] = set()
    class_counts: dict[int, int] = {}
    for ci, star in enumerate(catalog):
        if not isinstance(star, dict):
            issues.append(_issue(["catalog", ci], "星表条目必须是对象"))
            continue
        sid = star.get("id")
        if not isinstance(sid, str) or not sid.strip():
            issues.append(_issue(["catalog", ci, "id"], "目录星标识必须是非空字符串"))
        elif sid in seen_ids:
            issues.append(_issue(["catalog", ci, "id"], f"目录星标识 {sid!r} 重复"))
        else:
            seen_ids.add(sid)
        mag = star.get("magnitude")
        if not isinstance(mag, int) or isinstance(mag, bool):
            issues.append(_issue(["catalog", ci, "magnitude"], "亮度类别必须是整数"))
        else:
            class_counts[mag] = class_counts.get(mag, 0) + 1
        vec = star.get("vector")
        norm2 = None
        if not isinstance(vec, list) or len(vec) != 3 or any(
            (not isinstance(x, int)) or isinstance(x, bool) for x in vec
        ):
            issues.append(
                _issue(["catalog", ci, "vector"], "三维向量必须是 3 个整数，例如 [2,2,1]")
            )
        else:
            norm2 = vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2
            if norm2 <= 0:
                issues.append(_issue(["catalog", ci, "vector"], "零向量不能作为目录星方向"))
            norms.add(norm2)
        if isinstance(sid, str) and sid.strip() and mag is not None and norm2:
            cat_ids.append(sid)
            cat_mag.append(mag)
            cat_vec.append((vec[0], vec[1], vec[2]))

    if len(norms) > 1:
        issues.append(
            _issue(["catalog"], f"目录星必须等范数，但发现多种平方范数 {sorted(norms)}")
        )
    for mag, count in sorted(class_counts.items()):
        if count > 20:
            issues.append(
                _issue(["catalog"], f"亮度类别 {mag} 有 {count} 颗候选星，超过每类 20 颗上限")
            )

    # ---- observations ------------------------------------------------------
    if not isinstance(observations, list):
        issues.append(_issue(["observations"], "观测必须是数组"))
        observations = []
    if not (6 <= len(observations) <= 18):
        issues.append(
            _issue(["observations"], f"观测数量须在 6 到 18 之间，当前 {len(observations)}")
        )
    for oi, obs in enumerate(observations):
        if not isinstance(obs, dict):
            issues.append(_issue(["observations", oi], "观测条目必须是对象"))
            continue
        mag = obs.get("magnitude")
        if not isinstance(mag, int) or isinstance(mag, bool):
            issues.append(_issue(["observations", oi, "magnitude"], "亮度类别必须是整数"))
        else:
            obs_mag.append(mag)

    n = len(observations)

    # ---- dot product matrix ------------------------------------------------
    if not isinstance(dots, list):
        issues.append(_issue(["dot_measurements"], "点积测量必须是二维整数数组"))
        dots = []
    if len(dots) != n:
        issues.append(
            _issue(
                ["dot_measurements"],
                f"点积矩阵须为 {n}×{n}（与观测数一致），当前 {len(dots)} 行",
            )
        )
    for i, row in enumerate(dots):
        if not isinstance(row, list) or len(row) != n:
            issues.append(_issue(["dot_measurements", i], f"第 {i} 行长度须为 {n}"))
            continue
        for j, val in enumerate(row):
            if not isinstance(val, int) or isinstance(val, bool):
                issues.append(_issue(["dot_measurements", i, j], "点积必须是整数"))
    if isinstance(dots, list) and len(dots) == n and all(
        isinstance(r, list) and len(r) == n for r in dots
    ) and all(isinstance(v, int) and not isinstance(v, bool) for r in dots for v in r):
        matrix = [row[:] for row in dots]
        for i in range(n):
            for j in range(i + 1, n):
                if matrix[i][j] != matrix[j][i]:
                    issues.append(
                        _issue(
                            ["dot_measurements", j, i],
                            f"点积矩阵不对称：m[{i}][{j}]={matrix[i][j]} "
                            f"但 m[{j}][{i}]={matrix[j][i]}",
                        )
                    )
        matrix = [[matrix[i][j] for j in range(n)] for i in range(n)]

    # observations whose class does not exist in the catalog are not illegal
    # (they can simply be outliers), but the quota must plausibly cover them.
    if obs_mag and cat_mag and isinstance(quota, int) and not isinstance(quota, bool):
        uncatalogued = [i for i, m in enumerate(obs_mag) if m not in class_counts]
        if len(uncatalogued) > quota:
            issues.append(
                _issue(
                    ["outlier_quota"],
                    f"有 {len(uncatalogued)} 个观测的亮度类别在星表中无候选星，"
                    f"超过 {quota} 个离群名额（观测下标 {uncatalogued}）",
                )
            )

    if issues:
        raise SolveValidationError(issues)

    engine = Engine(
        cat_ids=cat_ids,
        cat_vec=cat_vec,
        cat_mag=cat_mag,
        obs_mag=obs_mag,
        measured=matrix,
        threshold=threshold,
        quota=quota,
    )
    return engine.run()


class Engine:
    """Branch-and-bound over partial injection states.

    A state is a tuple of length n with entries:

      * UNDECIDED (-2): observation not decided yet,
      * REJECT    (-1): observation is a rejected pseudostar,
      * k >= 0    : observation is paired with candidate position ``k``
                    (candidate positions index the full catalog list).
    """

    def __init__(
        self,
        cat_ids: list[str],
        cat_vec: list[tuple[int, int, int]],
        cat_mag: list[int],
        obs_mag: list[int],
        measured: list[list[int]],
        threshold: int,
        quota: int,
    ):
        self.ids = cat_ids
        self.vec = cat_vec
        self.cat_mag = cat_mag
        self.obs_mag = obs_mag
        self.M = measured
        self.T = threshold
        self.quota = quota
        self.n = len(obs_mag)

        # catalog dot products (exact integers)
        self.cdp: dict[tuple[int, int], int] = {}
        for a in range(len(cat_vec)):
            for b in range(a + 1, len(cat_vec)):
                va, vb = cat_vec[a], cat_vec[b]
                self.cdp[(a, b)] = va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]

        # candidates per observation, sorted by catalog id for lex order
        self.cand: list[list[int]] = []
        for m in obs_mag:
            group = [a for a, cm in enumerate(cat_mag) if cm == m]
            group.sort(key=lambda a: cat_ids[a])
            self.cand.append(group)

        # pairwise feasibility and residual cost, keyed i<j
        self.ok: dict[tuple[int, int], dict[int, set[int]]] = {}
        self.cost: dict[tuple[int, int], dict[tuple[int, int], int]] = {}
        for i in range(self.n):
            for j in range(i + 1, self.n):
                table: dict[int, set[int]] = {}
                costs: dict[tuple[int, int], int] = {}
                for a in self.cand[i]:
                    allowed: set[int] = set()
                    for b in self.cand[j]:
                        if a == b:
                            continue
                        actual = self.cdp[(min(a, b), max(a, b))]
                        r = abs(actual - measured[i][j])
                        if r <= threshold:
                            allowed.add(b)
                            costs[(a, b)] = r
                    if allowed:
                        table[a] = allowed
                self.ok[(i, j)] = table
                self.cost[(i, j)] = costs

        self.feas_memo: dict[tuple, int] = {}
        self.nodes = 0

    # ------------------------------------------------------------------ utils
    def edge_ok(self, i: int, a: int, j: int, b: int) -> bool:
        if i > j:
            i, j = j, i
            a, b = b, a
        return b in self.ok[(i, j)].get(a, ())

    def edge_cost(self, i: int, a: int, j: int, b: int) -> int:
        if i > j:
            i, j = j, i
            a, b = b, a
        return self.cost[(i, j)][(a, b)]

    @staticmethod
    def _kept_of(state) -> list[int]:
        return [i for i, v in enumerate(state) if v >= 0]

    def _used(self, state) -> set[int]:
        return {v for v in state if v >= 0}

    def _domain(self, state, i: int, used: set[int]) -> list[int]:
        out = []
        kept = [(j, state[j]) for j in range(self.n) if state[j] >= 0]
        for a in self.cand[i]:
            if a in used:
                continue
            if all(self.edge_ok(i, a, j, aj) for j, aj in kept):
                out.append(a)
        return out

    def _increment(self, state, i: int, a: int) -> int:
        """Residual contributed by pairing i->a against all current keeps."""
        total = 0
        for j in range(self.n):
            if state[j] >= 0:
                total += self.edge_cost(i, a, j, state[j])
        return total

    # ------------------------------------------------- stage 1: max kept count
    def best_feasible(self, state: list[int], rej_left: int) -> int:
        """Maximum number of kept obs reachable from this partial state.

        Rejections are allowed while ``rej_left`` remains.  Memoized on the
        canonicalized partial state.
        """
        state, rej_left = self._canonicalize(state, rej_left)
        if state is None:
            return -1
        key = (tuple(state), rej_left)
        cached = self.feas_memo.get(key)
        if cached is not None:
            return cached
        self.nodes += 1

        undecided = [i for i, v in enumerate(state) if v == UNDECIDED]
        used = self._used(state)
        n_kept = self.n - len(undecided) - sum(1 for v in state if v == REJECT)
        if not undecided:
            self.feas_memo[key] = n_kept
            return n_kept

        domains = {i: self._domain(state, i, used) for i in undecided}
        # Relaxation: bipartite matching of undecided obs to unused catalog
        # stars (domains already respect the fixed keeps; undecided/
        # undecided residual edges are ignored).  Hall matching bounds how
        # many more observations can be kept; the rest must be rejected.
        match_cap = self._matching_cardinality_domains(undecided, domains)
        must_keep = len(undecided) - rej_left
        if match_cap < must_keep:
            self.feas_memo[key] = -1
            return -1
        upper = n_kept + min(match_cap, len(undecided))

        # MRV: most constrained observation first
        pivot = min(undecided, key=lambda i: (len(domains[i]), i))

        best = -1
        for a in domains[pivot]:
            state[pivot] = a
            r = self.best_feasible(state, rej_left)
            state[pivot] = UNDECIDED
            if r > best:
                best = r
            if best == upper:
                break
        if rej_left > 0 and best < upper:
            state[pivot] = REJECT
            r = self.best_feasible(state, rej_left - 1)
            state[pivot] = UNDECIDED
            if r > best:
                best = r

        self.feas_memo[key] = best
        return best

    @staticmethod
    def _matching_cardinality_domains(undecided, domains) -> int:
        """Kuhn maximum matching on precomputed domains (relaxed problem)."""
        match_to: dict[int, int] = {}

        def augment(i: int, seen: set[int]) -> bool:
            for a in domains[i]:
                if a in seen:
                    continue
                seen.add(a)
                if a not in match_to or augment(match_to[a], seen):
                    match_to[a] = i
                    return True
            return False

        count = 0
        for i in sorted(undecided, key=lambda k: (len(domains[k]), k)):
            if augment(i, set()):
                count += 1
        return count

    def _canonicalize(self, state: list[int], rej_left: int):
        """Force-reject undecided observations whose domain is empty.

        Such an observation can never be kept regardless of later choices,
        so dropping it deterministically loses nothing and consumes one
        outlier slot.  Returns (None, x) when the quota cannot cover them.
        """
        changed = True
        state = state[:]
        while changed:
            changed = False
            used = self._used(state)
            for i, v in enumerate(state):
                if v != UNDECIDED:
                    continue
                if not self._domain(state, i, used):
                    if rej_left <= 0:
                        return None, 0
                    state[i] = REJECT
                    rej_left -= 1
                    changed = True
        return state, rej_left

    def witness_for_max(self, rej_left: int) -> Optional[list[int]]:
        """One concrete state attaining the best_feasible(root) count."""
        state = [UNDECIDED] * self.n
        target = self.best_feasible(state, rej_left)
        if target < 0:
            return None
        state, rej_left = self._canonicalize(state, rej_left)
        return self._finish_max(state, rej_left, target)

    def _finish_max(self, state, rej_left, target):
        undecided = [i for i, v in enumerate(state) if v == UNDECIDED]
        used = self._used(state)
        if not undecided:
            return state[:] if sum(1 for v in state if v >= 0) == target else None
        domains = {i: self._domain(state, i, used) for i in undecided}
        pivot = min(undecided, key=lambda i: (len(domains[i]), i))
        for a in domains[pivot]:
            state[pivot] = a
            if self.best_feasible(state, rej_left) == target:
                sol = self._finish_max(state, rej_left, target)
                if sol is not None:
                    state[pivot] = UNDECIDED
                    return sol
            state[pivot] = UNDECIDED
        if rej_left > 0:
            state[pivot] = REJECT
            if self.best_feasible(state, rej_left - 1) == target:
                sol = self._finish_max(state, rej_left - 1, target)
                if sol is not None:
                    state[pivot] = UNDECIDED
                    return sol
            state[pivot] = UNDECIDED
        return None

    # --------------------------------------------- stage 2: min residual sum
    def min_residual(self, k_star: int, seed: list[int]) -> tuple[int, list[int]]:
        """Minimum residual sum among injections keeping exactly k_star obs."""
        rej_left = self.n - k_star
        best_cost = self._cost_of(seed)
        best_state = [seed[:]]

        def dfs(state, rej_left, cur):
            nonlocal best_cost
            state, rej_left = self._canonicalize(state, rej_left)
            if state is None:
                return
            undecided = [i for i, v in enumerate(state) if v == UNDECIDED]
            need = len(undecided) - rej_left
            if need < 0:
                return
            kept_so_far = sum(1 for v in state if v >= 0)
            if self.best_feasible(state, rej_left) < kept_so_far + need:
                return
            if cur + self._lower_bound(state, undecided, need) >= best_cost:
                return
            if need == 0:
                # every remaining undecided observation is rejected
                if cur < best_cost:
                    best_cost = cur
                    best_state[0] = [
                        REJECT if v == UNDECIDED else v for v in state
                    ]
                return

            used = self._used(state)
            domains = {i: self._domain(state, i, used) for i in undecided}
            # canonicalize emptied every domain; branch on the tightest obs
            pivot = min(undecided, key=lambda i: (len(domains[i]), i))
            branches = sorted(
                domains[pivot], key=lambda a: (self._increment(state, pivot, a), a)
            )
            for a in branches:
                inc = self._increment(state, pivot, a)
                if cur + inc >= best_cost:
                    continue
                state[pivot] = a
                dfs(state, rej_left, cur + inc)
                state[pivot] = UNDECIDED
            if rej_left > 0:
                state[pivot] = REJECT
                dfs(state, rej_left - 1, cur)
                state[pivot] = UNDECIDED

        dfs([UNDECIDED] * self.n, rej_left, 0)
        return best_cost, best_state[0]

    def _lower_bound(self, state, undecided, need) -> int:
        """Relaxed integer LB for edges from current keeps to future keeps.

        For every undecided observation take the cheapest still-compatible
        catalog star (minimum residual summed against the current keeps),
        then keep the ``need`` smallest of those minima.  Edges between two
        future keeps are non-negative and dropped, so this can only
        under-estimate; the distinct-catalog constraint is also dropped.
        """
        if need == 0:
            return 0
        used = self._used(state)
        minima = []
        for i in undecided:
            best = INF
            for a in self._domain(state, i, used):
                inc = self._increment(state, i, a)
                if inc < best:
                    best = inc
            minima.append(best)
        minima.sort()
        return sum(minima[:need])

    def _cost_of(self, mapping) -> int:
        total = 0
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if mapping[i] >= 0 and mapping[j] >= 0:
                    total += self.edge_cost(i, mapping[i], j, mapping[j])
        return total

    # ----------------------------- stage 3: lex enumeration at optimal levels
    def enumerate_at(self, k_star: int, r_star: int, limit: int = 2):
        """Yield mappings at the optimum in strict lexicographic order.

        Rejection (-1) is enumerated before every catalog identifier; within
        assignments identifiers are ascending.  The first yielded mapping is
        the canonical solution, the second a genuine alternative witness.
        """
        results: list[tuple] = []
        rej_left = self.n - k_star
        state = [UNDECIDED] * self.n

        def dfs(idx, rej_left, cur):
            if len(results) >= limit:
                return
            if idx == self.n:
                if rej_left == 0 and cur == r_star:
                    results.append(tuple(state))
                return
            if state[idx] != UNDECIDED:  # pragma: no cover - defensive
                dfs(idx + 1, rej_left, cur)
                return
            undecided = [i for i in range(idx, self.n) if state[i] == UNDECIDED]
            need = len(undecided) - rej_left
            if need < 0:
                return
            if self.best_feasible(state, rej_left) < sum(
                1 for v in state if v >= 0
            ) + need:
                return
            if cur + self._seq_lower_bound(state, undecided, need) > r_star:
                return

            # rejection is lexicographically preferred
            if rej_left > 0:
                state[idx] = REJECT
                dfs(idx + 1, rej_left - 1, cur)
                state[idx] = UNDECIDED
            used = self._used(state)
            for a in self._domain(state, idx, used):
                inc = self._increment(state, idx, a)
                if cur + inc > r_star:
                    continue
                state[idx] = a
                dfs(idx + 1, rej_left, cur + inc)
                state[idx] = UNDECIDED

        dfs(0, rej_left, 0)
        return results

    def _seq_lower_bound(self, state, undecided, need) -> int:
        """Lower bound on residual still addable (same relaxation as stage 2)."""
        if need == 0:
            return 0
        minima = []
        used = self._used(state)
        for i in undecided:
            best = INF
            for a in self._domain(state, i, used):
                inc = self._increment(state, i, a)
                if inc < best:
                    best = inc
            minima.append(best)
        minima.sort()
        return sum(minima[:need])

    # -------------------------------------------------------------------- run
    def run(self) -> dict:
        root = [UNDECIDED] * self.n
        k_star = self.best_feasible(root, self.quota)
        required = self.n - self.quota

        if k_star < required:
            return {
                "status": "incompatible",
                "message": (
                    f"不相容：在至多 {self.quota} 个离群名额下，"
                    f"最多只能保留 {max(k_star, 0)} 颗观测，"
                    f"而可行方案至少需保留 {required} 颗"
                ),
                "kept_count": max(k_star, 0),
                "required_kept": required,
                "outlier_quota": self.quota,
                "threshold": self.T,
                "n_observations": self.n,
                "n_catalog": len(self.ids),
                "search_nodes": self.nodes,
                "canonical": None,
                "witness": None,
                "multiple": False,
            }

        seed = self.witness_for_max(self.quota)
        r_star, opt_state = self.min_residual(k_star, seed)
        mappings = self.enumerate_at(k_star, r_star, limit=2)
        canonical = mappings[0]
        witness = mappings[1] if len(mappings) > 1 else None

        return {
            "status": "optimal",
            "message": None,
            "kept_count": k_star,
            "rejected_count": self.n - k_star,
            "required_kept": required,
            "residual_sum": r_star,
            "outlier_quota": self.quota,
            "threshold": self.T,
            "n_observations": self.n,
            "n_catalog": len(self.ids),
            "search_nodes": self.nodes,
            "multiple": witness is not None,
            "canonical": self._pack(canonical, r_star),
            "witness": self._pack(witness, r_star) if witness is not None else None,
        }

    def _pack(self, mapping, r_star) -> dict:
        assignments = []
        rejected = []
        for i, a in enumerate(mapping):
            if a >= 0:
                assignments.append(
                    {"observation_index": i, "catalog_index": a, "catalog_id": self.ids[a]}
                )
            else:
                rejected.append(i)
        pairs = []
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if mapping[i] >= 0 and mapping[j] >= 0:
                    a, b = mapping[i], mapping[j]
                    actual = self.cdp[(min(a, b), max(a, b))]
                    pairs.append(
                        {
                            "i": i,
                            "j": j,
                            "catalog_i": self.ids[a],
                            "catalog_j": self.ids[b],
                            "measured": self.M[i][j],
                            "actual": actual,
                            "residual": abs(actual - self.M[i][j]),
                        }
                    )
        return {
            "assignments": assignments,
            "rejected": rejected,
            "sequence": [self.ids[a] if a >= 0 else None for a in mapping],
            "residual_pairs": pairs,
            "residual_sum": sum(p["residual"] for p in pairs),
            "at_optimal_residual": sum(p["residual"] for p in pairs) == r_star,
        }


# Module-level helpers used by the static lower bound (kept out of the hot
# attribute namespace on purpose).
def state_cand_iter(state, i, used):
    for a in (eng for eng in ()):  # pragma: no cover - replaced at runtime
        yield a


def edge_or_none(i, a, j, b):  # pragma: no cover - replaced at runtime
    return None
