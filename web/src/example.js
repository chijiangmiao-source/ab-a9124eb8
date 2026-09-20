// 示例实例生成：等范数整数向量族 + 含噪点积测量 + 伪星离群
function norm14Family() {
  const perms = [
    [1, 2, 3], [1, 3, 2], [2, 1, 3],
    [2, 3, 1], [3, 1, 2], [3, 2, 1],
  ];
  const signs = [];
  for (const a of [1, -1]) for (const b of [1, -1]) for (const c of [1, -1]) signs.push([a, b, c]);
  const out = [];
  for (const p of perms) for (const s of signs) out.push([p[0] * s[0], p[1] * s[1], p[2] * s[2]]);
  return out; // 48 个范数平方均为 14 的整数向量
}

const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];

export function generateExample() {
  const family = norm14Family();
  const classes = ['A', 'B', 'C'];
  // 12 颗目录星，三类各 4 颗（≤ 20 上限）
  const catalog = family.slice(0, 12).map((v, i) => ({
    id: String(i),
    cls: classes[i % 3],
    x: String(v[0]),
    y: String(v[1]),
    z: String(v[2]),
  }));

  // 8 个有序观测，类别循环；真星取同类第 i 颗
  const M = 8;
  const obsClasses = Array.from({ length: M }, (_, i) => classes[i % 3]);
  const trueVec = obsClasses.map((cls, i) => {
    const inClass = catalog.map((c, idx) => ({ ...c, idx })).filter((c) => c.cls === cls);
    const pick = inClass[Math.floor(i / 3) % inClass.length];
    return family[pick.idx];
  });

  const threshold = 1;
  const outlier = 5; // 第 6 个观测是混入的伪星
  const dots = {};
  for (let i = 0; i < M; i++) {
    for (let j = i + 1; j < M; j++) {
      let v;
      if (i === outlier || j === outlier) {
        v = Math.floor(Math.random() * 61) - 30; // 垃圾测量
      } else {
        v = dot(trueVec[i], trueVec[j]) + Math.floor(Math.random() * 3) - 1; // ±1 噪声
      }
      dots[`${i}-${j}`] = String(v);
    }
  }

  return {
    threshold: String(threshold),
    maxOutliers: '2',
    catalog,
    obsClasses,
    dots,
  };
}

export const EMPTY_CATALOG_ROW = { id: '', cls: 'A', x: '', y: '', z: '' };
