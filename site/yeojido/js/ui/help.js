// 도움말 (?) — 이 판에서 실제로 되는 조작만 적는다 (main.js 의 입력 처리와 같아야 한다).

import { h } from '../dom.js';
import { iconEl } from '../icons.js';
import { openModal, closeModal, isOpen } from './modal.js';

const k = (...keys) => keys.map((t) => h('kbd', t));
const row = (keys, text) => h('tr', h('th', { scope: 'row' }, keys), h('td', text));

export class Help {
  constructor(app) {
    this.app = app;
    this.el = h('div.modal.help', { hidden: true, 'aria-labelledby': 'help-title' },
      h('div.sheet',
        h('header.mhead', h('h2#help-title', '도움말', h('small', '지도 읽는 법과 조작')), h('button.x', { type: 'button', 'aria-label': '도움말 닫기', onclick: () => this.close() }, iconEl('close', 18))),
        h('div.help-body',
          h('ol.ideas',
            h('li', h('b', '먹에서 빛깔로'), '멀리서는 먹으로 찍은 지도다. 다가가면 칸마다 땅의 쓰임(숲·논·밭·시가지)이 빛깔로 배어 나온다.'),
            h('li', h('b', '렌즈는 덧찍기'), '갈피(왼쪽, 좁은 화면에서는 아래)에서 렌즈를 고르면 그 통계가 먹판 위에 한 판 더 찍힌다. 범례에서 범위를 고르면 그 칸만 남는다.'),
            h('li', h('b', '층은 배율 따라'), '불가사의·자원·기반시설 아이콘은 다가갈수록 늘어난다. 층 단추(오른쪽)로 묶음을 켜고 끈다.')),
          h('div.cols',
            h('section', h('h3', '지도'),
              h('table.keys', h('tbody',
                row('끌기', '지도 옮기기 (손가락 하나)'),
                row('휠 · 두 손가락', '확대·축소'),
                row('두 번 누르기', '그 자리로 두 배 확대'),
                row('고을 이름', '고을 장 열기'),
                row('아이콘 · 교역로', '항목 장 열기'),
                row('시도 이름', '시도 장 열기'),
                row('빈 땅', '마우스: 그 칸이 속한 고을 장. 손가락: 칸 띠가 먼저 뜨고, 거기서 고을 장·시도 장으로'),
                row('바다', '고른 것 풀기')))),
            h('section', h('h3', '글쇠'),
              h('table.keys', h('tbody',
                row(k('←', '↑', '→', '↓'), '옮기기 (지도에 초점이 있을 때)'),
                row(k('W', 'A', 'S', 'D'), '옮기기'),
                row(k('+', '−', '0'), '확대 · 축소 · 전도로'),
                row(k('/'), '찾기'),
                row([...k('L'), ' ', ...k('Shift', 'L')], '다음 렌즈 · 이전 렌즈'),
                row(k('R'), '자원 층 켜고 끄기'),
                row(k('?'), '이 도움말'),
                row(k('Esc'), '맨 위에 뜬 것부터 하나씩 닫기: 창 → 메뉴 → 범례에서 고른 범위 → 장'),
                row(k('Tab'), '위 장부(순위 보고서) · 갈피 · 층 · 장으로 차례로'))))),
          h('section.more', h('h3', '더'),
            h('ul',
              h('li', h('b', '나라 장부'), ' — 위쪽 숫자(인구·산출 등)를 누르면 순위 보고서가 열린다. "대한민국"을 누르면 전국 장.'),
              h('li', h('b', '공유'), ' — 지금 화면의 링크를 복사하거나, 출처가 찍힌 그림(PNG)으로 저장한다.'),
              h('li', h('b', '연감'), ' — 모든 규칙·정의·출처와 기준 시점. 산줄기를 어떻게 셈했는지도 여기 있다.'),
              h('li', h('b', 'koreaciv 판으로'), ' — 같은 자리·같은 렌즈·같은 선택을 든 채 기존판으로 건너간다. 주소(해시)가 두 판에서 같다.'),
              h('li', h('b', '글로 읽기'), ' — 화면 맨 처음의 "고을 목록으로 건너뛰기"로 가면 시도와 고을을 목록으로 읽고 고를 수 있다.'))),
          h('p.dim', '입력란에 글자를 넣는 동안에는 글쇠가 동작하지 않는다. 움직임을 줄이도록 설정한 기기에서는 날아가기·관성·바뀜 효과를 모두 끈다.'))));
    this.el.addEventListener('pointerdown', (e) => { if (e.target === this.el) this.close(); });
    document.getElementById('modal-root').append(this.el);
  }
  open() { if (isOpen(this.el)) return this.close(); openModal(this.el); }
  close() { closeModal(this.el); }
}
