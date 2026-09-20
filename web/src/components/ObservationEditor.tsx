import type { Issue, Observation } from "../types";

interface Props {
  observations: Observation[];
  issues: Issue[];
  onChange: (observations: Observation[]) => void;
  onMatrixResize: (n: number) => void;
}

export default function ObservationEditor({
  observations,
  issues,
  onChange,
  onMatrixResize,
}: Props) {
  const setMag = (i: number, raw: string) => {
    const value: number | string = raw === "" || raw === "-" ? raw : Number(raw);
    onChange(observations.map((o, k) => (k === i ? { magnitude: value } : o)));
  };
  const remove = (i: number) => {
    if (observations.length <= 6) return;
    const next = observations.filter((_, k) => k !== i);
    onChange(next);
    onMatrixResize(next.length);
  };
  const add = () => {
    if (observations.length >= 18) return;
    onChange([...observations, { magnitude: 0 }]);
    onMatrixResize(observations.length + 1);
  };

  const fieldIssue = (i: number) =>
    issues.find((x) => x.loc[0] === "observations" && x.loc[1] === i && x.loc[2] === "magnitude");

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>② 有序观测</h2>
        <span className={`counter ${observations.length < 6 || observations.length > 18 ? "bad" : ""}`}>
          {observations.length} / 6–18（顺序即配对字典序）
        </span>
      </div>
      <div className="obs-chips">
        {observations.map((o, i) => (
          <div key={i} className={`obs-chip ${fieldIssue(i) ? "chip-bad" : ""}`}>
            <span className="obs-index">#{i}</span>
            <label>
              类别
              <input
                type="number"
                id={`f-observations-${i}-magnitude`}
                value={o.magnitude}
                className={fieldIssue(i) ? "input-bad" : ""}
                onChange={(e) => setMag(i, e.target.value)}
              />
            </label>
            <button
              className="btn-mini danger"
              onClick={() => remove(i)}
              disabled={observations.length <= 6}
              title="删除该观测并同步收缩点积矩阵"
            >
              ×
            </button>
          </div>
        ))}
        <button className="btn-mini" onClick={add} disabled={observations.length >= 18}>
          + 观测
        </button>
      </div>
    </section>
  );
}
