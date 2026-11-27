// 겹쳐 뜨는 것(모달·서랍)의 공통 규칙: 초점 가두기, Esc 로 맨 위 것부터 닫기, 닫으면 초점을 열기 전 자리로.

const stack = [];
// 사파리는 단추를 눌러도 초점을 주지 않는다 -> 방금 누른 조작 요소를 기억해 두었다가 닫을 때 그리로 돌아간다
let lastPress = null, lastPressAt = 0;
document.addEventListener('pointerdown', (e) => { lastPress = e.target.closest ? e.target.closest('button, a[href], [tabindex]') : null; lastPressAt = performance.now(); }, true);
// 초점이 맨 위 모달 밖으로 나가면(브라우저마다 Tab 이 서는 요소가 달라 생긴다) 도로 데려온다
document.addEventListener('focusin', (e) => {
  const m = stack[stack.length - 1];
  if (!m || m.opts.trap === false || m.el.contains(e.target)) return;
  const f = m.el.querySelector(FOCUSABLE) || m.el;
  f.focus({ preventScroll: true });
});
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, summary, [tabindex]:not([tabindex="-1"])';

// el: 대화 상자 노드. opts: {onClose, initial: 처음 초점 둘 노드, trap: true}
export function openModal(el, opts = {}) {
  if (stack.some((m) => m.el === el)) return;
  let prev = document.activeElement;
  if ((!prev || prev === document.body) && lastPress && lastPress.isConnected && performance.now() - lastPressAt < 1500 && !el.contains(lastPress)) prev = lastPress;
  const m = { el, opts, prev };
  el.hidden = false;
  if (!el.hasAttribute('role')) el.setAttribute('role', 'dialog');
  if (opts.trap !== false) el.setAttribute('aria-modal', 'true');
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
  m.key = (e) => {
    if (e.key !== 'Tab' || opts.trap === false) return;
    const f = [...el.querySelectorAll(FOCUSABLE)].filter((x) => x.offsetParent !== null || x === document.activeElement);
    if (!f.length) { e.preventDefault(); el.focus(); return; }
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === el)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  el.addEventListener('keydown', m.key);
  stack.push(m);
  const target = opts.initial || el.querySelector('[autofocus]') || el.querySelector(FOCUSABLE) || el;
  target.focus({ preventScroll: true });
}

export function closeModal(el, restore = true) {
  const k = stack.findIndex((m) => m.el === el);
  if (k < 0) { el.hidden = true; return; }
  const [m] = stack.splice(k, 1);
  el.removeEventListener('keydown', m.key);
  el.hidden = true;
  if (m.opts.onClose) m.opts.onClose();
  if (restore && m.prev && m.prev.isConnected && m.prev.focus) m.prev.focus({ preventScroll: true });
}

// 맨 위 것을 닫는다. 닫은 게 있으면 true
export function closeTop() {
  const m = stack[stack.length - 1];
  if (!m) return false;
  closeModal(m.el);
  return true;
}
export const modalOpen = () => stack.length > 0;
export const isOpen = (el) => stack.some((m) => m.el === el);
