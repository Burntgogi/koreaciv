// 출처와 이용조건 — ../data/sources.json 을 읽어 그린다. 글은 모두 텍스트 노드로 넣는다 (자료 글을 HTML 로 풀지 않는다).
// 두 판(koreaciv, 신여지도)이 함께 쓰는 쪽이라 어느 판의 모듈도 가져오지 않는다.
// 기록의 필드는 모두 f(기록, '이름') 으로 읽는다. 읽는 필드는 아래 FIELDS 에 적고, pipeline/validate.py 가 자료와 대조한다.

export const FIELDS = /*FIELDS*/{
  "top": {"required": ["sources"], "optional": ["profile", "summary", "cite", "restricted_rule", "restriction_kinds", "derived", "credits", "notes", "license_rule", "attribution"]},
  "profile": {"required": ["profile", "name", "statement", "excluded", "rule"], "optional": ["check_needed", "check_rule", "consent_kept"]},
  "excluded": {"required": ["id", "what", "why", "sources"], "optional": ["instead"]},
  "check_needed": {"required": ["key", "title"], "optional": ["publisher", "license_short", "kinds", "use_scope", "where"]},
  "consent_kept": {"required": ["key", "title", "why"], "optional": []},
  "notice": {"required": ["paragraphs", "rule"], "optional": ["from", "from_sha256", "from_url"]},
  "shipped": {"required": ["file", "path", "label"], "optional": []},
  "summary": {"required": ["text", "built", "population_vintage", "counts"], "optional": []},
  "counts": {"required": ["publishers"], "optional": []},
  "cite": {"required": ["text", "lines"], "optional": ["rule"]},
  "restriction_kind": {"required": ["code", "name", "text"], "optional": []},
  "attribution": {"required": ["rule"], "optional": []},
  "source": {"required": ["key", "title", "publisher", "group", "used_in", "vintage", "url", "license", "license_short", "license_url", "sha256", "file"],
             "optional": ["retrieved", "license_note", "license_from", "license_checked", "files", "bytes", "restriction", "restriction_kinds", "affects",
                          "use_scope", "manual", "basis", "alternative", "attribution_name", "derived_table", "note", "license_collected",
                          "required_notice", "commercial_use", "odbl", "shipped"]},
  "affects": {"required": ["base", "lenses"], "optional": []},
  "file": {"required": [], "optional": ["file", "title", "sha256", "bytes"]},
  "derived": {"required": ["key", "title", "rule", "inputs", "file", "used_in"], "optional": ["parts", "inputs_note", "checks", "version"]},
  "part": {"required": ["name", "rule"], "optional": []},
  "credit": {"required": ["key", "kind", "title", "publisher", "license", "used_in"],
             "optional": ["role", "url", "source_ref", "retrieved", "license_short", "license_url", "license_file", "copyright", "reserved_font_name",
                          "files", "note", "license_note", "names", "basis"]}
}/*END*/;

const DATA_URL = '../data/sources.json';
const f = (x, k) => (x && typeof x === 'object' && x[k] != null ? x[k] : undefined);
const arr = (v) => (Array.isArray(v) ? v : []);
const str = (v) => (v == null ? '' : String(v));
const UNKNOWN = '미확인';

// ---- 작은 DOM 도우미 ----
function h(tag, attrs, ...kids) {
  const [name, ...cls] = tag.split('.');
  const el = document.createElement(name);
  if (cls.length) el.className = cls.join(' ');
  if (attrs && (typeof attrs !== 'object' || attrs instanceof Node || Array.isArray(attrs))) { kids.unshift(attrs); attrs = null; }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = [el.className, v].filter(Boolean).join(' ');
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  add(el, kids);
  return el;
}
function add(el, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k == null || k === false || k === '') continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}
const safeURL = (u) => { const s = str(u).trim(); return /^https?:\/\//i.test(s) ? s : null; };
function ext(u, label) {
  const s = safeURL(u);
  return s ? h('a.ext', { href: s, rel: 'noopener noreferrer', target: '_blank' }, label || s) : (label || null);
}
const anchorId = (key) => 'src-' + str(key).replace(/[^\w-]/g, '_');
const fmtBytes = (b) => (typeof b === 'number' ? (b >= 1e6 ? (b / 1e6).toFixed(1) + ' MB' : b >= 1e3 ? Math.round(b / 1e3) + ' KB' : b + ' B') : '');
const day = (v) => str(v).slice(0, 10);
const isUnknown = (s) => !f(s, 'license') || f(s, 'license') === UNKNOWN;
const collator = new Intl.Collator('ko');

function slot(name) { return document.querySelector(`[data-slot="${name}"]`); }
function fill(name, build) {
  const el = slot(name);
  if (!el) return;
  try {
    const kids = build();
    el.replaceChildren();
    add(el, [kids]);
  } catch (e) {
    el.replaceChildren(h('p.warn', { role: 'alert' }, '이 부분을 그리지 못했습니다. 기록 원본(', h('a', { href: DATA_URL }, 'sources.json'), ')을 보십시오.'));
    console.warn('[sources]', name, e);
  }
}
function dl(rows) {
  const out = h('dl.meta');
  for (const [k, v] of rows) {
    if (v == null || v === '' || (Array.isArray(v) && !v.length)) continue;
    out.append(h('div', h('dt', k), h('dd', v)));
  }
  return out;
}

// ---- 이용조건 분류 이름 ----
let KINDS = new Map();
const kindBadges = (codes) => arr(codes).map((c) => h('span.badge', { 'data-kind': c }, (KINDS.get(c) || {}).name || c));

// ---- 요약 ----
function renderSummary(J) {
  const sm = f(J, 'summary');
  const S = arr(f(J, 'sources'));
  const unk = S.filter(isUnknown).length;
  const rs = S.filter((s) => arr(f(s, 'restriction_kinds')).length).length;
  const pubs = new Set(S.map((s) => f(s, 'publisher'))).size;
  const lines = arr(f(sm, 'text'));
  const c = f(sm, 'counts') || {};
  return [
    lines.length ? h('ul.summary', lines.map((t) => h('li', t))) : h('p', `자료 출처 ${S.length}건.`),
    h('div.facts', { role: 'list' },
      fact(S.length, '자료 출처', '#list'), fact(f(c, 'publishers') ?? pubs, '기관·출처', '#list'),
      fact(rs, '조건이 있는 자료', '#restricted'), fact(unk, '이용허락 미확인', '#unknown'),
      fact(arr(f(J, 'derived')).length, '계산한 층', '#derived'), fact(arr(f(J, 'credits')).filter((x) => f(x, 'kind') === 'font').length, '글꼴', '#credits')),
    f(sm, 'built') ? h('p.dim', `출처 목록 빌드 ${f(sm, 'built')} · 인구 기준 ${f(sm, 'population_vintage') || '–'}`) : null,
  ];
}
function fact(n, label, href) {
  return h('a.fact', { href, role: 'listitem' }, h('b', n == null ? '–' : String(n)), h('span', label));
}

// ---- 이 판 (공개판·전체판) ----
let CHECK = new Set();
function renderProfile(J) {
  const P = f(J, 'profile');
  if (!P) return [h('p.dim', '판 기록(profile)이 없는 옛 빌드입니다.')];
  const pub = f(P, 'profile') === 'public';
  const ex = arr(f(P, 'excluded'));
  const rows = ex.map((e) => h('tr',
    h('th', { scope: 'row' }, str(f(e, 'what'))),
    h('td', str(f(e, 'why'))),
    h('td', f(e, 'instead') ? str(f(e, 'instead')) : h('span.na', '대신하지 않음 — 그 자리는 비거나 "이 판에서는 제공하지 않음"')),
    h('td', arr(f(e, 'sources')).length ? h('small', `${arr(f(e, 'sources')).length}건 · `, arr(f(e, 'sources')).slice(0, 3).map((x, i) => [i ? ', ' : '', h('code', str(f(x, 'key')))]),
      arr(f(e, 'sources')).length > 3 ? ' …' : '') : '–')));
  const chk = arr(f(P, 'check_needed'));
  const ck = arr(f(P, 'consent_kept'));
  return [
    h('div.profile', { 'data-profile': pub ? 'public' : 'full' },
      h('p.pname', h('b', str(f(P, 'name'))), h('code', ` profile ${str(f(P, 'profile'))}`)),
      h('p', str(f(P, 'statement')))),
    h('h3', pub ? '이 판에서 뺀 것' : '공개판에서 빼는 것 (이 판에는 들어 있음)'),
    h('div.tablewrap', h('table.ptable', h('thead', h('tr', h('th', '무엇'), h('th', '까닭'), h('th', pub ? '대신' : '공개판에서 대신'), h('th', '출처'))), h('tbody', rows))),
    chk.length ? [h('h3', { id: 'check-needed' }, '변경금지 통계 — 원 통계를 바꾸지 않음'), h('p', str(f(P, 'check_rule'))),
      h('ul.check', chk.map((x) => h('li', h('a', { href: '#' + anchorId(f(x, 'key')) }, str(f(x, 'title'))), h('span.by', ' — ', str(f(x, 'publisher')), ' · ', str(f(x, 'license_short'))),
        arr(f(x, 'where')).length ? h('p', h('b', '이 사이트에서 영향 받는 곳: '), arr(f(x, 'where')).join('; ')) : null)))] : null,
    ck.length ? [h('h3', '허락 조건이 상업 이용에만 걸려 남긴 자료'), h('ul.check', ck.map((x) => h('li', h('a', { href: '#' + anchorId(f(x, 'key')) }, str(f(x, 'title'))), ' — ', str(f(x, 'why')))))] : null,
    h('p.dim', str(f(P, 'rule'))),
  ];
}

// ---- 지정 고지 (SRTM30+ 원문, ODbL) ----
function renderNotices(J) {
  const S = arr(f(J, 'sources'));
  const out = [];
  for (const s of S) {
    const n = f(s, 'required_notice');
    if (!n) continue;
    out.push(h('article.notice', { 'aria-labelledby': anchorId(f(s, 'key')) + '-n' },
      h('h3', { id: anchorId(f(s, 'key')) + '-n' }, h('a', { href: '#' + anchorId(f(s, 'key')) }, str(f(s, 'title')))),
      h('p.dim', str(f(n, 'rule'))),
      h('div.noticetext', { lang: 'en', tabindex: '0', 'aria-label': '고지 원문' }, arr(f(n, 'paragraphs')).map((t) => h('p', str(t).split('\n').map((ln, i) => [i ? h('br') : null, ln])))),
      h('p.dim', '원문: ', ext(f(n, 'from_url')) || '–', f(n, 'from') ? ` · 보관본 ${str(f(n, 'from'))}` : ''),
      f(s, 'commercial_use') ? h('p.warn', { role: 'note' }, str(f(s, 'commercial_use'))) : null));
  }
  for (const s of S) {
    if (!f(s, 'odbl')) continue;
    out.push(h('article.notice', h('h3', h('a', { href: '#' + anchorId(f(s, 'key')) }, str(f(s, 'title'))), ' — ODbL 1.0'), h('p', str(f(s, 'odbl')))));
  }
  return out.length ? out : [h('p.dim', '지정 고지가 있는 자료가 기록에 없습니다.')];
}

// 실린 자리 (감사 05): 조건부·미확인 자료가 사이트 JSON 의 어느 필드에 실렸는지
function shippedBlock(s) {
  const sh = arr(f(s, 'shipped'));
  if (!sh.length) return null;
  return h('p.shipped', h('b', '실린 곳: '), sh.map((r, i) => [i ? ' · ' : '', str(f(r, 'label')), h('small', ` (${str(f(r, 'file'))} ${str(f(r, 'path'))})`)]));
}

// ---- 출처 표기 ----
function renderCite(J) {
  const C = f(J, 'cite');
  const text = str(f(C, 'text'));
  const lines = arr(f(C, 'lines'));
  if (!text && !lines.length) return [h('p.dim', '출처 표기 글이 기록에 없습니다.')];
  const full = text + (lines.length ? '\n\n이용허락별 기관:\n' + lines.join('\n') : '');
  const pre = h('pre.cite', { tabindex: '0', 'aria-label': '출처 표기 글' }, full);
  const msg = h('span.copymsg', { role: 'status', 'aria-live': 'polite' });
  const btn = h('button.btn', { type: 'button', onclick: () => copy(full, pre, msg) }, '글 복사');
  return [h('div.citebox', pre, h('div.citebar', btn, msg)), f(C, 'rule') ? h('p.dim', f(C, 'rule')) : null];
}
async function copy(text, pre, msg) {
  let ok = false;
  try { if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); ok = true; } } catch (e) { ok = false; }
  if (!ok) {
    try {
      const r = document.createRange(); r.selectNodeContents(pre);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      ok = document.execCommand && document.execCommand('copy');
    } catch (e) { ok = false; }
  }
  msg.textContent = ok ? '복사했습니다.' : '복사하지 못했습니다. 글을 골라 직접 복사하십시오.';
}

// ---- 조건이 있는 자료 ----
// 같은 기관·이용허락·메모·분류이고 제목이 연월만 다른 기록(월별 파일)은 한 장으로 묶는다 (NOTICE.md 와 같은 규칙)
function restrictedGroups(S) {
  const m = new Map();
  for (const s of S) {
    const kinds = arr(f(s, 'restriction_kinds'));
    if (!kinds.length) continue;
    const k = JSON.stringify([f(s, 'publisher'), f(s, 'license'), f(s, 'license_note'), kinds, f(s, 'restriction'), str(f(s, 'title')).replace(/\d{4}-\d{2}/g, '')]);
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(s);
  }
  return [...m.values()];
}
function whereUsed(g) {
  const s = g[0];
  const lenses = [];
  for (const x of g) for (const n of arr(f(f(x, 'affects'), 'lenses'))) if (!lenses.includes(n)) lenses.push(n);
  const base = g.some((x) => f(f(x, 'affects'), 'base'));
  return [
    f(s, 'used_in') ? h('p', f(s, 'used_in')) : null,
    lenses.length ? h('p', h('b', '렌즈: '), lenses.join(', ')) : null,
    base ? h('p', h('b', '지도 바탕: '), '두 판의 지도 바탕에 늘 그려집니다 (렌즈를 끄더라도).') : null,
    f(s, 'use_scope') ? h('p.scope', h('b', '쓴 범위: '), f(s, 'use_scope')) : null,
    g.map((x) => shippedBlock(x)).find(Boolean) || null,
  ];
}
function renderRestricted(J) {
  const S = arr(f(J, 'sources'));
  const groups = restrictedGroups(S);
  const counts = new Map();
  for (const s of S) for (const c of arr(f(s, 'restriction_kinds'))) counts.set(c, (counts.get(c) || 0) + 1);
  const legend = h('ul.kinds', [...KINDS.values()].map((k) => h('li', h('span.badge', { 'data-kind': k.code }, k.name), ` ${counts.get(k.code) || 0}건 — `, k.text)));
  const cards = groups.map((g) => {
    const s = g[0];
    const many = g.length > 1;
    return h('article.rcard', { 'aria-labelledby': anchorId(f(s, 'key')) + '-r' },
      h('header',
        h('h3', { id: anchorId(f(s, 'key')) + '-r' }, h('a', { href: '#' + anchorId(f(s, 'key')) }, str(f(s, 'title'))), many ? h('small', ` 외 ${g.length - 1}건`) : null),
        h('p.by', str(f(s, 'publisher')), ' · ', kindBadges(f(s, 'restriction_kinds')))),
      h('div.cols',
        h('div',
          h('h4', '원문의 조건'),
          h('blockquote', str(f(s, 'license')) || UNKNOWN),
          f(s, 'license_note') ? h('p.note', f(s, 'license_note')) : null,
          f(s, 'restriction') ? h('p.warn', { role: 'note' }, h('b', 'API 이용약관: '), f(s, 'restriction')) : null,
          safeURL(f(s, 'license_url')) ? h('p.dim', ext(f(s, 'license_url'), '이용허락 원문 쪽')) : null),
        h('div',
          h('h4', '이 사이트에서 쓰는 곳'),
          whereUsed(g),
          many ? h('p.dim', '묶은 기록: ', g.map((x, i) => [i ? ', ' : '', h('a', { href: '#' + anchorId(f(x, 'key')) }, str(f(x, 'key')))])) : null)));
  });
  return [
    f(J, 'restricted_rule') ? h('details.rule', h('summary', '분류하는 규칙'), h('p', f(J, 'restricted_rule'))) : null,
    legend,
    cards.length ? h('div.rcards', cards) : h('p.dim', '분류에 든 자료가 없습니다.'),
  ];
}

// ---- 미확인 ----
function renderUnknown(J) {
  const U = arr(f(J, 'sources')).filter(isUnknown);
  if (!U.length) return [h('p', '이용허락을 확인하지 못한 자료가 없습니다.')];
  return [
    h('p', h('b', `${U.length}건`), ' — 기록에는 "미확인"으로 둡니다. 이 자료를 다시 쓰려면 제공기관에 먼저 확인해야 합니다.'),
    h('ul.unknown', U.map((s) => h('li',
      h('a', { href: '#' + anchorId(f(s, 'key')) }, str(f(s, 'title'))),
      h('span.by', ' — ', str(f(s, 'publisher'))),
      f(s, 'license_note') ? h('span.note', ' · ', f(s, 'license_note')) : null,
      f(s, 'license_collected') ? h('span.note', ` · 수집 기록의 값: ${f(s, 'license_collected')}`) : null,
      shippedBlock(s)))),
  ];
}

// ---- 출처 목록 ----
function licenseCell(s) {
  const short = f(s, 'license_short') || (isUnknown(s) ? '이용허락 미확인' : str(f(s, 'license')).slice(0, 28));
  const full = str(f(s, 'license')) || UNKNOWN;
  const lk = safeURL(f(s, 'license_url'));
  return h('span', { class: isUnknown(s) ? 'na' : null },
    lk ? h('a.ext', { href: lk, rel: 'noopener noreferrer', target: '_blank' }, short) : short,
    full !== short ? h('small.full', full) : null,
    f(s, 'license_checked') ? h('small', `확인 ${f(s, 'license_checked')}${f(s, 'license_from') ? ' · ' + f(s, 'license_from') : ''}`) : null);
}
function filesBlock(s) {
  const fl = arr(f(s, 'files'));
  const sha = f(s, 'sha256');
  if (!sha && !fl.length && !f(s, 'file')) return null;
  const sum = fl.length ? `파일 ${fl.length}개 · sha256` : 'sha256 · 파일';
  return h('details.files', h('summary', sum),
    f(s, 'file') ? h('p', h('span.k', '파일 '), h('code', str(f(s, 'file'))), f(s, 'bytes') ? ` (${fmtBytes(f(s, 'bytes'))})` : '') : null,
    sha ? h('p', h('span.k', 'sha256 '), h('code.sha', str(sha))) : null,
    fl.length ? h('ol.fl', fl.map((x) => h('li', h('code', str(f(x, 'file') || f(x, 'title') || '')), f(x, 'bytes') ? ` (${fmtBytes(f(x, 'bytes'))})` : '', f(x, 'sha256') ? h('code.sha', str(f(x, 'sha256'))) : null))) : null,
    f(s, 'manual') ? h('p.note', '수작업 표: ', str(f(s, 'basis') || '')) : null,
    f(s, 'derived_table') ? h('p.note', `정리표 ${f(s, 'derived_table')}`) : null);
}
// KOSIS 기록의 기준 시점은 'Y,2024,@' 꼴(수록 주기 기호, 연도…, @)로 적혀 있다 — 연도만 보이고 원래 값은 title 에 둔다
function vintage(v) {
  const s = str(v).trim();
  if (!s) return h('span.na', '자료 없음');
  const m = /^[A-Z],((?:\d{4},?)+),@$/.exec(s);
  return m ? h('span', { title: `원래 값 ${s}` }, m[1].split(',').filter(Boolean).join(', ')) : s;
}
function item(s) {
  const kinds = arr(f(s, 'restriction_kinds'));
  return h('li.item', { id: anchorId(f(s, 'key')) },
    h('h4', ext(f(s, 'url'), str(f(s, 'title'))) || str(f(s, 'title')),
      f(s, 'alternative') ? h('span.badge.alt', '대체 자료') : null,
      f(s, 'manual') ? h('span.badge.alt', '수작업') : null,
      kinds.length ? h('a.badge.warnb', { href: '#' + anchorId(f(s, 'key')) + '-r', title: '조건이 있는 자료' }, '조건 있음') : null,
      CHECK.has(str(f(s, 'key'))) ? h('a.badge.warnb', { href: '#check-needed', title: '변경금지 조건 — 원 통계를 바꾸지 않고 모아 보이기만 하며 출처를 밝힌다' }, '변경금지 · 원값 그대로') : null,
      f(s, 'required_notice') ? h('a.badge.alt', { href: '#' + anchorId(f(s, 'key')) + '-n', title: '제공자가 지정한 고지 원문' }, '지정 고지') : null),
    f(s, 'used_in') ? h('p.use', f(s, 'used_in')) : null,
    dl([
      ['기준 시점', vintage(f(s, 'vintage'))],
      ['이용허락', licenseCell(s)],
      ['받은 날', f(s, 'retrieved') ? day(f(s, 'retrieved')) : null],
      ['갈래', f(s, 'group')],
      ['표기 이름', f(s, 'attribution_name')],
      ['원래 주소', safeURL(f(s, 'url')) ? h('a.ext.url', { href: safeURL(f(s, 'url')), rel: 'noopener noreferrer', target: '_blank' }, safeURL(f(s, 'url'))) : (f(s, 'manual') ? '저장소 코드 (수작업 표)' : null)],
    ]),
    f(s, 'license_note') && !isUnknown(s) ? h('p.note', f(s, 'license_note')) : null,
    f(s, 'odbl') ? h('p.note', f(s, 'odbl')) : null,
    shippedBlock(s),
    filesBlock(s));
}
function renderList(J) {
  const S = arr(f(J, 'sources'));
  const byPub = new Map();
  for (const s of S) { const p = str(f(s, 'publisher')) || '(기관 기록 없음)'; if (!byPub.has(p)) byPub.set(p, []); byPub.get(p).push(s); }
  const pubs = [...byPub.entries()].sort((a, b) => b[1].length - a[1].length || collator.compare(a[0], b[0]));
  const count = (key) => { const m = new Map(); for (const s of S) { const v = key(s); m.set(v, (m.get(v) || 0) + 1); } return [...m.entries()].sort((a, b) => b[1] - a[1] || collator.compare(a[0], b[0])); };
  const licOf = (s) => f(s, 'license_short') || (isUnknown(s) ? '이용허락 미확인' : str(f(s, 'license')).slice(0, 28));
  const grpOf = (s) => str(f(s, 'group')) || '(갈래 없음)';
  const sel = (id, label, opts) => h('label.field', { for: id }, h('span', label),
    h('select', { id }, h('option', { value: '' }, `모두 (${S.length})`), opts.map(([v, n]) => h('option', { value: v }, `${v} (${n})`))));
  const fg = sel('f-group', '갈래', count(grpOf));
  const fl = sel('f-lic', '이용허락', count(licOf));
  const q = h('input', { type: 'search', id: 'f-q', placeholder: '자료 · 기관 · 쓴 곳 · key', autocomplete: 'off' });
  const fq = h('label.field.grow', { for: 'f-q' }, h('span', '찾기'), q);
  const reset = h('button.btn.ghost', { type: 'button' }, '처음대로');
  const status = h('p.count', { role: 'status', 'aria-live': 'polite' });
  const rows = [];
  const sections = pubs.map(([p, list]) => {
    const n = h('span.n');
    const mine = [];
    const ol = h('ol.items', list.map((s) => {
      const li = item(s);
      mine.push(rows[rows.push({ li, s, text: [f(s, 'title'), f(s, 'publisher'), f(s, 'used_in'), f(s, 'license'), licOf(s), f(s, 'key'), f(s, 'vintage'), f(s, 'group')].map(str).join(' ').toLowerCase() }) - 1]);
      return li;
    }));
    const sec = h('section.pub', h('h3', p, ' ', n), ol);
    return { sec, n, list, mine };
  });
  const apply = () => {
    const g = fg.querySelector('select').value, l = fl.querySelector('select').value, t = q.value.trim().toLowerCase();
    let shown = 0;
    for (const r of rows) {
      const on = (!g || grpOf(r.s) === g) && (!l || licOf(r.s) === l) && (!t || t.split(/\s+/).every((w) => r.text.includes(w)));
      r.li.hidden = !on; r.on = on; if (on) shown++;
    }
    for (const x of sections) {
      const k = x.mine.filter((r) => r.on).length;
      x.sec.hidden = k === 0;
      x.n.textContent = k === x.list.length ? `${k}건` : `${k} / ${x.list.length}건`;
    }
    status.textContent = shown === S.length ? `출처 ${S.length}건 · 기관 ${pubs.length}곳` : `${shown}건 / ${S.length}건`;
  };
  fg.querySelector('select').addEventListener('change', apply);
  fl.querySelector('select').addEventListener('change', apply);
  q.addEventListener('input', apply);
  reset.addEventListener('click', () => { fg.querySelector('select').value = ''; fl.querySelector('select').value = ''; q.value = ''; apply(); q.focus(); });
  // 다른 곳(조건 카드·미확인 목록)의 링크로 가려진 항목에 닿으면 거르기를 풀어 보인다
  addEventListener('hashchange', () => revealHash(rows, reset));
  apply();
  setTimeout(() => revealHash(rows, reset), 0);
  return [h('form.filters', { role: 'search', 'aria-label': '출처 거르기', onsubmit: (e) => e.preventDefault() }, fg, fl, fq, reset), status, h('div.pubs', sections.map((x) => x.sec))];
}
function revealHash(rows, reset) {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id.startsWith('src-') || id.endsWith('-r')) return;
  const r = rows.find((x) => x.li.id === id);
  if (r && r.li.hidden) { reset.click(); }
  if (r) { r.li.scrollIntoView({ block: 'start' }); r.li.classList.add('hit'); setTimeout(() => r.li.classList.remove('hit'), 2400); }
}

// ---- 계산한 층 ----
function renderDerived(J) {
  const D = arr(f(J, 'derived'));
  if (!D.length) return [h('p.dim', '계산한 층의 기록이 없습니다.')];
  const S = arr(f(J, 'sources'));
  const byKey = new Map(S.map((s) => [f(s, 'key'), s]));
  return [h('div.dcards', D.map((d) => {
    const ins = arr(f(d, 'inputs'));
    const parts = arr(f(d, 'parts'));
    const inList = h('ul.inputs', ins.map((k) => { const s = byKey.get(k); return h('li', h('a', { href: '#' + anchorId(k) }, s ? str(f(s, 'title')) : str(k)), s ? h('span.by', ' — ', str(f(s, 'publisher'))) : null); }));
    return h('article.dcard', { id: 'd-' + str(f(d, 'key')).replace(/[^\w-]/g, '_') },
      h('h3', str(f(d, 'title'))),
      h('p.by', str(f(d, 'used_in')), f(d, 'file') ? [' · ', h('code', str(f(d, 'file')))] : null),
      f(d, 'rule') && !parts.length ? h('p.rule', f(d, 'rule')) : null,
      parts.length && f(d, 'rule') && f(d, 'rule') !== parts.map((p) => `${f(p, 'name')}: ${f(p, 'rule')}`).join(' / ') ? h('p.rule', f(d, 'rule')) : null,
      parts.length ? h('dl.parts', parts.map((p) => h('div', h('dt', str(f(p, 'name'))), h('dd', str(f(p, 'rule')))))) : null,
      f(d, 'checks') ? h('p.dim', '검사: ', f(d, 'checks'), f(d, 'version') ? ` · 판 ${f(d, 'version')}` : '') : null,
      ins.length ? (ins.length > 6 ? h('details.inputs', h('summary', `입력 출처 ${ins.length}건`), inList) : h('div', h('h4', '입력 출처'), inList))
        : h('p.dim', '입력: ', str(f(d, 'inputs_note') || '–')));
  }))];
}

// ---- 글꼴·그 밖의 표기 ----
const repoToSite = (p) => (str(p).startsWith('site/') ? '../' + str(p).slice(5) : null);
function renderCredits(J) {
  const C = arr(f(J, 'credits'));
  const fonts = C.filter((c) => f(c, 'kind') === 'font');
  const other = C.filter((c) => f(c, 'kind') !== 'font');
  const fontCards = fonts.map((c) => h('article.fcard',
    h('h4', str(f(c, 'title'))),
    h('p.by', str(f(c, 'role') || '')),
    dl([
      ['만든 이', f(c, 'publisher')],
      ['이용허락', [repoToSite(f(c, 'license_file')) ? h('a', { href: repoToSite(f(c, 'license_file')) }, str(f(c, 'license'))) : str(f(c, 'license')),
        arr(f(c, 'reserved_font_name')).length ? h('small', `예약 글꼴 이름: ${arr(f(c, 'reserved_font_name')).join(', ')} — 줄인 파일은 이름을 바꿨습니다`) : null]],
      ['원본', [ext(f(c, 'url'), '저장소'), f(c, 'source_ref') ? h('small', f(c, 'source_ref')) : null]],
      ['받은 날', f(c, 'retrieved')],
      ['쓰는 곳', f(c, 'used_in')],
    ]),
    f(c, 'note') ? h('p.note', f(c, 'note')) : null,
    h('details.files', h('summary', '저작권 표시 · 파일'),
      arr(f(c, 'copyright')).map((t) => h('p.copy', t)),
      h('ol.fl', arr(f(c, 'files')).map((x) => h('li', h('code', str(f(x, 'file'))), f(x, 'bytes') ? ` (${fmtBytes(f(x, 'bytes'))})` : '', f(x, 'sha256') ? h('code.sha', str(f(x, 'sha256'))) : null))))));
  const otherCards = other.map((c) => h('article.ocard',
    h('h4', ext(f(c, 'url'), str(f(c, 'title'))) || str(f(c, 'title'))),
    h('p.by', str(f(c, 'publisher'))),
    f(c, 'used_in') ? h('p', f(c, 'used_in')) : null,
    arr(f(c, 'names')).length ? h('p', h('code', arr(f(c, 'names')).join(' · '))) : null,
    h('p', h('b', '이용허락: '), h('span', { class: f(c, 'license') === UNKNOWN ? 'na' : null }, str(f(c, 'license')) || UNKNOWN)),
    f(c, 'license_note') ? h('p.note', f(c, 'license_note')) : null));
  return [
    h('h3', '글꼴'),
    h('p', '신여지도와 이 쪽이 쓰는 글꼴은 모두 사이트 안에 실려 있고(자체 호스팅), SIL Open Font License 1.1 입니다. 이용허락 전문은 이름을 누르면 열립니다. 기존판은 글꼴 파일을 싣지 않고 기기의 글꼴을 씁니다.'),
    fonts.length ? h('div.fcards', fontCards) : h('p.dim', '글꼴 기록이 없습니다.'),
    h('h3', '그 밖의 표기'),
    otherCards.length ? h('div.ocards', otherCards) : h('p.dim', '기록이 없습니다.'),
    h('p.dim', '아이콘과 종이 무늬는 이 프로젝트에서 새로 그린 것입니다. 그림문자(이모지)는 기기의 글꼴로 보입니다.'),
  ];
}

// ---- 기록에 대하여 ----
function renderNotes(J) {
  return [
    f(J, 'license_rule') ? h('p', f(J, 'license_rule')) : null,
    arr(f(J, 'notes')).length ? h('ul.notes', arr(f(J, 'notes')).map((n) => h('li', str(n)))) : null,
    f(f(J, 'attribution'), 'rule') ? h('p.dim', f(f(J, 'attribution'), 'rule')) : null,
  ];
}

// ---- 돌아가는 링크: 판에서 왔으면 보던 화면(주소의 # 까지)으로 ----
function backLinks() {
  try {
    const ref = document.referrer ? new URL(document.referrer) : null;
    if (!ref || ref.origin !== location.origin) return;
    const root = new URL('../', location.href).pathname;
    const yeo = new URL('../yeojido/', location.href).pathname;
    const p = ref.pathname;
    const a = p.startsWith(yeo) ? document.getElementById('back-yeojido') : (p === root || p === root + 'index.html') ? document.getElementById('back-koreaciv') : null;
    if (!a) return;
    a.classList.add('from');
    a.setAttribute('aria-describedby', 'from-note');
    // 같은 창에서 왔으면 뒤로 가기로 돌아간다 (보던 자리·렌즈를 담은 주소의 # 까지 그대로). 아니면 링크 그대로
    a.addEventListener('click', (e) => { if (history.length > 1) { e.preventDefault(); history.back(); } });
    document.querySelector('.editions').append(h('span.sr-only', { id: 'from-note' }, '보던 화면으로 돌아갑니다'));
  } catch (e) { /* 주소를 읽지 못하면 기본 링크 그대로 */ }
}

// ---- 인쇄: 접힌 칸을 펴서 찍고 되돌린다 ----
let opened = [];
addEventListener('beforeprint', () => { opened = [...document.querySelectorAll('details:not([open])')]; for (const d of opened) d.open = true; });
addEventListener('afterprint', () => { for (const d of opened) d.open = false; opened = []; });

async function main() {
  backLinks();
  let J;
  try {
    const r = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    J = await r.json();
  } catch (e) {
    fill('summary', () => [h('p.warn', { role: 'alert' }, h('b', '불러오지 못함 '), '출처 목록(', h('a', { href: DATA_URL }, 'data/sources.json'), ')을 읽지 못했습니다. 새로 고쳐 보십시오. 같은 기록의 요약은 저장소의 NOTICE.md 에 있습니다.')]);
    for (const n of ['profile', 'cite', 'notices', 'restricted', 'unknown', 'list', 'derived', 'credits', 'notes']) fill(n, () => [h('p.dim', '—')]);
    return;
  }
  CHECK = new Set(arr(f(f(J, 'profile'), 'check_needed')).map((x) => str(f(x, 'key'))));
  KINDS = new Map(arr(f(J, 'restriction_kinds')).filter((k) => f(k, 'code')).map((k) => [f(k, 'code'), { code: f(k, 'code'), name: str(f(k, 'name')), text: str(f(k, 'text')) }]));
  fill('summary', () => renderSummary(J));
  fill('profile', () => renderProfile(J));
  fill('cite', () => renderCite(J));
  fill('notices', () => renderNotices(J));
  fill('restricted', () => renderRestricted(J));
  fill('unknown', () => renderUnknown(J));
  fill('list', () => renderList(J));
  fill('derived', () => renderDerived(J));
  fill('credits', () => renderCredits(J));
  fill('notes', () => renderNotes(J));
  document.body.classList.add('is-ready');
  if (location.hash && !location.hash.startsWith('#src-')) { const t = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t) t.scrollIntoView(); }
}
main();
