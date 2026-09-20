import { useMemo, useState } from "react";
import type { CatalogStar, Mapping, SolveResult } from "../types";

interface Props {
  catalog: CatalogStar[];
  result: SolveResult;
}

const CLASS_COLORS = [
  "#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185",
  "#22d3ee", "#f472b6", "#a3e635", "#fb923c",
];

function classColor(mag: number): string {
  return CLASS_COLORS[((mag % 9) + 9) % 9];
}

interface CatPos {
  x: number;
  y: number;
  star: CatalogStar;
  col: number;
}

interface ObsPos {
  x: number;
  y: number;
  index: number;
}

/**
 * Whole-field audit picture:
 *   left  - catalog stars grouped into columns by brightness class,
 *   right - ordered observations in a single column,
 *   solid lines  = canonical injection pairs,
 *   dashed amber = the alternative witness injection (when ambiguous),
 *   right-side arcs = residual of each kept/kept pair (green -> red),
 *   red slashed nodes = rejected pseudostars.
 */
export default function StarFieldSvg({ catalog, result }: Props) {
  const [showWitness, setShowWitness] = useState(true);
  const [showResiduals, setShowResiduals] = useState(true);
  const [hover, setHover] = useState<string | null>(null);

  const layout = useMemo(() => {
    const groups = new Map<number, CatalogStar[]>();
    for (const s of catalog) {
      if (!groups.has(s.magnitude)) groups.set(s.magnitude, []);
      groups.get(s.magnitude)!.push(s);
    }
    const classes = [...groups.keys()].sort((a, b) => a - b);
    const maxRows = Math.max(...[...groups.values()].map((g) => g.length));
    const rowH = 26;
    const topPad = 56;
    const height = topPad * 2 + Math.max(maxRows, result.n_observations) * rowH;
    const colX = 130;
    const colGap = 76;
    const cat: CatPos[] = [];
    classes.forEach((mag, col) => {
      const g = groups.get(mag)!;
      const y0 = topPad + ((Math.max(maxRows, result.n_observations) - g.length) * rowH) / 2;
      g.forEach((star, row) => {
        cat.push({ x: colX + col * colGap, y: y0 + row * rowH, star, col });
      });
    });
    const obsX = colX + Math.max(classes.length - 1, 0) * colGap + 170;
    const obsY0 =
      topPad + ((Math.max(maxRows, result.n_observations) - result.n_observations) * rowH) / 2;
    const obs: ObsPos[] = Array.from({ length: result.n_observations }, (_, i) => ({
      x: obsX,
      y: obsY0 + i * rowH,
      index: i,
    }));
    const width = obsX + 210;
    return { cat, obs, height, width, classes, rowH, topPad };
  }, [catalog, result.n_observations]);

  const catById = useMemo(() => {
    const m = new Map<string, CatPos>();
    for (const p of layout.cat) m.set(p.star.id, p);
    return m;
  }, [layout]);

  const canonical: Mapping | null = result.canonical;
  const witness: Mapping | null = result.witness;
  const threshold = Math.max(result.threshold, 1);

  const obsByIdx = new Map(layout.obs.map((o) => [o.index, o]));
  const rejectedSet = new Set(canonical?.rejected ?? []);

  const pairPath = (obsIndex: number, catalogId: string) => {
    const o = obsByIdx.get(obsIndex)!;
    const c = catById.get(catalogId);
    if (!c) return null;
    const mx = (o.x + c.x) / 2;
    return `M ${c.x} ${c.y} C ${mx} ${c.y}, ${mx} ${o.y}, ${o.x} ${o.y}`;
  };

  const residualColor = (r: number) => {
    const t = Math.min(1, r / threshold);
    // green (34,197,94) -> red (239,68,68)
    const rr = Math.round(34 + t * (239 - 34));
    const gg = Math.round(197 + t * (68 - 197));
    const bb = Math.round(94 + t * (68 - 94));
    return `rgb(${rr},${gg},${bb})`;
  };

  const hoverPair = hover ? canonical?.residual_pairs.find(
    (p) => hover === `res-${p.i}-${p.j}`,
  ) : null;

  return (
    <div className="svg-wrap">
      <div className="svg-controls">
        <label>
          <input
            type="checkbox"
            checked={showWitness && result.multiple}
            disabled={!result.multiple}
            onChange={(e) => setShowWitness(e.target.checked)}
          />
          叠加见证映射（虚线）
        </label>
        <label>
          <input
            type="checkbox"
            checked={showResiduals}
            onChange={(e) => setShowResiduals(e.target.checked)}
          />
          保留对残差弧线
        </label>
        <span className="svg-hint">悬停节点/弧线查看测量明细</span>
      </div>

      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        width="100%"
        role="img"
        aria-label="星场身份关系图"
      >
        {/* headers */}
        <text x={layout.cat[0]?.x ?? 40} y="24" className="svg-title">
          目录星（按亮度类别分列）
        </text>
        <text x={layout.obs[0]?.x ?? 200} y="24" className="svg-title" textAnchor="middle">
          有序观测
        </text>

        {/* residual arcs (drawn first, behind pair lines) */}
        {showResiduals &&
          canonical?.residual_pairs.map((p) => {
            const a = obsByIdx.get(p.i)!;
            const b = obsByIdx.get(p.j)!;
            const my = (a.y + b.y) / 2;
            const bulge = 40 + Math.min(90, Math.abs(b.y - a.y) * 0.15);
            const key = `res-${p.i}-${p.j}`;
            const active = hover === key;
            return (
              <g key={key}>
                <path
                  d={`M ${a.x} ${a.y} Q ${a.x + bulge} ${my}, ${b.x} ${b.y}`}
                  fill="none"
                  stroke={residualColor(p.residual)}
                  strokeWidth={active ? 4 : 2}
                  strokeOpacity={active ? 1 : 0.55}
                  onMouseEnter={() => setHover(key)}
                  onMouseLeave={() => setHover(null)}
                />
                <text
                  x={a.x + bulge + 4}
                  y={my + 3}
                  fontSize="9"
                  fill={residualColor(p.residual)}
                  className="svg-reslabel"
                >
                  {p.residual}
                </text>
              </g>
            );
          })}

        {/* witness pairs (dashed amber, under canonical) */}
        {result.multiple && showWitness &&
          witness?.assignments.map((asg) => {
            const d = pairPath(asg.observation_index, asg.catalog_id);
            if (!d) return null;
            const key = `w-${asg.observation_index}`;
            return (
              <path
                key={key}
                d={d}
                fill="none"
                stroke="#f59e0b"
                strokeWidth={hover === key ? 3 : 1.8}
                strokeDasharray="6 4"
                strokeOpacity={hover === key ? 1 : 0.75}
                onMouseEnter={() => setHover(key)}
                onMouseLeave={() => setHover(null)}
              />
            );
          })}

        {/* canonical pairs */}
        {canonical?.assignments.map((asg) => {
          const d = pairPath(asg.observation_index, asg.catalog_id);
          if (!d) return null;
          const key = `c-${asg.observation_index}`;
          const dimmed = hover !== null && hover !== key && !hover.startsWith("res-");
          return (
            <path
              key={key}
              d={d}
              fill="none"
              stroke="#22c55e"
              strokeWidth={hover === key ? 3.2 : 2}
              strokeOpacity={dimmed ? 0.2 : 0.9}
              onMouseEnter={() => setHover(key)}
              onMouseLeave={() => setHover(null)}
            />
          );
        })}

        {/* catalog nodes */}
        {layout.cat.map((c) => {
          const usedByCanonical = canonical?.assignments.some(
            (a) => a.catalog_id === c.star.id,
          );
          const usedByWitness = witness?.assignments.some(
            (a) => a.catalog_id === c.star.id,
          );
          const key = `cat-${c.star.id}`;
          return (
            <g
              key={key}
              transform={`translate(${c.x},${c.y})`}
              onMouseEnter={() => setHover(key)}
              onMouseLeave={() => setHover(null)}
            >
              {usedByWitness && !usedByCanonical && (
                <circle r="9" fill="none" stroke="#f59e0b" strokeWidth="1.6"
                  strokeDasharray="3 2" />
              )}
              <circle
                r="6.5"
                fill={usedByCanonical ? classColor(c.star.magnitude) : "#1e293b"}
                stroke={usedByCanonical ? "#22c55e" : classColor(c.star.magnitude)}
                strokeWidth={usedByCanonical ? 2.4 : 1.2}
                fillOpacity={usedByCanonical ? 1 : 0.55}
              />
              <text x="-10" y="3.5" textAnchor="end" fontSize="9" className="svg-label">
                {c.star.id}
              </text>
            </g>
          );
        })}

        {/* observation nodes */}
        {layout.obs.map((o) => {
          const rejected = rejectedSet.has(o.index);
          const asg = canonical?.assignments.find((a) => a.observation_index === o.index);
          const key = `obs-${o.index}`;
          return (
            <g
              key={key}
              transform={`translate(${o.x},${o.y})`}
              onMouseEnter={() => setHover(key)}
              onMouseLeave={() => setHover(null)}
            >
              <circle
                r="7.5"
                fill={rejected ? "#450a0a" : asg ? "#052e16" : "#1e293b"}
                stroke={rejected ? "#ef4444" : asg ? "#22c55e" : "#64748b"}
                strokeWidth="2"
              />
              <text y="3.6" textAnchor="middle" fontSize="9.5"
                fill={rejected ? "#fca5a5" : "#e2e8f0"}>
                {o.index}
              </text>
              {rejected && (
                <g stroke="#ef4444" strokeWidth="2">
                  <line x1="-10" y1="-10" x2="10" y2="10" />
                  <line x1="10" y1="-10" x2="-10" y2="10" />
                </g>
              )}
              <text x="14" y="3.5" fontSize="9" className="svg-label">
                {rejected ? "剔除（伪星）" : asg?.catalog_id ?? "未保留"}
              </text>
            </g>
          );
        })}

        {/* tooltip */}
        {hoverPair && (
          <g transform={`translate(${layout.obs[0].x + 52}, ${
            (obsByIdx.get(hoverPair.i)!.y + obsByIdx.get(hoverPair.j)!.y) / 2
          })`}>
            <rect
              x="0" y="-30" width="150" height="46" rx="6"
              fill="#0f172a" stroke={residualColor(hoverPair.residual)}
            />
            <text x="8" y="-13" fontSize="10" fill="#e2e8f0">
              obs{hoverPair.i}↔obs{hoverPair.j}：|{hoverPair.actual}−{hoverPair.measured}|
            </text>
            <text x="8" y="1" fontSize="10" fill={residualColor(hoverPair.residual)}>
              残差 {hoverPair.residual}（阈值 {result.threshold}）
            </text>
          </g>
        )}
      </svg>

      <div className="svg-legend">
        <span><i className="lg-line green" /> 规范配对</span>
        {result.multiple && <span><i className="lg-line amber" /> 见证配对</span>}
        <span><i className="lg-dot" /> 保留观测</span>
        <span><i className="lg-cross" /> 剔除伪星</span>
        <span>残差：<b style={{ color: "#22c55e" }}>0</b> → <b style={{ color: "#ef4444" }}>阈值</b></span>
        <span className="svg-classes">
          亮度类别：
          {layout.classes.map((m) => (
            <i key={m} className="lg-class" style={{ background: classColor(m) }}>
              {m}
            </i>
          ))}
        </span>
      </div>
    </div>
  );
}
