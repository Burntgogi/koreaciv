// DOM 짓기 — 자료에서 온 글은 모두 텍스트 노드로 넣는다 (innerHTML 에 자료를 잇지 않는다).

// h('div.cls#id', {attr}, ...children). children: 노드 | 문자열(텍스트) | null | 배열
export function h(sel, attrs, ...kids) {
  const m = sel.match(/^([a-z0-9]+)?((?:[.#][\w-]+)*)$/i);
  const el = document.createElement((m && m[1]) || 'div');
  if (m && m[2]) for (const p of m[2].match(/[.#][\w-]+/g)) p[0] === '.' ? el.classList.add(p.slice(1)) : (el.id = p.slice(1));
  if (attrs && (attrs instanceof Node || typeof attrs !== 'object' || Array.isArray(attrs))) { kids.unshift(attrs); attrs = null; }
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className += (el.className ? ' ' : '') + v;
    else if (k === 'text') el.textContent = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  add(el, kids);
  return el;
}
export function add(el, kids) {
  for (const k of [].concat(kids)) {
    if (k == null || k === false) continue;
    if (Array.isArray(k)) add(el, k);
    else el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}
export function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }

// SVG 짓기
const NS = 'http://www.w3.org/2000/svg';
export function s(tag, attrs, ...kids) {
  const el = document.createElementNS(NS, tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) el.setAttribute(k, v);
  for (const k of [].concat(...kids)) if (k != null) el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return el;
}

// 값 + 작은 단위: num('38.8','조') -> <span class="num">38.8<small>조</small></span>. parts 가 null 이면 '자료 없음'
export function numEl(parts, cls = '') {
  if (!parts) return h('span.na', '자료 없음');
  return h('span.num' + (cls ? '.' + cls : ''), parts[0], parts[1] ? h('small', parts[1]) : null);
}
export const na = () => h('span.na', '자료 없음');

// http(s) 주소만 링크로
export function safeLink(url, text) {
  if (typeof url === 'string' && /^https?:\/\//i.test(url)) return h('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, text || url);
  return document.createTextNode(text || '');
}

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
