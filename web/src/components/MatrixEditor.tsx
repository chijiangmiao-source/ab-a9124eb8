import type { Issue } from "../types";

interface Props {
  matrix: number[][];
  issues: Issue[];
  onChange: (matrix: number[][]) => void;
}

export default function MatrixEditor({ matrix, issues, onChange }: Props) {
  const n = matrix.length;

  const setCell = (i: number, j: number, raw: string) => {
    const v = raw === "" || raw === "-" ? 0 : Number(raw);
    const next = matrix.map((row) => row.slice());
    next[i][j] = v;
    next[j][i] = v; // symmetry enforced on edit
    onChange(next);
  };

  const cellIssue = (i: number, j: number) =>
    issues.find(
      (x) =>
        x.loc[0] === "dot_measurements" &&
        x.loc[1] === i &&
        (x.loc.length === 2 || x.loc[2] === j),
    );
  const rowIssue = (i: number) =>
    issues.find((x) => x.loc[0] === "dot_measurements" && x.loc[1] === i && x.loc.length === 2);
  const matrixIssue = issues.find((x) => x.loc[0] === "dot_measurements" && x.loc.length === 1);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>③ 点积测量矩阵（整数，对称）</h2>
        <span className={matrixIssue ? "counter bad" : "counter"}>
          {n}×{n}
        </span>
      </div>
      {matrixIssue && <div className="local-warn">{matrixIssue.message}</div>}
      <div className="table-scroll matrix-scroll">
        <table className="matrix-table">
          <thead>
            <tr>
              <th></th>
              {Array.from({ length: n }, (_, j) => (
                <th key={j}>#{j}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => (
              <tr key={i} className={rowIssue(i) ? "row-bad" : ""}>
                <th>#{i}</th>
                {row.map((val, j) => {
                  const issue = cellIssue(i, j);
                  const diag = i === j;
                  const lower = i > j;
                  return (
                    <td key={j} title={issue?.message}>
                      <input
                        id={`f-dot-${i}-${j}`}
                        value={val}
                        disabled={diag || lower}
                        readOnly={diag || lower}
                        className={[
                          "matrix-cell",
                          diag ? "cell-diag" : "",
                          lower ? "cell-lower" : "",
                          issue ? "input-bad" : "",
                        ].join(" ")}
                        onChange={(e) => setCell(i, j, e.target.value)}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">仅上三角可编辑，下三角自动镜像；对角线为 0。</p>
    </section>
  );
}
