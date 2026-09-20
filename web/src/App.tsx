import { useEffect, useMemo, useState } from "react";
import type {
  CatalogStar,
  Issue,
  Observation,
  Scenario,
  SolveResult,
} from "./types";
import { fetchHealth, fetchScenarios, solve, ValidationFailed } from "./api";
import CatalogEditor from "./components/CatalogEditor";
import ObservationEditor from "./components/ObservationEditor";
import MatrixEditor from "./components/MatrixEditor";
import ResultPanel from "./components/ResultPanel";

const INITIAL_DRAFT = {
  catalog: [] as CatalogStar[],
  observations: [{ magnitude: 0 }] as Observation[],
  matrix: [[0]] as number[][],
};

function resizeMatrix(prev: number[][], n: number): number[][] {
  const next = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => (prev[i]?.[j] ?? 0)),
  );
  return next;
}

function locInputId(loc: (string | number)[]): string | null {
  if (loc[0] === "catalog" && loc.length >= 3)
    return `f-catalog-${loc[1]}-${loc[2]}`;
  if (loc[0] === "observations" && loc.length >= 3)
    return `f-observations-${loc[1]}-${loc[2]}`;
  if (loc[0] === "dot_measurements" && loc.length === 3)
    return `f-dot-${loc[1]}-${loc[2]}`;
  if (loc[0] === "threshold") return "f-threshold";
  if (loc[0] === "outlier_quota") return "f-quota";
  return null;
}

function locSection(loc: (string | number)[]): string | null {
  const map: Record<string, string> = {
    catalog: "section-catalog",
    observations: "section-observations",
    dot_measurements: "section-matrix",
    threshold: "section-params",
    outlier_quota: "section-params",
  };
  return map[String(loc[0])] ?? null;
}

export default function App() {
  const [health, setHealth] = useState<string>("checking");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [catalog, setCatalog] = useState<CatalogStar[]>(INITIAL_DRAFT.catalog);
  const [observations, setObservations] = useState<Observation[]>(
    INITIAL_DRAFT.observations,
  );
  const [matrix, setMatrix] = useState<number[][]>(INITIAL_DRAFT.matrix);
  const [threshold, setThreshold] = useState<number>(1);
  const [quota, setQuota] = useState<number>(2);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(false);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [activeScenario, setActiveScenario] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("down"));
    fetchScenarios()
      .then((list) => {
        setScenarios(list);
        if (list[0]) loadScenario(list[0]);
      })
      .catch(() => setScenarios([]));
  }, []);

  // clear stale field errors as the user edits
  const touch = () => {
    if (issues.length) setIssues([]);
    if (networkError) setNetworkError(null);
  };

  const classCounts = useMemo(() => {
    const m = new Map<number, number>();
    for (const s of catalog) m.set(s.magnitude, (m.get(s.magnitude) ?? 0) + 1);
    return m;
  }, [catalog]);
  const classOverflow = [...classCounts.entries()].filter(([, c]) => c > 20);

  const loadScenario = (sc: Scenario) => {
    setCatalog(sc.catalog.map((s) => ({ ...s, vector: [...s.vector] as [number, number, number] })));
    setObservations(sc.observations.map((o) => ({ ...o })));
    setMatrix(sc.dot_measurements.map((r) => r.slice()));
    setThreshold(sc.threshold);
    setQuota(sc.outlier_quota);
    setIssues([]);
    setResult(null);
    setNetworkError(null);
    setActiveScenario(sc.key);
  };

  const onRun = async () => {
    setLoading(true);
    setIssues([]);
    setNetworkError(null);
    try {
      const r = await solve({
        threshold,
        outlier_quota: quota,
        catalog,
        observations,
        dot_measurements: matrix,
      });
      setResult(r);
    } catch (e) {
      if (e instanceof ValidationFailed) {
        setIssues(e.issues);
        setResult(null);
      } else {
        setNetworkError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  };

  const focusIssue = (issue: Issue) => {
    const id = locInputId(issue.loc);
    if (id) {
      const el = document.getElementById(id) as HTMLInputElement | null;
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.focus();
        return;
      }
    }
    const sec = locSection(issue.loc);
    if (sec) document.getElementById(sec)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>星场身份审计台</h1>
          <p className="subtitle">
            精确整数分支限界搜索 · 注入映射可复算 · 保留 / 剔除 / 配对全审计
          </p>
        </div>
        <div className={`health health-${health}`}>
          API：{health === "ok" ? "● 已连接" : health === "checking" ? "◌ 检测中" : "○ 未连接"}
        </div>
      </header>

      <div className="scenario-bar">
        <b>预设场景：</b>
        {scenarios.map((sc) => (
          <button
            key={sc.key}
            className={`btn-scenario ${activeScenario === sc.key ? "active" : ""}`}
            onClick={() => loadScenario(sc)}
            title={sc.description}
          >
            {sc.title}
          </button>
        ))}
        {activeScenario && scenarios.find((s) => s.key === activeScenario) && (
          <span className="scenario-desc">
            {scenarios.find((s) => s.key === activeScenario)!.description}
          </span>
        )}
      </div>

      <div className="layout">
        <div className="col-edit">
          <section className="panel" id="section-params">
            <div className="panel-head"><h2>⓪ 识别参数</h2></div>
            <div className="params-row">
              <label className="param">
                残差阈值（非负整数）
                <input
                  id="f-threshold"
                  type="number" min={0} value={threshold}
                  className={issues.some((i) => i.loc[0] === "threshold") ? "input-bad" : ""}
                  onChange={(e) => { touch(); setThreshold(Number(e.target.value)); }}
                />
              </label>
              <label className="param">
                离群名额（0–3）
                <input
                  id="f-quota"
                  type="number" min={0} max={3} value={quota}
                  className={issues.some((i) => i.loc[0] === "outlier_quota") ? "input-bad" : ""}
                  onChange={(e) => { touch(); setQuota(Number(e.target.value)); }}
                />
              </label>
              <button className="btn-run" onClick={onRun} disabled={loading}>
                {loading ? "搜索中…" : "▶ 运行精确识别"}
              </button>
            </div>
            {classOverflow.length > 0 && (
              <div className="local-warn">
                亮度类别 {classOverflow.map(([m, c]) => `${m}（${c} 颗）`).join("、")}
                超过每类最多 20 颗候选星
              </div>
            )}
          </section>

          <div id="section-catalog">
            <CatalogEditor catalog={catalog} issues={issues}
              onChange={(c) => { touch(); setCatalog(c); }} />
          </div>
          <div id="section-observations">
            <ObservationEditor
              observations={observations}
              issues={issues}
              onChange={(o) => { touch(); setObservations(o); }}
              onMatrixResize={(n) => { touch(); setMatrix((m) => resizeMatrix(m, n)); }}
            />
          </div>
          <div id="section-matrix">
            <MatrixEditor matrix={matrix} issues={issues}
              onChange={(m) => { touch(); setMatrix(m); }} />
          </div>
        </div>

        <div className="col-result">
          {networkError && (
            <section className="panel">
              <div className="error-banner">
                网络/服务错误：{networkError}（草稿已保留，API 恢复后可重试）
              </div>
            </section>
          )}
          {issues.length > 0 && (
            <section className="panel">
              <div className="error-banner">
                <h3>校验失败：草稿已保留，共 {issues.length} 处问题</h3>
                <ul className="issue-list">
                  {issues.map((iss, k) => (
                    <li key={k}>
                      <button className="issue-link" onClick={() => focusIssue(iss)}>
                        <code>{iss.loc.length ? iss.loc.join(" → ") : "(请求)"}</code>
                      </button>
                      <span>{iss.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}
          {result && <ResultPanel result={result} catalog={catalog} />}
          {!result && issues.length === 0 && !networkError && (
            <section className="panel placeholder-panel">
              <h2>审计结论将显示在这里</h2>
              <p>
                载入上方预设场景，或在左侧编辑星表、观测与点积矩阵后点击
                「运行精确识别」。后端不会调用任何通用约束求解器：
                搜索过程是手工实现的整数分支限界，先最大化保留数，
                再最小化残差和，最后取字典序规范解并尝试给出第二份真实见证。
              </p>
              <ul>
                <li>无可行映射 → 明确显示<b>不相容</b>及瓶颈；</li>
                <li>前两级同优存在多份映射 → 显示<b>多解</b>、规范映射与见证；</li>
                <li>校验失败 → <b>保留草稿</b>，点击问题可定位到输入格。</li>
              </ul>
            </section>
          )}
        </div>
      </div>

      <footer className="app-footer">
        FastAPI + React · 所有向量与点积均为精确整数运算 · 无通用求解器依赖
      </footer>
    </div>
  );
}
