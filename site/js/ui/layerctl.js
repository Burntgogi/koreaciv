// 층 조작 (6단계): 접힌 한 줄(묶음 아이콘 5개)이 기본. 아이콘을 누르면 그 묶음을 켜고 끈다.
// ▾ 를 누르면 펼쳐져 종류별 세부 켜고 끄기가 나온다. 층 자료는 첫 화면을 그린 뒤 따로 불러온다.

import { iconURL, KINDS, LAYER_GROUPS, SUB_ICONS } from '../render/layers.js';

// 층 자료에 항목이 있는 세부·종류 (그 판에 없는 층 — 공개판의 광산·한우 — 은 조작부에 두지 않는다). 선 층(도로·교역로·접경)은 늘 둔다
const LINE_SUBS = new Set(['lines', 'routes', 'frontier']);
function presentKinds(layers) {
  const kinds = new Set();
  for (const L of Object.values(layers || {})) for (const it of (L && Array.isArray(L.items) ? L.items : [])) kinds.add(it.kind);
  return kinds;
}

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

function groupIcon(g) {
  if (g.icon) return `<img src="${iconURL(g.icon)}" alt="">`;
  return '<i class="fr"></i>';
}

function subIcon(k, kinds) {
  const ks = (SUB_ICONS[k] || []).filter((kd) => !kinds || kinds.has(kd));
  if (k === 'lines') return '<i class="rd"></i><i class="rl"></i>';
  if (k === 'routes') return '<i class="tr"></i>';
  if (k === 'frontier') return '<i class="fr"></i>';
  return ks.map((kd) => `<img src="${iconURL(kd, kd === 'station')}" alt="">`).join('');
}

export class LayerControl {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('layerctl');
    this.open = false;
    this.render();
    this.el.addEventListener('change', (e) => {
      const s = e.target.dataset.sub;
      if (!s) return;
      if (e.target.checked) app.subOff.delete(s);
      else app.subOff.add(s);
      const g = e.target.dataset.group;
      // 세부를 켜면 묶음도 켠다 (켜진 세부가 꺼진 묶음에 묻히지 않게)
      if (e.target.checked && !app.layerOn[g]) app.layerOn[g] = true;
      this.render();
      app.requestDraw();
    });
    this.el.addEventListener('click', (e) => {
      if (e.target.closest('[data-toggle]')) {
        this.open = !this.open;
        this.render();
        return;
      }
      const g = e.target.closest('[data-grp]');
      if (g && !g.disabled) app.toggleLayerGroup(g.dataset.grp);
    });
  }

  render() {
    const a = this.app;
    const ready = !!a.layers;
    const kinds = ready ? presentKinds(a.layers) : null;
    const subsOf = (g) => g.subs.filter(([k]) => !kinds || LINE_SUBS.has(k) || [...kinds].some((kd) => KINDS[kd] && KINDS[kd].sub === k));
    this.el.classList.toggle('open', this.open);
    const row = LAYER_GROUPS.map((g) => `<button class="lg ${a.layerOn[g.id] ? 'on' : ''}" data-grp="${esc(g.id)}" aria-pressed="${esc(a.layerOn[g.id])}" title="${esc(g.name)} ${a.layerOn[g.id] ? '끄기' : '켜기'}" ${ready ? '' : 'disabled'}>
      ${groupIcon(g)}<span>${esc(g.name)}</span></button>`).join('');
    const detail = this.open
      ? `<div class="subs">${LAYER_GROUPS.map((g) => `<div class="sg ${a.layerOn[g.id] ? '' : 'off'}"><p>${esc(g.name)}${a.layerOn[g.id] ? '' : ' <small>꺼짐</small>'}</p>
          ${subsOf(g).map(([k, nm]) => `<label><input type="checkbox" data-group="${esc(g.id)}" data-sub="${k}" ${a.subOff.has(k) ? '' : 'checked'} ${ready ? '' : 'disabled'}><span class="nm">${esc(nm)}</span><span class="ic">${subIcon(k, kinds)}</span></label>`).join('')}</div>`).join('')}
          <p class="hint">배율에 따라 아이콘 수가 달라진다 — 규칙은 연감 › 지도 층</p></div>`
      : '';
    this.el.innerHTML = `<div class="row" role="group" aria-label="지도 층">${row}<button class="more" data-toggle aria-expanded="${this.open}" title="${this.open ? '세부 접기' : '종류별 세부 켜고 끄기'}">${ready ? (this.open ? '▴' : '▾') : '…'}</button></div>${detail}`;
  }
}
