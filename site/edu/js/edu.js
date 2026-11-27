// 교육의 활용 — content.json 을 읽어 그린다. 글은 모두 텍스트 노드로 넣는다 (내용 글을 HTML 로 풀지 않는다).
// 두 판(koreaciv, 신여지도)이 함께 쓰는 쪽이라 어느 판의 모듈도 가져오지 않는다.
// 수치는 이 파일에도 content.json 에도 없다: '지금 자료의 값'은 ../data/*.json 에서 그때 읽는다 (경로 문법은 pipeline/build_edu.py 의 Data.resolve 와 같다).

const CONTENT_URL = 'content.json';
const DATA = '../data/';
const STAGE = { observe: '관찰', interpret: '해석', limit: '한계' };
const FIT = { direct: '직접 연결', partial: '부분 연결' };

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
  for (const k of kids.flat(Infinity)) {
    if (k == null || k === false || k === '') continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}
const arr = (v) => (Array.isArray(v) ? v : []);
const slot = (name) => document.querySelector(`[data-slot="${name}"]`);
const fill = (name, ...kids) => { const s = slot(name); if (s) s.replaceChildren(...kids.flat(Infinity).filter(Boolean)); };
const safeURL = (u) => (/^https?:\/\//i.test(String(u || '').trim()) ? String(u).trim() : null);
const safeHash = (x) => (typeof x === 'string' && /^#[\w=&,.\-%]*$/.test(x) ? x : null);
const hashLens = (x) => { const m = /(?:^#|&)lens=([\w]+)/.exec(x || ''); return m ? m[1] : null; };

let C = null; // content.json

// ---- '지도에서 열기' 단추 ----
// 두 판에 같은 해시를 넘긴다. editions 가 한 판만 가리키면 다른 판 단추는 누를 수 없게 두고 까닭을 적는다.
function opens(hash, { editions, label, small, note } = {}) {
  const hs = safeHash(hash);
  if (!hs) return null;
  const lens = hashLens(hs);
  const box = h('div.opens');
  if (label) box.append(h('span.lab', label));
  for (const [id, ed] of Object.entries(C.editions)) {
    const off = editions && !editions.includes(id);
    const a = off
      ? h('span.btn.ghost' + (small ? '.sm' : ''), { 'aria-disabled': 'true', title: note || '이 판에는 이 수업에 쓰는 기능이 없습니다' }, ed.name, h('span.sub', '이 판에서는 안 됨'))
      : h('a.btn' + (id === 'yeojido' ? '.ghost' : '') + (small ? '.sm' : ''), { href: ed.path + hs, target: '_blank', rel: 'noopener', 'data-lens': lens, 'data-edition': id }, ed.name, h('span.sub', ed.sub + '에서 열기'));
    box.append(a);
  }
  if (editions && note) box.append(h('span.why', note));
  return box;
}

// 지금 자료(../data/lenses.json)에 없는 렌즈를 가리키는 단추는 누를 수 없게 바꾸고 표시한다 (공개판에서 빠지는 렌즈)
let lensIds = null;
function markAbsent(root = document) {
  if (!lensIds) return;
  for (const a of root.querySelectorAll('a.btn[data-lens]')) {
    if (lensIds.has(a.dataset.lens)) continue;
    const s = h('span', { class: a.className + ' absent', 'aria-disabled': 'true', title: `이 판의 자료에는 '${a.dataset.lens}' 렌즈가 없습니다` }, a.firstChild.textContent, h('span.sub', '이 판에 없는 렌즈'));
    a.replaceWith(s);
  }
}

// ---- 자료 읽기 ('지금 자료의 값') ----
const cache = new Map();
function getJSON(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(DATA + name + '.json').then((r) => { if (!r.ok) throw new Error(`${name}.json ${r.status}`); return r.json(); })
      .catch((e) => { cache.delete(name); throw e; }));
  }
  return cache.get(name);
}
const dig = (o, dotted) => {
  for (const k of dotted ? dotted.split('.') : []) {
    if (o == null || typeof o !== 'object' || !(k in o)) throw new Error(`필드 ${k} 없음`);
    o = o[k];
  }
  return o;
};
async function lensRange(lid, codes) {
  const [L, W] = await Promise.all([getJSON('lenses'), getJSON('world')]);
  const lens = arr(L.lenses).find((x) => x.id === lid);
  if (!lens) throw new Error(`렌즈 ${lid} 없음`);
  if (!lens.by_county) throw new Error(`렌즈 ${lid} 는 칸 값`);
  const idx = new Map(arr(W.counties).map((c, i) => [c.code, i]));
  const v = codes.map((c) => lens.by_county[idx.get(c)]).filter((x) => typeof x === 'number');
  return { lens, range: v.length ? [Math.min(...v), Math.max(...v)] : null };
}
async function resolve(path) {
  const p = path.split(':');
  if (p[0] === 'city') { const c = (await getJSON('cities')).find((x) => x.id === Number(p[1])); if (!c) throw new Error('도시 없음'); return { v: dig(c, p[2]) }; }
  if (p[0] === 'state') { const s = (await getJSON('states')).find((x) => x.code === p[1]); if (!s) throw new Error('시도 없음'); return { v: dig(s, p[2]) }; }
  if (p[0] === 'nation') return { v: dig((await getJSON('nation')).nation, p[1]) };
  if (p[0] === 'route') { const s = arr((await getJSON('trade')).routes.segments).find((x) => `${x.a}-${x.b}` === p[1]); if (!s) throw new Error('교역로 없음'); return { v: dig(s, p[2]) }; }
  if (p[0] === 'layer') return { v: dig(await getJSON(p[1]), p[2]) };
  if (p[0] === 'lens') {
    if (p[2] === 'city' || p[2] === 'state') {
      let codes;
      if (p[2] === 'city') { const c = (await getJSON('cities')).find((x) => x.id === Number(p[3])); if (!c) throw new Error('도시 없음'); codes = c.sgg; }
      else codes = arr((await getJSON('world')).counties).map((c) => c.code).filter((c) => c.startsWith(p[3]));
      const { lens, range } = await lensRange(p[1], codes);
      return { v: p[4] ? (range ? range[p[4] === 'lo' ? 0 : 1] : null) : range, lens };
    }
    const lens = arr((await getJSON('lenses')).lenses).find((x) => x.id === p[1]);
    if (!lens) throw new Error(`렌즈 ${p[1]} 없음`);
    return { v: dig(lens, p[2]) };
  }
  throw new Error('모르는 경로');
}
const nf = (d) => new Intl.NumberFormat('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (x, d) => (x > 0 ? '+' : x < 0 ? '−' : '') + nf(d).format(Math.abs(x));
function fmtLensValue(x, lens) {
  const f = lens.format;
  if (f === 'cat') return arr(lens.categories)[x] ?? String(x);
  const d = f === 'int' ? 0 : f === 'f2' || f === 'pct2' ? 2 : 1;
  return lens.scale === 'diverging' && lens.unit === '%' ? signed(x, d) : nf(d).format(x);
}
function fmt(res, f) {
  const v = res.v;
  if (v == null) return null;
  const u = f.unit ? (/^[가-힣%]/.test(f.unit) ? f.unit : ' ' + f.unit) : '';
  switch (f.fmt) {
    case 'int': return nf(0).format(v) + u;
    case 'f1': return nf(1).format(v) + u;
    case 'f2': return nf(2).format(v) + u;
    case 'pct1': return nf(1).format(v) + '%';
    case 'spct1': return signed(v, 1) + '%';
    case 'won_man': return nf(0).format(Math.round(v / 10000)) + '만 원';
    case 'ton_man': return nf(0).format(Math.round(v / 10000)) + '만 톤';
    case 'count': return nf(0).format(Array.isArray(v) ? v.length : Object.keys(v).length) + u;
    case 'lens': {
      const L = res.lens, un = L.unit ? (L.unit === '%' ? '%' : ' ' + L.unit) : '';
      if (!Array.isArray(v)) return fmtLensValue(v, L) + un;
      return v[0] === v[1] ? fmtLensValue(v[0], L) + un : `${fmtLensValue(v[0], L)} ~ ${fmtLensValue(v[1], L)}${un} (구·군별 범위)`;
    }
    default: return String(v) + u;
  }
}
async function loadFacts(lesson, box, btn) {
  btn.disabled = true;
  btn.textContent = '자료를 읽는 중…';
  const rows = [];
  let failed = 0;
  for (const f of arr(lesson.facts)) {
    let txt = null, cls = '';
    try { txt = fmt(await resolve(f.path), f); if (txt == null) { txt = '자료 없음'; cls = 'na'; } }
    catch (e) { txt = '이 자료에서 읽지 못함'; cls = 'na'; failed++; }
    rows.push(h('tr', h('th', { scope: 'row' }, f.label), h('td', { class: cls }, txt)));
  }
  let prof = '';
  if (cache.has('world')) { try { prof = (await cache.get('world')).build_profile === 'public' ? ' · 공개판 자료' : ' · 전체판 자료'; } catch (e) { /* */ } }
  box.querySelector('.out').replaceChildren(
    h('table.facts', h('caption.sr-only', '지금 자료의 값'), h('tbody', rows)),
    h('p', `읽은 때 ${new Date().toLocaleString('ko-KR')}${prof}. 자료가 새로 빌드되면 달라집니다. 수업 전에 지도에서도 한 번 확인하십시오.${failed ? ` 읽지 못한 값 ${failed}개는 지도에서 직접 읽습니다.` : ''}`));
  btn.textContent = '다시 읽기';
  btn.disabled = false;
  lesson._factsLoaded = true;
}

// ---- 그리기: 소개 ----
function renderAbout() {
  const m = C.meta, cur = C.curriculum;
  const n = (k) => arr(C[k]).length;
  fill('about',
    h('p.lede', m.lede),
    h('p.measure', m.audience),
    h('div.facts-row', { role: 'group', 'aria-label': '이 쪽에 있는 것' },
      h('a', { href: '#lessons' }, h('b', n('lessons')), h('span', '수업안')),
      h('a', { href: '#quick' }, h('b', n('quick')), h('span', '5~10분 활동')),
      h('a', { href: '#projects' }, h('b', n('projects')), h('span', '학생 탐구 과제')),
      h('a', { href: '#curriculum' }, h('b', Object.keys(C.standards).length), h('span', '성취기준 (고시 원문 대조)'))),
    h('h3', '먼저 알아 둘 것'),
    h('ul.caveats', arr(m.caveats).map((c) => h('li', c))),
    h('div.applies',
      h('h3', `${cur.applies.school_year}학년도에 2022 개정 교육과정이 적용되는 학년`),
      h('p', cur.applies.text),
      h('p.dim', cur.applies.note, ' ', h('a', { href: '#curriculum' }, '근거 보기'))));
}

function renderStart() {
  const s = C.start;
  fill('start',
    h('p.lede', s.lede),
    h('ol.strip', arr(s.steps).map((st) => h('li', h('h3', st.title), h('p', st.text), opens(st.hash, { small: true })))));
}

// ---- 그리기: 수업안 ----
const lessonById = new Map();
function stdItem(s) {
  const d = C.standards[s.code];
  if (!d) return h('li', s.code);
  const doc = arr(C.curriculum.documents).find((x) => x.id === d.doc);
  return h('li',
    h('span.code', s.code), h('span', { class: 'badge ' + s.fit }, FIT[s.fit] || s.fit), ' ', d.text,
    h('span.fitnote', s.note),
    h('span.src', `${d.band} · ${d.course} · ${d.unit} — ${doc ? doc.title : d.doc}, PDF ${d.page}쪽`));
}
function lessonPlan(l) {
  const lv = C.levels.find((x) => x.id === l.level);
  const eds = l.editions || null;
  const plan = h('div.plan');
  plan.append(
    h('div.bar',
      opens(l.open.hash, { editions: eds, label: '지도에서 열기', note: l.editions_note }),
      h('div.opens',
        h('button.btn.ghost.sm', { type: 'button', onclick: () => printOne(l) }, '이 수업안 인쇄'),
        h('a.anchor', { href: '#' + l.id, title: '이 수업안의 주소' }, '#' + l.id))),
    h('p.dim', { hidden: !l.open.label }, l.open.label || ''),
    h('dl.kv',
      h('div', h('dt', '대상'), h('dd', l.target)),
      h('div', h('dt', '시간'), h('dd', l.periods)),
      h('div', h('dt', '기기'), h('dd', l.devices)),
      lv ? h('div', h('dt', '교육과정 적용'), h('dd', lv.note)) : null),
    h('h4', '성취기준'),
    h('ul.stds', arr(l.standards).map(stdItem)),
    h('h4', '세 줄 요약'),
    h('ol.summary3', arr(l.summary).map((x) => h('li', x))),
    h('h4', '지도에서 할 일 — 세 단계'),
    h('ol.steps', arr(l.steps).map((st) => h('li', h('span', st.text), st.hash ? opens(st.hash, { editions: eds, small: true, label: '이 화면 열기' }) : null))),
    h('h4', '활동지 질문 (관찰 → 해석 → 한계)'),
    h('ol.ws', arr(l.worksheet).map((q) => h('li', h('span.stage', { 'data-stage': q.stage }, STAGE[q.stage] || q.stage), q.q))),
    h('h4', '마무리 질문'),
    h('p.closingq', l.closing),
    h('h4', '평가 기준'),
    h('table.rubric', h('tbody',
      h('tr', h('th', { scope: 'row' }, '상'), h('td', l.rubric.high)),
      h('tr', h('th', { scope: 'row' }, '중'), h('td', l.rubric.mid)),
      h('tr', h('th', { scope: 'row' }, '하'), h('td', l.rubric.low)))),
    h('div.care',
      h('div', h('h4', '주의할 점'), h('ul', arr(l.cautions).map((x) => h('li', x)))),
      h('div.dont', h('h4', '하지 말 것'), h('ul', arr(l.donts).map((x) => h('li', x))))),
    h('div.variants',
      h('div', h('h4', '더 쉽게'), h('p', l.easier)),
      h('div', h('h4', '더 깊게'), h('p', l.harder), l.harder_hash ? opens(l.harder_hash, { editions: eds, small: true, label: '이 화면 열기' }) : null)));
  if (arr(l.facts).length) {
    const btn = h('button.btn.ghost.sm.loadbtn', { type: 'button' }, '지금 자료의 값 읽기');
    const box = h('div.factbox',
      h('h4', '교사용 — 지금 자료의 값'),
      h('p', '수업안의 글에는 수치를 적지 않았습니다. 단추를 누르면 이 사이트의 자료(data/)에서 지금 값을 읽어 옵니다. 지도 자료 몇 메가바이트를 받습니다.'),
      btn, h('div.out', { 'aria-live': 'polite' }));
    btn.addEventListener('click', () => loadFacts(l, box, btn).catch(() => { btn.disabled = false; btn.textContent = '다시 읽기'; box.querySelector('.out').replaceChildren(h('p.warn', '자료를 불러오지 못했습니다. 값은 지도에서 직접 읽으십시오.')); }));
    plan.append(box);
  }
  if (arr(l.next).length) {
    plan.append(h('p.nextl', '이어서 하기 좋은 수업안: ', arr(l.next).map((id, i) => { const n = lessonById.get(id); return [i ? ' · ' : '', n ? h('a', { href: '#' + id }, n.title) : id]; })));
  }
  return plan;
}
function lessonEl(l) {
  const lv = C.levels.find((x) => x.id === l.level);
  const d = h('details.lesson', { id: l.id, 'data-level': l.level, 'data-subjects': arr(l.subjects).join('|'), 'data-themes': arr(l.themes).join('|'), 'data-time': l.minutes > 60 ? '2' : '1' },
    h('summary',
      h('span.t', l.title),
      h('span.meta', [lv ? lv.name : l.level, arr(l.subjects).join(' · '), l.periods].join(' · ')),
      h('span.q', l.question)));
  // 펼칠 때 한 번만 본문을 만든다 (인쇄·검색을 위해 처음부터 만들어 둔다 — 수업안이 많지 않다)
  d.append(lessonPlan(l));
  return d;
}
function renderLessons() {
  const subjects = [...new Set(C.lessons.flatMap((l) => arr(l.subjects)))];
  const sel = (id, label, opts) => h('label.field', label, h('select', { id }, h('option', { value: '' }, '모두'), opts.map(([v, t]) => h('option', { value: v }, t))));
  const fLevel = sel('f-level', '학교급', C.levels.map((x) => [x.id, x.name]));
  const fSubject = sel('f-subject', '과목', subjects.map((x) => [x, x]));
  const fTime = sel('f-time', '시간', [['1', '1차시'], ['2', '2차시']]);
  const fTheme = sel('f-theme', '주제', C.themes.map((x) => [x.id, x.name]));
  const count = h('p.count', { role: 'status', 'aria-live': 'polite' });
  const groups = C.levels.map((lv) => {
    const ls = C.lessons.filter((l) => l.level === lv.id);
    return h('section.levelgroup', { 'data-level': lv.id, 'aria-label': lv.name + ' 수업안' }, h('h3', lv.name, h('small', lv.note)), ls.map(lessonEl));
  });
  const all = () => [...document.querySelectorAll('details.lesson')];
  const apply = () => {
    const v = { level: fLevel.querySelector('select').value, subject: fSubject.querySelector('select').value, time: fTime.querySelector('select').value, theme: fTheme.querySelector('select').value };
    let shown = 0;
    for (const d of all()) {
      const ok = (!v.level || d.dataset.level === v.level) && (!v.subject || d.dataset.subjects.split('|').includes(v.subject))
        && (!v.time || d.dataset.time === v.time) && (!v.theme || d.dataset.themes.split('|').includes(v.theme));
      d.hidden = !ok;
      if (ok) shown++;
    }
    for (const g of groups) g.hidden = ![...g.querySelectorAll('details.lesson')].some((d) => !d.hidden);
    count.textContent = shown === C.lessons.length ? `수업안 ${shown}개` : `수업안 ${C.lessons.length}개 가운데 ${shown}개`;
  };
  for (const f of [fLevel, fSubject, fTime, fTheme]) f.querySelector('select').addEventListener('change', apply);
  const tools = h('div.tools',
    h('button.btn.ghost.sm', { type: 'button', onclick: () => all().forEach((d) => { if (!d.hidden) d.open = true; }) }, '모두 펼치기'),
    h('button.btn.ghost.sm', { type: 'button', onclick: () => all().forEach((d) => { d.open = false; }) }, '모두 접기'),
    h('button.btn.ghost.sm', { type: 'button', onclick: () => { for (const f of [fLevel, fSubject, fTime, fTheme]) f.querySelector('select').value = ''; apply(); } }, '고르기 풀기'));
  fill('lessons', h('div.filters', { role: 'group', 'aria-label': '수업안 고르기' }, fLevel, fSubject, fTime, fTheme, tools), count, groups);
  apply();
}

// ---- 그리기: 짧은 활동 · 과제 ----
const levelNames = (ids) => arr(ids).map((id) => (C.levels.find((x) => x.id === id) || {}).name || id).join(' · ');
function renderQuick() {
  fill('quick', h('div.cards', C.quick.map((q) => h('article.card', { id: q.id },
    h('h3', q.title),
    h('span.by', `${q.when} · ${q.minutes}분 · ${levelNames(q.levels)}`),
    h('p.q', q.question),
    h('p', q.how),
    opens(q.hash, { small: true })))));
}
function renderProjects() {
  fill('projects', h('div.cards', C.projects.map((p) => h('article.card', { id: p.id },
    h('h3', p.title),
    h('span.by', levelNames(p.levels)),
    h('p.q', p.question),
    h('p', h('span.k', '보는 화면'), p.screen),
    h('p', h('span.k', '내는 것'), p.deliverable),
    h('p.lim', h('span.k', '한계 확인'), p.limit),
    opens(p.hash, { small: true })))));
}

// ---- 그리기: 안내 · 할 수 없는 것 · 낱말 · 교육과정 ----
function renderGuide() {
  const g = C.guide;
  fill('guide',
    h('h3', { id: 'rules' }, g.rules.title),
    h('ol.rules', arr(g.rules.items).map((x) => h('li', h('b', x.t), h('span', x.d)))),
    h('h3', { id: 'sensitive' }, g.sensitive.title),
    h('p.lede', g.sensitive.lede),
    h('dl.defs.sens', arr(g.sensitive.items).map((x) => h('div', h('dt', x.t), h('dd', x.d)))),
    h('h3', { id: 'game' }, g.game.title),
    h('ul.plain', arr(g.game.items).map((x) => h('li', x))),
    h('h3', { id: 'faq' }, '자주 묻는 것'),
    arr(g.faq).map((x) => h('details.faq', h('summary', x.q), h('p', x.a))),
    h('h3', { id: 'devices' }, g.devices.title),
    h('dl.defs.cols', arr(g.devices.items).map((x) => h('div', h('dt', x.t), h('dd', x.d)))));
}
function renderCannot() {
  const c = C.cannot;
  fill('cannot', h('p.lede', c.lede), h('dl.defs.cols', arr(c.items).map((x) => h('div', h('dt', x.t), h('dd', x.d)))));
}
function renderGlossary() {
  fill('glossary', h('dl.defs.cols', C.glossary.map((x) => h('div', h('dt', x.term), h('dd', x.plain), x.kid ? h('dd.kid', x.kid) : null))));
}
function renderCurriculum() {
  const cur = C.curriculum;
  const uses = new Map();
  for (const l of C.lessons) for (const s of arr(l.standards)) { if (!uses.has(s.code)) uses.set(s.code, []); uses.get(s.code).push([l, s.fit]); }
  const link = (u, t) => (safeURL(u) ? h('a', { href: safeURL(u), target: '_blank', rel: 'noopener noreferrer' }, t) : u && !/^[a-z]+:/i.test(u) ? h('a', { href: u }, t) : t);
  fill('curriculum',
    h('p.lede', '수업안에 적은 성취기준은 모두 아래 고시 원문에서 글자 그대로 옮기고 다시 대조했습니다. 대조하지 못한 코드는 싣지 않았습니다. \'부분 연결\'은 성취기준의 일부만 이 지도로 다룰 수 있다는 뜻입니다.'),
    h('h3', '적용 학년'),
    h('p.measure', cur.applies.text),
    h('ul.plain', arr(cur.applies.schedule).map((x) => h('li', x))),
    h('p.dim.measure', cur.applies.note),
    h('h3', '2022 개정 고등학교 사회과의 과목'),
    h('p.measure', cur.structure.text),
    h('table.courses', h('tbody', arr(cur.structure.courses).map((x) => h('tr', h('th', { scope: 'row' }, x.kind), h('td', x.names))))),
    h('p.dim.measure', cur.structure.note),
    h('h3', '이 쪽이 쓴 성취기준'),
    h('div.tablewrap', h('table.std',
      h('thead', h('tr', h('th', { scope: 'col' }, '코드'), h('th', { scope: 'col' }, '성취기준 (고시 원문)'), h('th', { scope: 'col' }, '학교급 · 과목 · 단원'), h('th', { scope: 'col' }, '근거'), h('th', { scope: 'col' }, '쓰인 수업안'))),
      h('tbody', Object.entries(C.standards).map(([code, d]) => h('tr',
        h('td.code', code), h('td', d.text), h('td', `${d.band} · ${d.course} · ${d.unit}`), h('td', `${d.doc === 's10' ? '별책 10' : '별책 7'} PDF ${d.page}쪽`),
        h('td.use', arr(uses.get(code)).map(([l, fit], i) => [i ? ', ' : '', h('a', { href: '#' + l.id, title: l.title }, l.id), fit === 'partial' ? ' (부분)' : '']))))))),
    h('h3', '근거 문서'),
    h('p.measure', cur.how_to_find),
    h('ul.docs', arr(cur.documents).map((d) => h('li', h('b', d.title), h('br'), `${d.publisher} · 받은 날 ${d.retrieved} · `, link(d.url, '받는 곳'),
      d.note ? [h('br'), d.note] : null, d.file ? h('span.sha', `파일: ${d.file}${d.sha256 ? ' · sha256 ' + d.sha256 : ''}`) : null))),
    h('h3', '더 찾아볼 곳'),
    h('ul.plain', C.references.map((r) => h('li', link(r.url, r.title), r.note ? ' — ' + r.note : ''))));
}

// ---- 수업안 하나 인쇄 ----
// 본문과 따로 #printsheet 에 종이 두 장(학생용 활동지, 교사용)을 만들어 그것만 찍는다.
function buildSheet(l) {
  const lv = C.levels.find((x) => x.id === l.level);
  const big = l.level === 'e34';
  const abs = (ed, hs) => new URL(C.editions[ed].path + hs, location.href).href;
  const eds = l.editions || Object.keys(C.editions);
  const student = h('div.sheet' + (big ? '.big' : ''),
    h('div.ph', h('span', `${lv ? lv.name : ''} · ${arr(l.subjects).join(' · ')}`), h('span.who', '이름 ____________   날짜 ______')),
    h('h2', l.title),
    h('p.pq', l.question),
    arr(l.worksheet).map((q, i) => h('div.wsq', h('p', `${i + 1}. ${q.q}`), h('div.lines', Array.from({ length: q.stage === 'observe' ? 2 : 3 }, () => h('i'))))),
    h('div.closing', h('b', '마무리'), l.closing, h('div.lines', h('i'), h('i'))),
    h('p.foot', '지도: koreaciv · 신여지도 (공공 통계로 그린 대한민국 지도). 숫자마다 조사한 때가 다르니 범례의 \'기준\'을 함께 적습니다.'));
  const teacher = h('div.sheet',
    h('div.ph', h('span', `교사용 · ${l.target} · ${l.periods}`), h('span.who', '#' + l.id)),
    h('h2', l.title),
    h('h3', '성취기준'),
    h('ul', arr(l.standards).map((s) => { const d = C.standards[s.code] || {}; return h('li', `${s.code} ${d.text || ''} (${FIT[s.fit]}: ${s.note})`); })),
    h('h3', '요약'),
    h('ol', arr(l.summary).map((x) => h('li', x))),
    h('h3', '지도에서 할 일'),
    h('ol', arr(l.steps).map((st) => h('li', st.text, st.hash ? eds.map((e) => h('div.url', `${C.editions[e].name}: ${abs(e, st.hash)}`)) : null))),
    h('h3', '평가 기준'),
    h('table', h('tbody', h('tr', h('th', '상'), h('td', l.rubric.high)), h('tr', h('th', '중'), h('td', l.rubric.mid)), h('tr', h('th', '하'), h('td', l.rubric.low)))),
    h('div.two',
      h('div', h('h3', '주의할 점'), h('ul', arr(l.cautions).map((x) => h('li', x)))),
      h('div', h('h3', '하지 말 것'), h('ul', arr(l.donts).map((x) => h('li', x))))),
    h('div.two', h('div', h('h3', '더 쉽게'), h('p', l.easier)), h('div', h('h3', '더 깊게'), h('p', l.harder))),
    h('p.foot', `${C.meta.caveats[0]} 성취기준 출처: 교육부 고시 제2022-33호(국가교육과정정보센터 게시). ${new URL('#' + l.id, location.href).href}`));
  return [student, teacher];
}
function printOne(l) {
  const sheet = document.getElementById('printsheet');
  sheet.replaceChildren(...buildSheet(l));
  document.body.classList.add('print-one');
  const done = () => { document.body.classList.remove('print-one'); sheet.replaceChildren(); window.removeEventListener('afterprint', done); };
  window.addEventListener('afterprint', done);
  window.print();
}
// 쪽 전체를 찍을 때는 접힌 수업안을 펴서 찍는다
window.addEventListener('beforeprint', () => {
  if (document.body.classList.contains('print-one')) return;
  for (const d of document.querySelectorAll('details.lesson, details.faq')) { if (!d.open) { d.dataset.wasClosed = '1'; d.open = true; } }
});
window.addEventListener('afterprint', () => {
  for (const d of document.querySelectorAll('details[data-was-closed]')) { d.open = false; delete d.dataset.wasClosed; }
});

// ---- 주소의 닻(#id): 수업안이면 펼치고 그 자리로 ----
function goHash() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id || !/^[\w-]+$/.test(id)) return;
  const el = document.getElementById(id);
  if (!el) return;
  if (el.matches('details.lesson')) {
    if (el.hidden) { for (const s of document.querySelectorAll('.filters select')) s.value = ''; document.querySelector('.filters select').dispatchEvent(new Event('change')); }
    el.open = true;
    for (const x of document.querySelectorAll('details.lesson.hit')) x.classList.remove('hit');
    el.classList.add('hit');
  }
  el.scrollIntoView({ block: 'start' });
}

// ---- 시작 ----
async function main() {
  let res;
  try {
    res = await fetch(CONTENT_URL);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    C = await res.json();
    if (!C || !Array.isArray(C.lessons) || !C.meta) throw new Error('내용의 꼴이 다름');
  } catch (e) {
    fill('about', h('p.warn', { role: 'alert' }, '내용(content.json)을 불러오지 못했습니다. 새로 고치거나 잠시 뒤에 다시 열어 주십시오. ',
      h('a', { href: CONTENT_URL }, '내용 원본을 직접 열기'), '. 이 쪽은 개인이 만든 비공식 자료이며 교육부·교육청·교과서 발행사와 관계가 없습니다.'));
    document.body.classList.add('is-failed');
    return;
  }
  for (const l of C.lessons) lessonById.set(l.id, l);
  const parts = [['about', renderAbout], ['start', renderStart], ['lessons', renderLessons], ['quick', renderQuick], ['projects', renderProjects],
    ['guide', renderGuide], ['cannot', renderCannot], ['glossary', renderGlossary], ['curriculum', renderCurriculum]];
  for (const [name, fn] of parts) {
    try { fn(); } catch (e) { fill(name, h('p.warn', '이 부분을 그리지 못했습니다. 내용 원본(content.json)을 확인해 주십시오.')); console.warn('edu: ' + name, e); }
  }
  // 어느 판에서 왔는지 (링크의 ?from= 또는 앞 쪽 주소)
  const from = new URLSearchParams(location.search).get('from') || (/\/yeojido\//.test(document.referrer) ? 'yeojido' : '');
  const back = document.getElementById(from === 'yeojido' ? 'back-yeojido' : from === 'koreaciv' ? 'back-koreaciv' : '');
  if (back) back.classList.add('from');
  document.body.classList.add('is-ready');
  goHash();
  window.addEventListener('hashchange', goHash);
  // 지금 자료의 렌즈 목록을 받아, 없는 렌즈를 가리키는 단추를 표시한다. 못 받아도 쪽은 그대로 쓴다.
  getJSON('lenses').then((L) => { lensIds = new Set(arr(L.lenses).map((x) => x.id)); markAbsent(); document.body.classList.add('lenses-known'); })
    .catch(() => { document.body.classList.add('lenses-unknown'); });
}
main();
