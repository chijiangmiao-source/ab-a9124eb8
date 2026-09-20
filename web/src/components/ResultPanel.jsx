import React, { useState } from 'react';
import MappingSvg from './MappingSvg.jsx';
import ResidualMatrix from './ResidualMatrix.jsx';

function SequenceChips({ sequence, title }) {
  return (
    <div>
      <div className="hint">{title}</div>
      <div className="chips">
        {sequence.map((sid, i) => (
          <span key={i} className={`chip ${sid === -1 ? 'drop' : 'keep'}`}>
            观测 {i} → {sid === -1 ? '剔除' : <b>星 {sid}</b>}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ResultPanel({ result, snapshot }) {
  const [view, setView] = useState('canonical');

  if (!result) return null;

  if (result.status === 'infeasible') {
    return (
      <section className="panel">
        <h2>识别结论</h2>
        <div className="banner infeasible">
          不相容：{result.message}
          <span className="hint" style={{ display: 'block', marginTop: 6, fontWeight: 400 }}>
            搜索节点 {result.nodes}，耗时 {result.elapsed_ms} ms。可尝试调大阈值或离群名额后重新识别。
          </span>
        </div>
      </section>
    );
  }

  if (result.status !== 'ok' || !snapshot) return null;

  const obsClasses = snapshot.observations.map((o) => o.cls);
  const isWitness = view === 'witness' && result.multiple;
  const mapping = isWitness ? result.witness : result.canonical;
  const pairs = isWitness ? result.witness_pair_residuals : result.pair_residuals;
  const retained = mapping
    .map((m, i) => (m ? i : null))
    .filter((i) => i != null);
  const catalog = snapshot.catalog;

  return (
    <section className="panel">
      <h2>识别结论</h2>
      <div className="banner ok">
        识别完成：保留 {result.retained_count} / {obsClasses.length} 个观测，
        剔除 {result.drops.length} 个{result.drops.length > 0 && `（观测 ${result.drops.join('、')}）`}，
        残差和 {result.residual_sum}。
        {result.multiple
          ? ' 存在多份前两级同优映射，以下给出规范映射与另一份真实见证。'
          : ' 映射在前两级目标下唯一。'}
      </div>

      <div className="stats">
        <span><b>{result.retained_count}</b>保留观测</span>
        <span><b>{result.drops.length}</b>已用离群名额（上限 {result.max_outliers}）</span>
        <span><b>{result.residual_sum}</b>残差和（阈值 {result.threshold}）</span>
        <span><b>{result.multiple ? '是' : '否'}</b>多解</span>
        <span><b>{result.nodes}</b>搜索节点</span>
        <span><b>{result.elapsed_ms}</b>毫秒</span>
      </div>

      <SequenceChips sequence={result.sequence} title="规范映射（字典序最小解，-1 为剔除）" />
      {result.multiple && (
        <SequenceChips sequence={result.witness_sequence} title="另一份同优见证映射" />
      )}

      {result.multiple && (
        <div className="view-toggle">
          <button type="button" className={!isWitness ? 'active' : 'secondary'} onClick={() => setView('canonical')}>
            规范映射
          </button>
          <button type="button" className={isWitness ? 'active' : 'secondary'} onClick={() => setView('witness')}>
            见证映射
          </button>
        </div>
      )}

      <h2 style={{ marginTop: 14 }}>配对关系（{isWitness ? '见证' : '规范'}映射）</h2>
      <MappingSvg catalog={catalog} obsClasses={obsClasses} mapping={mapping} />
      <div className="legend">
        <span className="l-keep">保留 / 已配对</span>
        <span className="l-drop">剔除（伪星）</span>
        <span className="l-free">未占用目录星</span>
        <span className="l-edge">配对边</span>
      </div>

      <h2 style={{ marginTop: 14 }}>保留对残差</h2>
      <ResidualMatrix pairResiduals={pairs} retained={retained} threshold={result.threshold} />
    </section>
  );
}
