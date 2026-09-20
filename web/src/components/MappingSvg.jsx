import React, { useMemo } from 'react';

// 二分配对图：左侧有序观测，右侧目录星；边表示保留配对，剔除观测以红色标记
export default function MappingSvg({ catalog, obsClasses, mapping }) {
  const M = obsClasses.length;
  const stars = useMemo(
    () => [...catalog].sort((a, b) => a.id - b.id),
    [catalog]
  );
  const N = stars.length;
  const starIndex = useMemo(() => {
    const m = new Map();
    stars.forEach((s, i) => m.set(s.id, i));
    return m;
  }, [stars]);

  const W = 760;
  const leftX = 150;
  const rightX = 610;
  const topPad = 34;
  const obsRow = 36;
  const starRow = Math.max(13, Math.min(30, 560 / Math.max(1, N)));
  const H = Math.max(M * obsRow, N * starRow) + topPad + 46;

  const obsY = (i) => topPad + i * obsRow + obsRow / 2;
  const starY = (i) => topPad + i * starRow + starRow / 2;

  const edges = [];
  mapping.forEach((entry, i) => {
    if (!entry) return;
    const si = starIndex.get(entry.star_id);
    if (si == null) return;
    edges.push({ i, si, star: entry.star_id });
  });
  const usedStars = new Set(edges.map((e) => e.star));

  return (
    <div className="svg-wrap">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="配对关系图">
        <text x={leftX} y={18} textAnchor="middle" fill="#94a3b8" fontSize="13">观测（有序）</text>
        <text x={rightX} y={18} textAnchor="middle" fill="#94a3b8" fontSize="13">目录星（{N} 颗）</text>

        {edges.map((e) => (
          <line key={`e-${e.i}`}
            x1={leftX + 12} y1={obsY(e.i)} x2={rightX - 12} y2={starY(e.si)}
            stroke="#38bdf8" strokeWidth="1.8" opacity="0.85" />
        ))}

        {obsClasses.map((cls, i) => {
          const kept = mapping[i] != null;
          return (
            <g key={`o-${i}`}>
              <circle cx={leftX} cy={obsY(i)} r="11"
                fill={kept ? '#22c55e' : '#1e293b'}
                stroke={kept ? '#22c55e' : '#ef4444'} strokeWidth="2" />
              {!kept && (
                <text x={leftX} y={obsY(i) + 4} textAnchor="middle" fill="#ef4444"
                  fontSize="12" fontWeight="700">✕</text>
              )}
              <text x={leftX - 18} y={obsY(i) + 4} textAnchor="end" fill="#e2e8f0" fontSize="12">
                观测 {i} · 类 {cls}
              </text>
              {kept && (
                <text x={(leftX + rightX) / 2} y={(obsY(i) + starY(starIndex.get(mapping[i].star_id))) / 2 - 4}
                  textAnchor="middle" fill="#38bdf8" fontSize="11" className="mono">
                  → 星 {mapping[i].star_id}
                </text>
              )}
            </g>
          );
        })}

        {stars.map((s, i) => {
          const used = usedStars.has(s.id);
          return (
            <g key={`s-${s.id}`}>
              <circle cx={rightX} cy={starY(i)} r={used ? 9 : 5}
                fill={used ? '#22c55e' : '#64748b'} opacity={used ? 1 : 0.55} />
              {(used || N <= 40) && (
                <text x={rightX + 14} y={starY(i) + 4} textAnchor="start"
                  fill={used ? '#e2e8f0' : '#64748b'} fontSize="11" className="mono">
                  {s.id} · {s.cls}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
