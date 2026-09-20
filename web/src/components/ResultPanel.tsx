import type { SolveResult } from "../types";
import StarFieldSvg from "./StarFieldSvg";
import type { CatalogStar } from "../types";

interface Props {
  result: SolveResult;
  catalog: CatalogStar[];
}

function MappingTable({ result, witness }: { result: SolveResult; witness: boolean }) {
  const m = witness ? result.witness : result.canonical;
  if (!m) return null;
  return (
    <table className="result-table">
      <thead>
        <tr>
          <th>观测顺序</th>
          <th>结论</th>
          <th>目录标识</th>
        </tr>
      </thead>
      <tbody>
        {m.sequence.map((sid, i) => (
          <tr key={i} className={sid ? "" : "row-reject"}>
            <td>#{i}</td>
            <td>{sid ? "保留配对" : "剔除（伪星）"}</td>
            <td className="mono">{sid ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ResultPanel({ result, catalog }: Props) {
  if (result.status === "incompatible") {
    return (
      <section className="panel result-panel">
        <div className="verdict incompatible">
          <h2>⛔ 不相容（INCOMPATIBLE）</h2>
          <p>{result.message}</p>
          <ul className="verdict-meta">
            <li>最多可保留：<b>{result.kept_count}</b> 颗</li>
            <li>可行方案至少保留：<b>{result.required_kept}</b> 颗</li>
            <li>离群名额：{result.outlier_quota}　残差阈值：{result.threshold}</li>
            <li>搜索节点数：{result.search_nodes}　耗时：{result.elapsed_ms} ms</li>
          </ul>
          <p className="hint">
            草稿已保留：可放宽阈值 / 增加离群名额 / 修正测量后重新识别。
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel result-panel">
      <div className="verdict optimal">
        <h2>✅ 识别成功</h2>
        <div className="verdict-stats">
          <div><b>{result.kept_count}</b><span>保留观测</span></div>
          <div><b>{result.rejected_count}</b><span>剔除伪星</span></div>
          <div><b>{result.residual_sum}</b><span>残差和（最优）</span></div>
          <div><b>{result.search_nodes}</b><span>搜索节点</span></div>
        </div>
        <p className="hint">
          优化优先级：① 保留数最大 → ② 全部保留对残差和最小 →
          ③ 观测顺序的目录标识序列字典序最小（剔除视为排在所有标识之前）。
        </p>
      </div>

      {result.multiple && (
        <div className="multi-banner">
          <h3>⚠️ 检测到多解：前两级同优的注入映射不止一份</h3>
          <p>
            下列两份映射具有相同的保留数（{result.kept_count}）与相同的残差和
            （{result.residual_sum}）。绿色实线为<b>规范映射</b>（字典序最小），
            琥珀色虚线为另一份<b>真实见证映射</b>。
          </p>
        </div>
      )}
      {!result.multiple && (
        <div className="unique-banner">
          ℹ️ 在前两级最优层面映射唯一，不存在第二份同优见证。
        </div>
      )}

      <StarFieldSvg catalog={catalog} result={result} />

      <div className="mapping-columns">
        <div>
          <h3>规范映射（canonical）</h3>
          <MappingTable result={result} witness={false} />
        </div>
        {result.multiple && result.witness && (
          <div>
            <h3>另一份见证（witness）</h3>
            <MappingTable result={result} witness={true} />
          </div>
        )}
      </div>

      <details className="pairs-detail">
        <summary>全部保留对残差明细（{result.canonical?.residual_pairs.length} 对）</summary>
        <table className="result-table small">
          <thead>
            <tr>
              <th>观测对</th><th>目录对</th><th>测量</th><th>实际</th><th>|残差|</th>
            </tr>
          </thead>
          <tbody>
            {result.canonical?.residual_pairs.map((p) => (
              <tr key={`${p.i}-${p.j}`} className={p.residual > result.threshold ? "row-bad" : ""}>
                <td>#{p.i} ↔ #{p.j}</td>
                <td className="mono">{p.catalog_i} ↔ {p.catalog_j}</td>
                <td>{p.measured}</td>
                <td>{p.actual}</td>
                <td className={p.residual === 0 ? "zero" : ""}>{p.residual}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
