import React, { useEffect, useMemo, useState } from 'react';
import CatalogEditor from './components/CatalogEditor.jsx';
import ObservationEditor from './components/ObservationEditor.jsx';
import ResultPanel from './components/ResultPanel.jsx';
import { generateExample } from './example.js';
import { errorKeys, pathToField, scrollToField } from './fieldPath.js';

const STORAGE_KEY = 'starfield-audit-draft-v1';
const INT_RE = /^-?\d+$/;

function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* 忽略损坏草稿 */
  }
  return null;
}

export default function App() {
  const [threshold, setThreshold] = useState('1');
  const [maxOutliers, setMaxOutliers] = useState('2');
  const [catalog, setCatalog] = useState([]);
  const [obsClasses, setObsClasses] = useState([]);
  const [dots, setDots] = useState({});
  const [errors, setErrors] = useState([]);
  const [result, setResult] = useState(null);
  const [snapshot, setSnapshot] = useState(null); // 提交识别时的输入快照，保证结论可复算
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  // 启动：恢复草稿，否则载入示例
  useEffect(() => {
    const draft = loadDraft();
    if (draft && Array.isArray(draft.catalog) && draft.catalog.length > 0) {
      setThreshold(draft.threshold ?? '1');
      setMaxOutliers(draft.maxOutliers ?? '2');
      setCatalog(draft.catalog);
      setObsClasses(draft.obsClasses ?? []);
      setDots(draft.dots ?? {});
    } else {
      loadExample();
    }
    setHydrated(true);
  }, []);

  // 草稿持久化（校验失败也不丢失）
  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ threshold, maxOutliers, catalog, obsClasses, dots })
      );
    } catch {
      /* 存储不可用时静默 */
    }
  }, [threshold, maxOutliers, catalog, obsClasses, dots, hydrated]);

  const invalid = useMemo(() => errorKeys(errors), [errors]);

  function loadExample() {
    const ex = generateExample();
    setThreshold(ex.threshold);
    setMaxOutliers(ex.maxOutliers);
    setCatalog(ex.catalog);
    setObsClasses(ex.obsClasses);
    setDots(ex.dots);
    setErrors([]);
    setResult(null);
  }

  function parseIntField(raw, path, errs, label) {
    const s = String(raw ?? '').trim();
    if (!INT_RE.test(s)) {
      errs.push({ path, message: `${label}必须是整数` });
      return null;
    }
    return parseInt(s, 10);
  }

  function buildPayload() {
    const errs = [];
    const t = parseIntField(threshold, 'threshold', errs, '阈值');
    const k = parseIntField(maxOutliers, 'max_outliers', errs, '离群名额');
    const cat = catalog.map((r, i) => {
      const id = parseIntField(r.id, `catalog[${i}].id`, errs, '目录标识');
      const cls = String(r.cls ?? '').trim();
      if (!cls) errs.push({ path: `catalog[${i}].cls`, message: '亮度类别不能为空' });
      const vec = ['x', 'y', 'z'].map((axis, c) =>
        parseIntField(r[axis], `catalog[${i}].vec[${c}]`, errs, '向量分量')
      );
      return { id, cls, vec };
    });
    const observations = obsClasses.map((cls, i) => {
      const c = String(cls ?? '').trim();
      if (!c) errs.push({ path: `observations[${i}].cls`, message: '亮度类别不能为空' });
      const d = {};
      for (let j = 0; j < obsClasses.length; j++) {
        if (j === i) continue;
        const key = i < j ? `${i}-${j}` : `${j}-${i}`;
        const raw = String(dots[key] ?? '').trim();
        if (!INT_RE.test(raw)) {
          errs.push({ path: `observations[${i}].dots.${j}`, message: '点积测量必须是整数' });
        } else {
          d[String(j)] = parseInt(raw, 10);
        }
      }
      return { cls: c, dots: d };
    });
    if (errs.length > 0) return { errors: errs };
    return {
      payload: { threshold: t, max_outliers: k, catalog: cat, observations },
    };
  }

  async function identify() {
    setErrors([]);
    setResult(null);
    const built = buildPayload();
    if (built.errors) {
      setErrors(built.errors);
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch('/api/identify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(built.payload),
      });
      const data = await resp.json();
      if (resp.status === 422) {
        setErrors(data.errors || [{ path: '', message: '输入校验失败' }]);
      } else if (!resp.ok) {
        setErrors([{ path: '', message: `服务异常（HTTP ${resp.status}）` }]);
      } else {
        setResult(data);
        setSnapshot(built.payload);
      }
    } catch (e) {
      setErrors([{ path: '', message: `无法连接识别服务：${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>星场身份识别审计台</h1>
      <p className="subtitle">
        星敏感器受粒子噪声干扰混入伪星后的整片星场身份结论：精确整数搜索，依次最大化保留观测数、
        最小化保留对残差和、取目录标识字典序最小解；多解时给出规范映射与另一份真实见证。
      </p>

      <section className="panel">
        <div className="controls">
          <div className="field">
            <label htmlFor="threshold">点积残差阈值</label>
            <input id="threshold" data-field="cfg-threshold"
              className={invalid.has('cfg-threshold') ? 'invalid' : ''}
              value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="maxOutliers">离群名额（0–3）</label>
            <input id="maxOutliers" data-field="cfg-outliers"
              className={invalid.has('cfg-outliers') ? 'invalid' : ''}
              value={maxOutliers} onChange={(e) => setMaxOutliers(e.target.value)} />
          </div>
          <button type="button" onClick={identify} disabled={loading}>
            {loading ? '识别中…' : '识别'}
          </button>
          <button type="button" className="secondary" onClick={loadExample}>载入示例</button>
        </div>
      </section>

      {errors.length > 0 && (
        <section className="panel">
          <div className="banner invalid">输入校验未通过（{errors.length} 处），草稿已保留，点击条目定位原因：</div>
          <ul className="error-list">
            {errors.map((e, i) => (
              <li key={i} onClick={() => scrollToField(pathToField(e.path))}>
                <code className="mono">{e.path || '(请求)'}</code>
                {e.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="editors">
        <CatalogEditor rows={catalog} setRows={setCatalog} invalid={invalid} />
        <ObservationEditor
          obsClasses={obsClasses} setObsClasses={setObsClasses}
          dots={dots} setDots={setDots} invalid={invalid}
        />
      </div>

      <ResultPanel result={result} snapshot={snapshot} />
    </div>
  );
}
