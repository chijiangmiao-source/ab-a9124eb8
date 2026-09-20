"""星场身份识别的精确整数搜索求解器。

问题：给定 N 颗目录星（等范数整数三维向量，每颗有亮度类别）和 M 个有序观测
（每个观测有亮度类别及与其他观测的整数点积测量），寻找一个从观测到目录星的
单射映射，允许至多 max_outliers 个观测被剔除（离群/伪星），满足：

  * 仅允许同亮度类别配对；
  * 每一对保留观测 (i, j) 的目录点积与实测点积之差的绝对值不超过阈值 T。

优化层级（依次）：
  1. 最大化保留观测数（即最小化剔除数）；
  2. 最小化全部保留对的残差和；
  3. 按观测顺序的目录标识序列取字典序最小（被剔除观测记为 -1，
     由于目录标识均非负，-1 排在任何标识之前）。

全部使用精确整数运算，自研分支限界搜索，不调用任何通用约束求解器。
"""

DROP = -1  # 序列中被剔除观测的占位标识

_INF = 1 << 62


class Solver:
    def __init__(self, catalog, obs_classes, meas, threshold, max_outliers):
        """
        catalog:     list[dict]，元素含 id(int>=0)、cls(str)、vec([x,y,z] int)
        obs_classes: list[str]，长度 M
        meas:        M x M 对称整数矩阵（对角线不使用）
        threshold:   非负整数阈值
        max_outliers: 0..3
        """
        self.catalog = catalog
        self.N = len(catalog)
        self.M = len(obs_classes)
        self.obs_classes = obs_classes
        self.meas = meas
        self.T = threshold
        self.k = max_outliers
        self.nodes = 0  # 搜索节点计数，用于审计展示

        # 目录星点积矩阵（精确整数）
        self.cdot = [[0] * self.N for _ in range(self.N)]
        for a in range(self.N):
            va = catalog[a]["vec"]
            for b in range(self.N):
                vb = catalog[b]["vec"]
                self.cdot[a][b] = va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]

        # 每个观测的候选目录星（同亮度类别），按目录标识升序，保证字典序枚举
        order = sorted(range(self.N), key=lambda s: (catalog[s]["id"], s))
        self.cand = []
        for i in range(self.M):
            self.cand.append([s for s in order if catalog[s]["cls"] == obs_classes[i]])

        # star -> 在 cand[i] 中的下标
        self.pos = [dict() for _ in range(self.M)]
        for i in range(self.M):
            for idx, s in enumerate(self.cand[i]):
                self.pos[i][s] = idx

        # 每对观测 (i<j) 的残差表：res_pair[(i,j)][ai][bj] = |cdot(a,b) - meas[i][j]|
        self.res_pair = {}
        for i in range(self.M):
            for j in range(i + 1, self.M):
                m = self.meas[i][j]
                table = []
                for a in self.cand[i]:
                    da = self.cdot[a]
                    table.append([abs(da[b] - m) for b in self.cand[j]])
                self.res_pair[(i, j)] = table

        # 每对观测的最小可能残差（用于分支限界下界）
        self.pair_min = [[0] * self.M for _ in range(self.M)]
        for i in range(self.M):
            for j in range(i + 1, self.M):
                table = self.res_pair[(i, j)]
                best = None
                for row in table:
                    for v in row:
                        if best is None or v < best:
                            best = v
                if best is None:
                    best = _INF  # 某一侧无候选，该对不可能同时保留
                self.pair_min[i][j] = self.pair_min[j][i] = best

    # ------------------------------------------------------------------ 工具

    def res(self, i, a, j, b):
        """观测 i 配星 a、观测 j 配星 b 时的点积残差。"""
        if i < j:
            return self.res_pair[(i, j)][self.pos[i][a]][self.pos[j][b]]
        return self.res_pair[(j, i)][self.pos[j][b]][self.pos[i][a]]

    def _viable(self, i, assign):
        """观测 i 与当前已固定观测全部相容的候选星列表（含单射约束）。"""
        out = []
        for a in self.cand[i]:
            if a in assign:  # 单射：一颗目录星至多配对一个观测
                continue
            ok = True
            for j in range(self.M):
                aj = assign[j]
                if aj is None or aj == DROP or j == i:
                    continue
                if self.res(i, a, j, aj) > self.T:
                    ok = False
                    break
            if ok:
                out.append(a)
        return out

    def _added_cost(self, i, a, assign):
        """把观测 i 配给星 a 时，与已固定观测之间新增的残差和。"""
        s = 0
        for j in range(self.M):
            aj = assign[j]
            if aj is None or aj == DROP or j == i:
                continue
            s += self.res(i, a, j, aj)
        return s

    def _lower_bound(self, assign, budget, cost, unassigned):
        """当前部分解的可采纳下界（剩余至多 budget 个剔除名额）。

        下界 = 已累积残差
             + 每个未定点到已定点集合的最小新增残差
             + 未定点两两之间的最小残差
             - 至多 budget 次剔除最多能抹去的量（取上界估计，保证可采纳）。
        """
        extras = []
        pair_sum = 0
        for i in unassigned:
            vi = self._viable(i, assign)
            if vi:
                extras.append(min(self._added_cost(i, a, assign) for a in vi))
            else:
                extras.append(0)  # 无可行候选，只能被剔除
        uset = set(unassigned)
        deg = {i: 0 for i in unassigned}
        for x in range(self.M):
            if x not in uset:
                continue
            for y in range(x + 1, self.M):
                if y not in uset:
                    continue
                pm = self.pair_min[x][y]
                pair_sum += pm
                deg[x] += pm
                deg[y] += pm
        total = cost + sum(extras) + pair_sum
        if budget > 0 and unassigned:
            # 剔除观测 i 至多能抹去 extras[i] + 其关联的未定点对残差和
            removable = sorted(
                (extras[t] + deg[i] for t, i in enumerate(unassigned)),
                reverse=True,
            )
            total -= sum(removable[:budget])
        return total

    # ------------------------------------------------------- 可行性（第一阶段）

    def _search_any(self, assign, budget, cost, cost_limit):
        """是否存在总残差 <= cost_limit、至多再剔除 budget 个观测的补全。"""
        self.nodes += 1
        if cost > cost_limit:
            return False
        unassigned = [i for i in range(self.M) if assign[i] is None]
        if not unassigned:
            return True
        if self._lower_bound(assign, budget, cost, unassigned) > cost_limit:
            return False

        # 选候选最少的未定点（失败优先）
        best_i, best_v = -1, None
        for i in unassigned:
            v = self._viable(i, assign)
            if best_v is None or len(v) < len(best_v):
                best_i, best_v = i, v
                if not v:
                    break
        i, v = best_i, best_v
        if not v:
            if budget <= 0:
                return False
            assign[i] = DROP
            r = self._search_any(assign, budget - 1, cost, cost_limit)
            assign[i] = None
            return r

        for a in v:
            add = self._added_cost(i, a, assign)
            if cost + add > cost_limit:
                continue
            assign[i] = a
            if self._search_any(assign, budget, cost + add, cost_limit):
                assign[i] = None
                return True
            assign[i] = None
        if budget > 0:
            assign[i] = DROP
            if self._search_any(assign, budget - 1, cost, cost_limit):
                assign[i] = None
                return True
            assign[i] = None
        return False

    # --------------------------------------------------- 最小残差（第二阶段）

    def _search_best(self, assign, budget, cost):
        """分支限界求最小总残差，结果存入 self.best_cost。"""
        self.nodes += 1
        if cost >= self.best_cost:
            return
        unassigned = [i for i in range(self.M) if assign[i] is None]
        if not unassigned:
            self.best_cost = cost
            return
        if self._lower_bound(assign, budget, cost, unassigned) >= self.best_cost:
            return

        best_i, best_v = -1, None
        for i in unassigned:
            v = self._viable(i, assign)
            if best_v is None or len(v) < len(best_v):
                best_i, best_v = i, v
                if not v:
                    break
        i, v = best_i, best_v
        if not v:
            if budget <= 0:
                return
            assign[i] = DROP
            self._search_best(assign, budget - 1, cost)
            assign[i] = None
            return

        # 按新增残差升序分支，尽早获得优质 incumbent
        scored = sorted(
            ((self._added_cost(i, a, assign), a) for a in v),
            key=lambda t: (t[0], self.catalog[t[1]]["id"]),
        )
        for add, a in scored:
            if cost + add >= self.best_cost:
                break
            assign[i] = a
            self._search_best(assign, budget, cost + add)
            assign[i] = None
        if budget > 0:
            assign[i] = DROP
            self._search_best(assign, budget - 1, cost)
            assign[i] = None

    def _greedy_incumbent(self, budget):
        """按观测顺序贪心构造一个可行解，为分支限界提供初始上界。"""
        assign = [None] * self.M
        cost = 0
        left = budget
        for i in range(self.M):
            best_a, best_add = None, None
            for a in self._viable(i, assign):
                add = self._added_cost(i, a, assign)
                if best_add is None or add < best_add:
                    best_a, best_add = a, add
            # 无相容候选或代价明显过大时，优先消耗剔除名额
            if left > 0 and (best_a is None or best_add > self.T * max(1, self.M)):
                assign[i] = DROP
                left -= 1
                continue
            if best_a is None:
                return _INF  # 第一阶段已保证不会发生
            assign[i] = best_a
            cost += best_add
        return cost

    # ------------------------------------------------------- 见证（第四阶段）

    def _search_witness(self, assign, t, budget, cost, limit, canonical, differed):
        """按观测顺序搜索一份与 canonical 不同且总残差 <= limit 的完整映射。"""
        self.nodes += 1
        if cost > limit:
            return None
        if t == self.M:
            return assign.copy() if differed else None
        unassigned = list(range(t, self.M))
        if self._lower_bound(assign, budget, cost, unassigned) > limit:
            return None

        options = []
        if budget > 0:
            options.append(DROP)
        for a in self._viable(t, assign):
            options.append(a)
        for v in options:
            if v == DROP:
                assign[t] = DROP
                r = self._search_witness(
                    assign, t + 1, budget - 1, cost, limit, canonical,
                    differed or canonical[t] != DROP,
                )
                if r is not None:
                    return r
                assign[t] = None
            else:
                add = self._added_cost(t, v, assign)
                if cost + add > limit:
                    continue
                assign[t] = v
                r = self._search_witness(
                    assign, t + 1, budget, cost + add, limit, canonical,
                    differed or canonical[t] != v,
                )
                if r is not None:
                    return r
                assign[t] = None
        return None

    # ------------------------------------------------------------------ 主流程

    def solve(self):
        """返回 dict：status / assignment / cost / multiple / witness / nodes。"""
        # 第一阶段：最少剔除数
        k_star = None
        for k in range(self.k + 1):
            if self._search_any([None] * self.M, k, 0, _INF):
                k_star = k
                break
        if k_star is None:
            return {"status": "infeasible", "nodes": self.nodes}

        # 第二阶段：在 k_star 个剔除名额下最小化残差和
        self.best_cost = _INF
        greedy = self._greedy_incumbent(k_star)
        if greedy < self.best_cost:
            self.best_cost = greedy
        self._search_best([None] * self.M, k_star, 0)
        c_star = self.best_cost

        # 第三阶段：逐位固定字典序最小的目录标识序列（剔除记 DROP=-1）
        assign = [None] * self.M
        budget = k_star
        cost = 0
        for t in range(self.M):
            options = ([DROP] if budget > 0 else []) + list(self.cand[t])
            chosen = None
            for v in options:
                if v == DROP:
                    assign[t] = DROP
                    if self._search_any(assign, budget - 1, cost, c_star):
                        budget -= 1
                        chosen = v
                        break
                    assign[t] = None
                else:
                    if v in assign:  # 单射：前缀已占用该目录星
                        continue
                    ok = True
                    for j in range(t):
                        aj = assign[j]
                        if aj is None or aj == DROP:
                            continue
                        if self.res(t, v, j, aj) > self.T:
                            ok = False
                            break
                    if not ok:
                        continue
                    add = self._added_cost(t, v, assign)
                    if cost + add > c_star:
                        continue
                    assign[t] = v
                    if self._search_any(assign, budget, cost + add, c_star):
                        cost += add
                        chosen = v
                        break
                    assign[t] = None
            if chosen is None:  # 理论上不可达：c_star 对应解必然存在
                raise RuntimeError("字典序构造失败，搜索状态不一致")

        # 第四阶段：寻找另一份前两级同优的见证映射
        witness = self._search_witness(
            [None] * self.M, 0, k_star, 0, c_star, assign, False
        )

        return {
            "status": "ok",
            "assignment": assign,
            "cost": c_star,
            "drops": k_star,
            "multiple": witness is not None,
            "witness": witness,
            "nodes": self.nodes,
        }


def build_response(result, catalog, obs_classes, meas):
    """把求解结果整理为 API 响应（含映射明细与保留对残差表）。"""
    if result["status"] != "ok":
        return {
            "status": "infeasible",
            "message": "不相容：在给定离群名额与阈值内不存在满足全部保留对约束的映射",
            "nodes": result["nodes"],
        }

    def mapping_of(assign):
        out = []
        for i, a in enumerate(assign):
            if a is None or a == DROP:
                out.append(None)
            else:
                star = catalog[a]
                out.append({
                    "obs": i,
                    "star_id": star["id"],
                    "cls": star["cls"],
                    "vec": star["vec"],
                })
        return out

    def sequence_of(assign):
        return [
            (DROP if (a is None or a == DROP) else catalog[a]["id"])
            for a in assign
        ]

    def pair_rows(assign):
        rows = []
        total = 0
        for i in range(len(assign)):
            ai = assign[i]
            if ai is None or ai == DROP:
                continue
            for j in range(i + 1, len(assign)):
                aj = assign[j]
                if aj is None or aj == DROP:
                    continue
                va, vb = catalog[ai]["vec"], catalog[aj]["vec"]
                cdot = va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]
                r = abs(cdot - meas[i][j])
                total += r
                rows.append({
                    "i": i, "j": j,
                    "measured": meas[i][j],
                    "catalog": cdot,
                    "residual": r,
                })
        return rows, total

    canonical = result["assignment"]
    used = [a for a in canonical if a is not None and a != DROP]
    assert len(set(used)) == len(used), "映射必须满足单射"
    pairs, total = pair_rows(canonical)
    assert total == result["cost"], "残差和校验失败"

    response = {
        "status": "ok",
        "retained_count": sum(1 for a in canonical if a is not None and a != DROP),
        "residual_sum": result["cost"],
        "drops": [i for i, a in enumerate(canonical) if a is None or a == DROP],
        "sequence": sequence_of(canonical),
        "canonical": mapping_of(canonical),
        "pair_residuals": pairs,
        "multiple": result["multiple"],
        "nodes": result["nodes"],
    }
    if result["multiple"]:
        witness = result["witness"]
        wpairs, wtotal = pair_rows(witness)
        assert wtotal == result["cost"], "见证残差和应与最优一致"
        response["witness"] = mapping_of(witness)
        response["witness_sequence"] = sequence_of(witness)
        response["witness_pair_residuals"] = wpairs
    else:
        response["witness"] = None
        response["witness_sequence"] = None
        response["witness_pair_residuals"] = None
    return response
