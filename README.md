# 星场身份审计台（Star-Field Identification Audit Console）

卫星星敏感器受高能粒子噪声干扰后，观测中会混入**伪星**。按最近角距逐颗贪心配对，
伪星可能提前占用真正的对应星，使后续识别级联失败。本项目对**整片星场**做一次
可复算的全局审计：在满足全部观测间点积一致性的前提下，求解观测→目录星的
**注入映射（injection mapping）**，明确每颗观测是「保留配对」还是「剔除伪星」，
并给出规范解、多解见证或不相容结论。

- **前端**：React 18 + Vite + TypeScript，编辑星表 / 有序观测 / 整数点积矩阵，
  SVG 展示目录星、观测、保留（实线）、剔除（红叉）、见证（虚线）与逐对残差。
- **后端**：FastAPI，核心为**纯 Python 精确整数分支限界搜索**，不调用任何
  通用 SAT / CP / MIP 求解器（依赖中也没有这类库）。
- **部署**：`Dockerfile` + `docker compose` 一键启动真实联调的 web / api；
  另有名为 `verify` 的可执行验收服务，对真实 HTTP 接口跑断言。

## 快速开始

```bash
cp .env.example .env          # 可选：修改宿主机端口与健康检查参数
docker compose up --build
# 打开 http://localhost:8080
# API 文档 http://localhost:8000/docs
```

运行可执行验收服务（健康检查、三个内置场景、422 定位、20 组随机实例对拍穷举
oracle，全过退出码 0）：

```bash
docker compose --profile acceptance run --rm verify
# 较新版本 Compose 也可直接：docker compose run --rm verify
```

本地非 Docker 开发：

```bash
# 后端
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
python -m app.verify http://127.0.0.1:8000      # 验收
python -m pytest -q                              # HTTP 测试
python test_oracle.py                            # 250 组穷举对拍

# 前端
cd web && npm install && npm run dev            # http://localhost:5173 ，/api 代理到 8000
npm test                                         # React 渲染冒烟测试
npm run build
```

## 输入规范（与需求逐项对应）

| 项 | 约束（后端强制校验，违反返回 422 且精确定位） |
| --- | --- |
| 有序观测 | 6–18 个，每个给出整数亮度类别 |
| 目录星 | 8–180 颗，标识唯一；三维**整数向量且全部等范数** |
| 每类候选 | 同一亮度类别的目录星 **≤ 20 颗** |
| 点积测量 | 观测对之间的**整数**点积，方阵须对称、对角为 0 |
| 残差阈值 | 非负整数，保留对仅允许 `|目录点积 − 测量| ≤ 阈值` |
| 离群名额 | 0–3，被剔除的伪星观测数不得超过该值 |
| 配对限制 | 仅允许**同亮度类别**配对，且每颗目录星至多占用一次 |

## 优化目标（严格字典优先级）

搜索全部精确整数运算，目标依次为：

1. **最大化保留观测数**；
2. 在保留数相同的方案中，**最小化全部保留对的残差绝对值之和**；
3. 前两级并列时，取「按观测顺序的目录标识序列」**字典序最小**的规范映射
   （剔除位 `-1` 排在所有目录标识之前）。

输出语义：

- 无可行映射 → HTTP 200 且 `status="incompatible"`，页面红牌明示不相容与
  瓶颈（最多可保留数 vs 至少需要保留数）；
- 前两级同优存在多份映射 → `multiple=true`，同时返回**规范映射** `canonical`
  与另一份**真实见证映射** `witness`（保证与规范不同、保留数与残差和相同）；
  唯一时 `witness=null`；
- 校验失败 → HTTP 422 + `issues:[{loc,message}]`，前端**保留草稿**，
  点击问题列表可滚动并聚焦到具体输入格。

## 搜索算法（无通用求解器）

`backend/app/solver.py` 手写分支限界，状态为每个观测的决策
（未决策 / 剔除 / 占用的目录星位置）：

- 同亮度候选预过滤 + 成对可行表与整数残差表；
- 强制剔除：候选域为空的未决策观测确定性地消耗一个离群名额；
- **MRV** 选最小候选域观测分支；
- **Hall 松弛**：未决策观测→未占用目录星做 Kuhn 二分图最大匹配，
  匹配数不足以覆盖「必须保留数」时立即剪枝；
- 记忆化布尔可行性，逐级完成：①最大保留数 ②整数下界剪枝的最小残差和
  ③按「剔除优先、标识升序」的严格序枚举，产出规范解与至多第二份见证。

规模上限（18 观测 / 180 目录星 / 每类 20）下实测通常仅需几十毫秒
（`search_nodes` 与 `elapsed_ms` 会在响应中返回，可复算审计）。

## 仓库结构

```
backend/
  app/solver.py      # 精确整数分支限界引擎（本项目核心）
  app/scenarios.py   # 三个内置场景（前端与 verify 共用的唯一数据源）
  app/main.py        # FastAPI：/api/health /api/scenarios /api/solve
  app/verify.py      # verify 服务：HTTP 验收 + 穷举 oracle 对拍
  test_oracle.py     # 250 组随机实例的引擎 vs 穷举对拍
  test_api.py        # 真实 FastAPI 应用的 HTTP 测试
  Dockerfile
web/
  src/components/    # 星表/观测/矩阵编辑器、结论面板、StarFieldSvg
  src/test/          # 四种审计结论的 React 渲染测试
  nginx.conf         # 静态托管 + /api 反代 api:8000
  Dockerfile         # 多阶段构建（node 构建，nginx 运行）
docker-compose.yml   # api / web / verify（profiles: acceptance）
.env.example         # 宿主机端口与健康检查参数
```

## SVG 审计图读法

- 左半部分：目录星按亮度类别分列（颜色编码类别），绿边实心＝被规范映射占用，
  琥珀虚环＝仅被见证映射占用；
- 右半部分：有序观测列，绿色描边＝保留，暗红底红叉＝剔除伪星；
- 绿色贝塞尔线＝规范配对，琥珀虚线＝见证配对；
- 观测右侧弧线＝保留对残差，颜色由绿（0）渐变到红（阈值），悬停查看
  `|实际目录点积 − 测量|` 明细。
