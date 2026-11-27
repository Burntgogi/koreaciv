// 조작 안내 (? 키, 상단 ? 단추): 실제로 동작하는 조작만 적는다.

export class Help {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('help');
    this.el.addEventListener('click', (e) => {
      if (e.target === this.el || e.target.closest('[data-close]')) return this.close();
      const pb = e.target.closest('[data-preset]');
      if (pb) { this.close(); this.app.applyPreset(pb.dataset.preset); }
    });
  }

  isOpen() { return !this.el.hidden; }

  // 데이터 기준 시점 6선 (nation.json presets, 빌드가 극값 규칙으로 고름)
  presetsHTML() {
    const P = this.app.nation.presets;
    if (!P || !P.items || !P.items.length) return '';
    const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
    return `<h3>데이터 기준 시점 6선 <small>자동 선정</small></h3><div class="presets">${P.items.map((p) => `<button type="button" data-preset="${esc(p.id)}" aria-label="${esc(`${p.title}, ${p.metric}, 선정 규칙 ${p.rule}`)}"><b>${esc(p.title)}</b> <span>${esc(p.metric)}${p.lens && this.app.lensById.get(p.lens) ? ' · ' + esc(this.app.lensById.get(p.lens).name) + ' 렌즈' : ''}</span><small>${esc(p.rule)}</small></button>`).join('')}</div>
      <p class="dim sm">${esc(P.rule)}</p>`;
  }

  toggle() { if (this.isOpen()) this.close(); else this.open(); }

  close() { this.el.hidden = true; }

  open() {
    this.app.share.close();
    const k = (t) => `<kbd>${t}</kbd>`;
    this.el.innerHTML = `<div class="sheet" role="dialog" aria-label="조작 안내"><button class="close" data-close title="닫기 (Esc)">×</button>
      <h2>조작 안내</h2>
      <div class="hcols">
        <section><h3>이동</h3><ul>
          <li>끌기 — 지도 옮기기 (터치: 한 손가락)</li>
          <li>휠 · 두 번 누르기 — 확대 (터치: 두 손가락 벌리기·오므리기)</li>
          <li>${k('←')}${k('↑')}${k('→')}${k('↓')} 또는 ${k('W')}${k('A')}${k('S')}${k('D')} — 옮기기</li>
          <li>${k('+')} ${k('−')} — 확대·축소</li>
          <li>오른쪽 아래 미니맵 — 누르거나 끌어서 그곳으로</li>
        </ul></section>
        <section><h3>탐색</h3><ul>
          <li>${k('/')} — 도시·시도·불가사의·발전소 찾기</li>
          <li>아래 렌즈 막대 — 묶음을 누르면 렌즈가 펼쳐진다. ${k('L')} 다음 렌즈, ${k('Shift')}+${k('L')} 이전 렌즈</li>
          <li>범례 눈금 위를 가리키거나 끌면 그 구간의 칸만 색이 남는다. 놓거나(터치는 두 번 누르면) 풀린다. 키보드는 범례에 초점을 두고 화살표·Enter, Esc 로 풀기</li>
          <li>순위 보고서의 행은 ${k('Tab')} 으로 옮겨 ${k('Enter')} 로 연다</li>
          <li>왼쪽 위 층 조작 — 아이콘을 눌러 묶음을 켜고 끄고, ▾ 로 종류별 세부. ${k('R')} 자원 켜고 끄기</li>
          <li>상단 수치(인구 · 고령 비율 · 소멸위험지수 · 다섯 산출) — 누르면 순위 보고서</li>
          <li>📤 공유 — 지금 화면 링크 복사, 그림 내려받기(정사각 1200×1200 · 와이드 1600×900). 메뉴는 ${k('↑')}${k('↓')} 로 고른다</li>
        </ul></section>
        <section><h3>패널 <small>세 가지</small></h3><ul>
          <li><b>도시·시도</b> — 깃발을 누르면 도시 패널(개요·경제·시설·교역·땅·행정 4탭, 고른 탭은 다른 도시로 옮겨도 남음), 시도 이름이나 깃발·아이콘이 없는 땅을 누르면 시도 패널. 탭 바에서 ${k('←')}${k('→')} 로 탭을 옮긴다</li>
          <li>다섯 산출 칸·특성 표시(예: 제조업 비중 ×2.6)·순위 막대 — 누르면 산식과 기준, 순위 막대는 바로 위·아래 순위 도시</li>
          <li><b>항목</b> — 지도 아이콘(불가사의·자원·기반시설)이나 교역로 선을 누르면 그 항목의 값·위치·선정 규칙·출처</li>
          <li><b>전국 보고서</b> — 상단 '기준' 칸. 순위 보고서의 행을 누르면 그 도시·시도 패널로</li>
          <li>값 옆 ⓘ 를 가리키거나 누르면 기준과 주의 문장이 나온다. 구역 아래 '기준과 주의'에 모아 둔다</li>
        </ul></section>
      </div>
      ${this.presetsHTML()}
      <p class="dim">${k('Esc')} 는 말풍선 → 그림 미리보기 → 도움말 → 공유 메뉴 → 찾기 → 연감 → 보고서 → 패널 순으로 하나씩 닫는다. 입력란에 글자를 넣는 동안에는 단축키가 동작하지 않는다.</p></div>`;
    this.el.hidden = false;
  }
}
