import React from 'react';

export default function ObservationEditor({ obsClasses, setObsClasses, dots, setDots, invalid }) {
  const M = obsClasses.length;

  const setClass = (i, value) => {
    setObsClasses(obsClasses.map((c, idx) => (idx === i ? value : c)));
  };

  const setDot = (i, j, value) => {
    const key = i < j ? `${i}-${j}` : `${j}-${i}`;
    setDots({ ...dots, [key]: value });
  };

  const addObs = () => setObsClasses([...obsClasses, 'A']);

  const removeObs = (idx) => {
    const mapping = {};
    obsClasses.forEach((_, old) => {
      if (old < idx) mapping[old] = old;
      else if (old > idx) mapping[old] = old - 1;
    });
    const next = {};
    for (const [key, value] of Object.entries(dots)) {
      const [a, b] = key.split('-').map(Number);
      if (mapping[a] == null || mapping[b] == null) continue;
      const na = mapping[a];
      const nb = mapping[b];
      next[na < nb ? `${na}-${nb}` : `${nb}-${na}`] = value;
    }
    setDots(next);
    setObsClasses(obsClasses.filter((_, i) => i !== idx));
  };

  return (
    <section className="panel">
      <div className="row-actions">
        <h2>有序观测（{M} 个，6–18）与点积测量矩阵</h2>
        <button type="button" className="secondary small" onClick={addObs}>+ 添加观测</button>
      </div>
      <div className="matrix-scroll" data-field="obs-table">
        <table className="grid">
          <thead>
            <tr>
              <th>观测</th>
              <th>亮度类别</th>
              {Array.from({ length: M }, (_, j) => <th key={j}>·{j}</th>)}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {obsClasses.map((cls, i) => (
              <tr key={i} data-field={`obs-row-${i}`} className={invalid.has(`obs-row-${i}`) ? 'invalid-row' : ''}>
                <td>观测 {i}</td>
                <td>
                  <input data-field={`obs-${i}-cls`} className={invalid.has(`obs-${i}-cls`) ? 'invalid' : ''}
                    value={cls} onChange={(e) => setClass(i, e.target.value)} />
                </td>
                {Array.from({ length: M }, (_, j) => {
                  if (j === i) return <td key={j} className="diag">—</td>;
                  if (j > i) {
                    const key = `${i}-${j}`;
                    return (
                      <td key={j} className={invalid.has(`dot-${key}`) ? 'invalid-cell' : ''}>
                        <input data-field={`dot-${key}`} className={invalid.has(`dot-${key}`) ? 'invalid' : ''}
                          value={dots[key] ?? ''} onChange={(e) => setDot(i, j, e.target.value)} />
                      </td>
                    );
                  }
                  const key = `${j}-${i}`;
                  return <td key={j} className="readonly mono">{dots[key] ?? ''}</td>;
                })}
                <td>
                  <button type="button" className="secondary small" onClick={() => removeObs(i)}>删</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">上三角填写整数点积测量，下三角自动镜像；删除观测会同步重排矩阵。</p>
    </section>
  );
}
