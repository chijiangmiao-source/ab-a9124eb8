import React from 'react';

const AXES = ['x', 'y', 'z'];

export default function CatalogEditor({ rows, setRows, invalid }) {
  const update = (i, key, value) => {
    setRows(rows.map((r, idx) => (idx === i ? { ...r, [key]: value } : r)));
  };
  const addRow = () => {
    const nextId = rows.reduce((m, r) => {
      const n = parseInt(r.id, 10);
      return Number.isFinite(n) ? Math.max(m, n + 1) : m;
    }, 0);
    setRows([...rows, { id: String(nextId), cls: 'A', x: '', y: '', z: '' }]);
  };
  const removeRow = (i) => setRows(rows.filter((_, idx) => idx !== i));

  return (
    <section className="panel">
      <div className="row-actions">
        <h2>目录星表（{rows.length} 颗，8–180，等范数整数向量，每类 ≤ 20）</h2>
        <button type="button" className="secondary small" onClick={addRow}>+ 添加目录星</button>
      </div>
      <div className="table-scroll" data-field="cat-table">
        <table className="grid">
          <thead>
            <tr>
              <th>#</th><th>标识</th><th>亮度类别</th><th>x</th><th>y</th><th>z</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} data-field={`cat-row-${i}`} className={invalid.has(`cat-row-${i}`) ? 'invalid-row' : ''}>
                <td>{i}</td>
                <td>
                  <input data-field={`cat-${i}-id`} className={invalid.has(`cat-${i}-id`) ? 'invalid' : ''}
                    value={r.id} onChange={(e) => update(i, 'id', e.target.value)} placeholder="id" />
                </td>
                <td>
                  <input data-field={`cat-${i}-cls`} className={invalid.has(`cat-${i}-cls`) ? 'invalid' : ''}
                    value={r.cls} onChange={(e) => update(i, 'cls', e.target.value)} placeholder="类" />
                </td>
                {AXES.map((axis, c) => (
                  <td key={axis}>
                    <input data-field={`cat-${i}-vec-${c}`} className={invalid.has(`cat-${i}-vec-${c}`) ? 'invalid' : ''}
                      value={r[axis]} onChange={(e) => update(i, axis, e.target.value)} placeholder={axis} />
                  </td>
                ))}
                <td>
                  <button type="button" className="secondary small" onClick={() => removeRow(i)}>删</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">全部目录星范数（x²+y²+z²）必须相等；标识为 0–1e9 的唯一整数。</p>
    </section>
  );
}
