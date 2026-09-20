# 星场身份识别审计台

星敏感器受粒子噪声干扰混入伪星后，姿态工程师需要**可复算的整片星场身份结论**。
本系统提供 React 审计页面 + FastAPI 精确识别服务：编辑星表与观测矩阵后一键识别，
以 SVG 展示保留、剔除与配对关系；多解时给出规范映射与另一份真实见证；不相容与
输入非法均有明确结论与定位。

## 问题定义与优化层级

一次输入包含：

| 项 | 约束 |
| --- | --- |
| 有序观测 | 6–18 个，每个含亮度类别及与其他观测的整数点积测量（对称矩阵） |
| 目录星 | 8–180 颗，等范数整数三维向量，标识为唯一非负整数 |
| 离群名额 | 0–3 个（至多剔除 3 个伪星观测） |
| 类别配额 | 每个亮度类别的候选目录星 ≤ 20 颗 |
| 残差阈值 | 非负整数 |

后端以**精确整数搜索**注入映射（自研分支限界，不调用通用约束求解器），约束：

- 仅允许同亮度类别配对，映射单射；
- 每对保留观测的目录点积与实测点积之差的绝对值 ≤ 阈值。

目标依次 lexicographic 优化：

1. **最大化保留观测数**（最小化剔除数）；
2. **最小化全部保留对的残差和**；
3. **按观测顺序的目录标识序列取字典序最小**——被剔除观测记为 `-1`，
   由于目录标识均非负，`-1` 排在任何标识之前（即同优时倾向剔除更靠前的观测，
   该约定保证结论唯一且可复算）。

前两级同优的映射存在多份时，接口返回 `multiple: true`、字典序最小的**规范映射**
以及另一份真实**见证映射**（二者残差和相同、映射不同）。

## 快速开始（Docker）

```bash
cp .env.example .env        # 可选：自定义端口与健康检查
docker compose up --build   # 启动 web 与 api
```

- Web：<http://localhost:8080>（`WEB_PORT` 可配）
- API：<http://localhost:8000/api/health>（`API_PORT` 可配）

### 验收服务

Compose 内置名为 `verify` 的可执行验收服务，对运行中的 Web 与 API
执行端到端用例（唯一解、不相容、多解见证、离群剔除、校验失败、代理联调）：

```bash
docker compose up --build --exit-code-from verify verify
# 或
docker compose run --rm verify
```

全部通过时退出码为 0，否则为 1 并打印失败明细。

### 可配置项（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `API_PORT` / `WEB_PORT` | 8000 / 8080 | 宿主机端口 |
| `HEALTHCHECK_PATH` | `/api/health` | API 健康检查路径 |
| `HEALTHCHECK_INTERVAL` / `TIMEOUT` / `RETRIES` / `START_PERIOD` | 10s / 5s / 5 / 5s | 健康检查参数 |

## 本地开发

```bash
# API（端口 8000）
cd api && pip install -r requirements.txt
uvicorn app.main:app --reload

# Web（端口 5173，/api 代理至 8000）
cd web && npm install && npm run dev

# 求解器单元测试
cd api && python -m pytest tests/

# 验收脚本（本地联调）
API_URL=http://127.0.0.1:8000 WEB_URL=http://127.0.0.1:5173 python3 verify/verify.py
```

## API 契约

### `POST /api/identify`

```json
{
  "threshold": 1,
  "max_outliers": 2,
  "catalog": [{"id": 0, "cls": "A", "vec": [1, 2, 3]}],
  "observations": [{"cls": "A", "dots": {"1": 14, "2": -3}}]
}
```

- `200 {"status": "ok", ...}`：`sequence`（目录标识序列，`-1`=剔除）、
  `canonical` / `witness`（映射明细）、`pair_residuals`（保留对残差表）、
  `retained_count`、`residual_sum`、`drops`、`multiple`、`nodes`、`elapsed_ms`；
- `200 {"status": "infeasible"}`：给定名额与阈值内不存在可行映射；
- `422 {"status": "invalid", "errors": [{"path", "message"}]}`：校验失败，
  `path` 形如 `catalog[3].vec[1]`、`observations[0].dots.4`，页面据此定位并保留草稿。

### `GET /api/health` → `{"status": "ok"}`

## 目录结构

```
├── docker-compose.yml      # web + api + verify 编排，端口/健康检查可配
├── api/                    # FastAPI 精确整数搜索服务
│   ├── app/solver.py       # 分支限界 + 字典序构造 + 见证搜索（无通用求解器）
│   ├── app/validation.py   # 服务端校验（带定位路径）
│   └── tests/              # 求解器与校验单元测试
├── web/                    # React + Vite 审计页面（nginx 反代 /api）
└── verify/                 # 可执行验收服务
```
