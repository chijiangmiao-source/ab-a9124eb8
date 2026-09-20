// 服务端错误路径 → 前端字段定位键
export function pathToField(path) {
  if (!path) return null;
  if (path === 'threshold') return 'cfg-threshold';
  if (path === 'max_outliers') return 'cfg-outliers';
  if (path === 'catalog') return 'cat-table';
  if (path === 'observations') return 'obs-table';
  let m = path.match(/^catalog\[(\d+)\]$/);
  if (m) return `cat-row-${m[1]}`;
  m = path.match(/^catalog\[(\d+)\]\.id$/);
  if (m) return `cat-${m[1]}-id`;
  m = path.match(/^catalog\[(\d+)\]\.cls$/);
  if (m) return `cat-${m[1]}-cls`;
  m = path.match(/^catalog\[(\d+)\]\.vec(?:\[(\d+)\])?$/);
  if (m) return `cat-${m[1]}-vec-${m[2] != null ? m[2] : '0'}`;
  m = path.match(/^observations\[(\d+)\]$/);
  if (m) return `obs-row-${m[1]}`;
  m = path.match(/^observations\[(\d+)\]\.cls$/);
  if (m) return `obs-${m[1]}-cls`;
  m = path.match(/^observations\[(\d+)\]\.dots(?:\.(.+))?$/);
  if (m) {
    const key = m[2];
    if (key != null && /^\d+$/.test(key)) {
      const a = Number(m[1]);
      const b = Number(key);
      return `dot-${Math.min(a, b)}-${Math.max(a, b)}`;
    }
    return `obs-${m[1]}-dots`;
  }
  return null;
}

export function errorKeys(errors) {
  const set = new Set();
  for (const e of errors || []) {
    const k = pathToField(e.path);
    if (k) set.add(k);
  }
  return set;
}

export function scrollToField(fieldKey) {
  if (!fieldKey) return;
  const el = document.querySelector(`[data-field="${fieldKey}"]`);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.remove('flash');
  // 强制重排以重启动画
  void el.offsetWidth;
  el.classList.add('flash');
  const input = el.tagName === 'INPUT' ? el : el.querySelector('input');
  if (input) input.focus({ preventScroll: true });
  setTimeout(() => el.classList.remove('flash'), 1700);
}
