import React from 'react';

// 保留观测两两之间的点积残差矩阵（颜色越红残差越大）
export default function ResidualMatrix({ pairResiduals, retained, threshold }) {
  const cell = 44;
  const pad = 56;
  const n = retained.length;
  if (n === 0) return null;
  const W = pad + n * cell + 8;
  const lookup = new Map();
  for (const p of pairResiduals) lookup.set(`${p.i}-${p.j}`, p);

  const color = (r) => {
    if (threshold <= 0) return r === 0 ? '#14532d' : '#7f1d1d';
    const t = Math.min(1, r / threshold);
    // 绿 → 黄 → 红
    const hue = 120 * (1 - t);
    return `hsl(${hue}, 70%, 30%)`;
  };

  return (
    <div className="svg-wrap">
      <svg width={W} height={W} viewBox={`0 0 ${W} ${W}`} role="img" aria-label="残差矩阵">
        <text x={W / 2} y={20} textAnchor="middle" fill="#94a3b8" fontSize="13">
          保留观测点积残差矩阵（阈值 {threshold}）
        </text>
        {retained.map((obs, r) =>
          retained.map((obs2, c) => {
            const x = pad + c * cell;
            const yy = pad + r * cell;
            if (r === c) {
              return (
                <g key={`${r}-${c}`}>
                  <rect x={x} y={yy} width={cell} height={cell} fill="#1e293b" stroke="#334155" />
                  <text x={x + cell / 2} y={yy + cell / 2 + 4} textAnchor="middle" fill="#64748b" fontSize="11">—</text>
                </g>
              );
            }
            const p = lookup.get(`${obs}-${obs2}`) || lookup.get(`${obs2}-${obs}`);
            if (!p) return null;
            return (
              <g key={`${r}-${c}`}>
                <rect x={x} y={yy} width={cell} height={cell} fill={color(p.residual)} stroke="#334155">
                  <title>{`观测 ${p.i} ↔ ${p.j}：实测 ${p.measured}，目录 ${p.catalog}，残差 ${p.residual}`}</title>
                </rect>
                <text x={x + cell / 2} y={yy + cell / 2 + 4} textAnchor="middle" fill="#e2e8f0" fontSize="12" className="mono">
                  {p.residual}
                </text>
                <title>{`观测 ${p.i} ↔ ${p.j}：实测 ${p.measured}，目录 ${p.catalog}，残差 ${p.residual}`}</title>
              </g>
            );
          })
        )}
        {retained.map((obs, k) => (
          <React.Fragment key={`lbl-${k}`}>
            <text x={pad - 8} y={pad + k * cell + cell / 2 + 4} textAnchor="end" fill="#94a3b8" fontSize="11">
              观测 {obs}
            </text>
            <text x={pad + k * cell + cell / 2} y={pad - 8} textAnchor="middle" fill="#94a3b8" fontSize="11">
              {obs}
            </text>
          </React.Fragment>
        ))}
      </svg>
    </div>
  );
}
