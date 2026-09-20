"""请求校验：全部规则在服务端精确落实，错误带定位路径返回。

输入契约：
  threshold:    非负整数
  max_outliers: 0..3 的整数
  catalog:      8..180 颗目录星，每颗 {id, cls, vec:[x,y,z]}
                - id 为 0..1e9 的唯一非负整数
                - vec 为整数三维向量，分量 |v| <= 1e6
                - 全部目录星范数相等
                - 同一亮度类别的目录星不超过 20 颗
  observations: 6..18 个有序观测，每个 {cls, dots}
                - dots 为对象，键为其他观测序号（字符串），值为整数点积
                - 全部无序对必须成对出现且数值一致（对称）
"""

MAX_COORD = 10 ** 6
MAX_ID = 10 ** 9
MAX_DOT = 10 ** 12
MAX_THRESHOLD = 10 ** 12
MAX_CLASS_LEN = 16


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_cls(cls, path, errors):
    if not isinstance(cls, str) or not cls.strip():
        errors.append({"path": path, "message": "亮度类别必须是非空字符串"})
        return None
    cls = cls.strip()
    if len(cls) > MAX_CLASS_LEN:
        errors.append({"path": path, "message": f"亮度类别长度不能超过 {MAX_CLASS_LEN} 个字符"})
        return None
    return cls


def validate_payload(payload):
    """返回 (data, errors)。data 为规范化后的求解输入，errors 非空时 data 为 None。"""
    errors = []
    if not isinstance(payload, dict):
        return None, [{"path": "", "message": "请求体必须是 JSON 对象"}]

    # ---- threshold / max_outliers --------------------------------------
    threshold = payload.get("threshold")
    if not _is_int(threshold) or threshold < 0 or threshold > MAX_THRESHOLD:
        errors.append({"path": "threshold", "message": "阈值必须是 0 到 1e12 之间的整数"})

    max_outliers = payload.get("max_outliers")
    if not _is_int(max_outliers) or max_outliers < 0 or max_outliers > 3:
        errors.append({"path": "max_outliers", "message": "离群名额必须是 0 到 3 之间的整数"})

    # ---- catalog --------------------------------------------------------
    catalog_raw = payload.get("catalog")
    catalog = []
    if not isinstance(catalog_raw, list):
        errors.append({"path": "catalog", "message": "目录星表必须是数组"})
    else:
        n = len(catalog_raw)
        if n < 8 or n > 180:
            errors.append({"path": "catalog", "message": f"目录星数量必须在 8 到 180 之间（当前 {n}）"})
        seen_ids = set()
        norms = []
        class_count = {}
        for idx, star in enumerate(catalog_raw):
            base = f"catalog[{idx}]"
            if not isinstance(star, dict):
                errors.append({"path": base, "message": "目录星必须是对象"})
                continue
            sid = star.get("id")
            if not _is_int(sid) or sid < 0 or sid > MAX_ID:
                errors.append({"path": f"{base}.id", "message": "目录标识必须是 0 到 1e9 之间的整数"})
                sid = None
            elif sid in seen_ids:
                errors.append({"path": f"{base}.id", "message": f"目录标识 {sid} 重复"})
                sid = None
            else:
                seen_ids.add(sid)
            cls = _check_cls(star.get("cls"), f"{base}.cls", errors)
            vec = star.get("vec")
            norm = None
            if (not isinstance(vec, list)) or len(vec) != 3:
                errors.append({"path": f"{base}.vec", "message": "向量必须是长度为 3 的整数数组"})
                vec = None
            else:
                for c in range(3):
                    if not _is_int(vec[c]) or abs(vec[c]) > MAX_COORD:
                        errors.append({
                            "path": f"{base}.vec[{c}]",
                            "message": "向量分量必须是绝对值不超过 1e6 的整数",
                        })
                        vec = None
                        break
                if vec is not None:
                    norm = vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2
                    norms.append((idx, norm))
            if cls is not None:
                class_count[cls] = class_count.get(cls, 0) + 1
            if sid is not None and cls is not None and vec is not None:
                catalog.append({"id": sid, "cls": cls, "vec": list(vec)})
        if norms:
            ref_idx, ref_norm = norms[0]
            for idx, norm in norms:
                if norm != ref_norm:
                    errors.append({
                        "path": f"catalog[{idx}].vec",
                        "message": f"范数平方 {norm} 与 catalog[{ref_idx}] 的 {ref_norm} 不一致：目录星必须等范数",
                    })
        for cls, cnt in class_count.items():
            if cnt > 20:
                errors.append({
                    "path": "catalog",
                    "message": f"亮度类别 “{cls}” 的候选目录星有 {cnt} 颗，超过 20 颗上限",
                })

    # ---- observations ---------------------------------------------------
    obs_raw = payload.get("observations")
    obs_classes = []
    meas = None
    if not isinstance(obs_raw, list):
        errors.append({"path": "observations", "message": "观测列表必须是数组"})
    else:
        m = len(obs_raw)
        if m < 6 or m > 18:
            errors.append({"path": "observations", "message": f"观测数量必须在 6 到 18 之间（当前 {m}）"})
        dots_matrix = [[0] * m for _ in range(m)]
        provided = {}
        for i, obs in enumerate(obs_raw):
            base = f"observations[{i}]"
            if not isinstance(obs, dict):
                errors.append({"path": base, "message": "观测必须是对象"})
                continue
            cls = _check_cls(obs.get("cls"), f"{base}.cls", errors)
            obs_classes.append(cls if cls is not None else "")
            dots = obs.get("dots")
            if not isinstance(dots, dict):
                errors.append({"path": f"{base}.dots", "message": "点积测量必须是对象（键为观测序号）"})
                continue
            for key, value in dots.items():
                try:
                    j = int(key)
                except (TypeError, ValueError):
                    errors.append({"path": f"{base}.dots.{key}", "message": "点积键必须是观测序号"})
                    continue
                if str(j) != str(key) or j < 0 or j >= m:
                    errors.append({"path": f"{base}.dots.{key}", "message": f"观测序号 {key} 超出范围"})
                    continue
                if j == i:
                    errors.append({"path": f"{base}.dots.{key}", "message": "不需要提供与自身的点积"})
                    continue
                if not _is_int(value) or abs(value) > MAX_DOT:
                    errors.append({"path": f"{base}.dots.{key}", "message": "点积必须是绝对值不超过 1e12 的整数"})
                    continue
                provided[(i, j)] = value
        for i in range(m):
            for j in range(i + 1, m):
                a = provided.get((i, j))
                b = provided.get((j, i))
                if a is None and b is None:
                    errors.append({
                        "path": f"observations[{i}].dots.{j}",
                        "message": f"缺少观测 {i} 与观测 {j} 的点积测量",
                    })
                elif a is None or b is None:
                    errors.append({
                        "path": f"observations[{i}].dots.{j}",
                        "message": f"观测 {i} 与 {j} 的点积只提供了一侧，必须双向对称填写",
                    })
                elif a != b:
                    errors.append({
                        "path": f"observations[{j}].dots.{i}",
                        "message": f"点积不对称：{i}→{j} 为 {a}，{j}→{i} 为 {b}",
                    })
                else:
                    dots_matrix[i][j] = dots_matrix[j][i] = a
        meas = dots_matrix

    if errors:
        return None, errors
    return {
        "threshold": threshold,
        "max_outliers": max_outliers,
        "catalog": catalog,
        "obs_classes": obs_classes,
        "meas": meas,
    }, []
