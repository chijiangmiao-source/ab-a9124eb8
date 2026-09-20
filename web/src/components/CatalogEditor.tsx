import type { CatalogStar, Issue } from "../types";

interface Props {
  catalog: CatalogStar[];
  issues: Issue[];
  onChange: (catalog: CatalogStar[]) => void;
}

export default function CatalogEditor({ catalog, issues, onChange }: Props) {
  const setRow = (i: number, patch: Partial<CatalogStar>) => {
    onChange(catalog.map((s, k) => (k === i ? { ...s, ...patch } : s)));
  };
  const setVec = (i: number, axis: 0 | 1 | 2, raw: string) => {
    const v = catalog[i].vector.slice() as [number, number, number];
    v[axis] = raw === "" || raw === "-" ? (raw as unknown as number) : Number(raw);
    setRow(i, { vector: v });
  };
  const remove = (i: number) => onChange(catalog.filter((_, k) => k !== i));
  const add = () =>
    onChange([
      ...catalog,
      { id: `STAR-${String(catalog.length + 1).padStart(2, "0")}`, magnitude: 0, vector: [3, 0, 0] },
    ]);

  const rowIssue = (i: number) =>
    issues.find((x) => x.loc[0] === "catalog" && x.loc[1] === i && x.loc.length === 2);
  const fieldIssue = (i: number, field: string) =>
    issues.find((x) => x.loc[0] === "catalog" && x.loc[1] === i && x.loc[2] === field);

  const norms = new Set(catalog.map((s) => s.vector.reduce((a, b) => a + b * b, 0)));
  const normBad = norms.size > 1;

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>① 星表目录</h2>
        <span className={`counter ${catalog.length < 8 || catalog.length > 180 ? "bad" : ""}`}>
          {catalog.length} / 8–180
        </span>
      </div>
      {normBad && (
        <div className="local-warn">向量平方范数不一致：{[...norms].join(", ")}（须全部相等）</div>
      )}
      <div className="table-scroll">
        <table className="edit-table">
          <thead>
            <tr>
              <th>#</th>
              <th>目录标识</th>
              <th>亮度类别</th>
              <th>x</th>
              <th>y</th>
              <th>z</th>
              <th>‖v‖²</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {catalog.map((s, i) => {
              const n2 = s.vector.reduce((a, b) => a + (Number(b) || 0) ** 2, 0);
              return (
                <tr key={i} className={rowIssue(i) ? "row-bad" : ""}>
                  <td className="dim">{i}</td>
                  <td>
                    <input
                      id={`f-catalog-${i}-id`}
                      className={fieldIssue(i, "id") ? "input-bad" : ""}
                      value={s.id}
                      onChange={(e) => setRow(i, { id: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      id={`f-catalog-${i}-magnitude`}
                      className={`narrow ${fieldIssue(i, "magnitude") ? "input-bad" : ""}`}
                      value={s.magnitude}
                      onChange={(e) => setRow(i, { magnitude: Number(e.target.value) })}
                    />
                  </td>
                  {([0, 1, 2] as const).map((axis) => (
                    <td key={axis}>
                      <input
                        type="number"
                        id={`f-catalog-${i}-vector`}
                        className={`narrow ${fieldIssue(i, "vector") ? "input-bad" : ""}`}
                        value={s.vector[axis]}
                        onChange={(e) => setVec(i, axis, e.target.value)}
                      />
                    </td>
                  ))}
                  <td className={`dim ${normBad ? "norm-bad" : ""}`}>{n2}</td>
                  <td>
                    <button className="btn-mini danger" onClick={() => remove(i)}>
                      删除
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button className="btn-mini" onClick={add} disabled={catalog.length >= 180}>
        + 添加目录星
      </button>
    </section>
  );
}
