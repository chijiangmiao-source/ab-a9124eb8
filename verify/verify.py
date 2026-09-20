"""验收服务：对运行中的 Web 与 API 执行端到端验收，全部通过则以 0 退出。

覆盖：
  1. API 健康检查；
  2. Web 页面可达（可用 WEB_CHECK=0 跳过）；
  3. 经 Web 反向代理的真实联调识别（唯一解实例）；
  4. 不相容实例；
  5. 多解实例：规范映射 + 另一份真实见证（独立复算残差验证）；
  6. 离群剔除实例；
  7. 校验失败实例：422 且错误带定位路径。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = os.environ.get("API_URL", "http://api:8000").rstrip("/")
WEB_URL = os.environ.get("WEB_URL", "http://web:80").rstrip("/")
WEB_CHECK = os.environ.get("WEB_CHECK", "1") != "0"
TIMEOUT = 10

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def http(method, url, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def wait_health():
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            code, body = http("GET", f"{API_URL}/api/health")
            if code == 200 and body.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


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

CAT_DUP = [
    {"id": 0, "cls": "B", "vec": [1, 3, 2]},
    {"id": 1, "cls": "C", "vec": [2, 1, 3]},
    {"id": 2, "cls": "D", "vec": [2, 3, 1]},
    {"id": 3, "cls": "E", "vec": [3, 1, 2]},
    {"id": 4, "cls": "F", "vec": [3, 2, 1]},
    {"id": 10, "cls": "A", "vec": [1, 2, 3]},
    {"id": 11, "cls": "A", "vec": [1, 2, 3]},
    {"id": 12, "cls": "G", "vec": [-1, -2, -3]},
]

CLASSES6 = ["A", "B", "C", "D", "E", "F"]


def make_obs(classes, vecs, corrupt=None):
    obs = []
    for i, cls in enumerate(classes):
        dots = {}
        for j in range(len(classes)):
            if j == i:
                continue
            if corrupt and (i in corrupt or j in corrupt):
                dots[str(j)] = 100
            else:
                dots[str(j)] = dot(vecs[i], vecs[j])
        obs.append({"cls": cls, "dots": dots})
    return obs


def payload(catalog, obs, threshold=0, outliers=0):
    return {"threshold": threshold, "max_outliers": outliers,
            "catalog": catalog, "observations": obs}


def verify_mapping(mapping, catalog, obs, threshold):
    """独立复算：映射满足同类配对、单射、残差阈值，返回残差和。"""
    by_id = {s["id"]: s for s in catalog}
    used = set()
    kept = []
    for i, entry in enumerate(mapping):
        if entry is None:
            continue
        star = by_id[entry["star_id"]]
        if star["cls"] != obs[i]["cls"]:
            return None
        if entry["star_id"] in used:
            return None
        used.add(entry["star_id"])
        kept.append((i, star))
    total = 0
    for a in range(len(kept)):
        for b in range(a + 1, len(kept)):
            i, si = kept[a]
            j, sj = kept[b]
            r = abs(dot(si["vec"], sj["vec"]) - obs[i]["dots"][str(j)])
            if r > threshold:
                return None
            total += r
    return total


def main():
    print(f"验收目标：API={API_URL} WEB={WEB_URL}")
    check("API 健康检查", wait_health(), "60 秒内 /api/health 未就绪")

    if WEB_CHECK:
        try:
            with urllib.request.urlopen(f"{WEB_URL}/", timeout=TIMEOUT) as resp:
                html = resp.read().decode()
            check("Web 页面可达", resp.status == 200 and "<div id=\"root\">" in html)
        except Exception as e:
            check("Web 页面可达", False, str(e))

    vecs6 = [c["vec"] for c in CAT[:6]]

    # 用例 1：唯一解（经 Web 代理提交，验证前后端真实联调）
    p1 = payload(CAT, make_obs(CLASSES6, vecs6), threshold=0, outliers=0)
    code, r1 = http("POST", f"{WEB_URL if WEB_CHECK else API_URL}/api/identify", p1)
    check("唯一解实例返回 200", code == 200, f"HTTP {code}: {r1}")
    if code == 200:
        check("唯一解实例状态 ok", r1.get("status") == "ok", str(r1)[:200])
        check("唯一解实例保留 6/6", r1.get("retained_count") == 6)
        check("唯一解实例残差和为 0", r1.get("residual_sum") == 0)
        check("唯一解实例序列正确", r1.get("sequence") == [0, 1, 2, 3, 4, 5],
              str(r1.get("sequence")))
        check("唯一解实例无多解", r1.get("multiple") is False)

    # 同一实例直连 API，结果应与代理一致
    code_d, r1d = http("POST", f"{API_URL}/api/identify", p1)
    check("直连 API 与代理结果一致",
          code_d == 200 and r1d.get("sequence") == r1.get("sequence"))

    # 用例 2：不相容
    bad_meas = [[100 if i != j else 0 for j in range(6)] for i in range(6)]
    obs_bad = [{"cls": c, "dots": {str(j): bad_meas[i][j] for j in range(6) if j != i}}
               for i, c in enumerate(CLASSES6)]
    code, r2 = http("POST", f"{API_URL}/api/identify",
                    payload(CAT, obs_bad, threshold=2, outliers=3))
    check("不相容实例返回 200", code == 200, f"HTTP {code}")
    check("不相容实例状态 infeasible", r2.get("status") == "infeasible", str(r2)[:200])

    # 用例 3：多解 + 见证（独立复算）
    dup_vecs = [[1, 2, 3]] + [c["vec"] for c in CAT_DUP[:5]]
    obs3 = make_obs(CLASSES6, dup_vecs)
    code, r3 = http("POST", f"{API_URL}/api/identify",
                    payload(CAT_DUP, obs3, threshold=0, outliers=0))
    check("多解实例返回 200", code == 200, f"HTTP {code}")
    if code == 200:
        check("多解实例标记 multiple", r3.get("multiple") is True, str(r3)[:200])
        check("规范映射取字典序最小", r3.get("sequence") == [10, 0, 1, 2, 3, 4],
              str(r3.get("sequence")))
        check("见证映射不同", r3.get("witness_sequence") == [11, 0, 1, 2, 3, 4],
              str(r3.get("witness_sequence")))
        c_cost = verify_mapping(r3.get("canonical", []), CAT_DUP, obs3, 0)
        w_cost = verify_mapping(r3.get("witness", []), CAT_DUP, obs3, 0)
        check("规范映射真实满足约束", c_cost == 0, f"复算残差和={c_cost}")
        check("见证映射真实满足约束且同优", w_cost == r3.get("residual_sum"),
              f"复算残差和={w_cost}")

    # 用例 4：离群剔除
    obs4 = make_obs(CLASSES6, vecs6, corrupt={5})
    code, r4 = http("POST", f"{API_URL}/api/identify",
                    payload(CAT, obs4, threshold=0, outliers=1))
    check("离群实例返回 200", code == 200, f"HTTP {code}")
    if code == 200:
        check("离群实例剔除伪星", r4.get("drops") == [5], str(r4.get("drops")))
        check("离群实例保留 5/6", r4.get("retained_count") == 5)

    # 用例 5：校验失败（范数不等）必须 422 且带定位路径
    bad_cat = [dict(c) for c in CAT]
    bad_cat[3]["vec"] = [5, 5, 5]
    code, r5 = http("POST", f"{API_URL}/api/identify",
                    payload(bad_cat, make_obs(CLASSES6, vecs6)))
    errs = r5.get("errors", []) if isinstance(r5, dict) else []
    check("非法实例返回 422", code == 422, f"HTTP {code}")
    check("非法实例错误带定位路径",
          any(e.get("path") == "catalog[3].vec" for e in errs), str(errs)[:200])

    # 用例 6：点积不对称必须 422
    obs6 = make_obs(CLASSES6, vecs6)
    obs6[1]["dots"]["3"] += 1
    code, r6 = http("POST", f"{API_URL}/api/identify",
                    payload(CAT, obs6))
    check("不对称点积返回 422", code == 422 and r6.get("status") == "invalid",
          f"HTTP {code}")

    print()
    if FAILURES:
        print(f"验收失败 {len(FAILURES)} 项：")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("全部验收用例通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
