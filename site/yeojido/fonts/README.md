# 신여지도 글꼴 · 제호 한자 · 낙관

모두 자체 호스팅이고 SIL Open Font License 1.1 이다. `python tools/yeojido/build_fonts.py` 가 이 폴더의 파일을 다시 만든다
(원본은 `tools/yeojido/fonts_src/`, 2026-11-27 에 받음). 연감은 `fonts.json` 을 읽어 글꼴 이름과 이용허락을 보여 준다.

| 파일 | 쓰임 | 원본 | 이용허락 |
|---|---|---|---|
| `Hahmlet-VF.subset.woff2` | 제목 · 고을 이름 · 큰 숫자 (`--serif`) | Hahmlet 1.002 가변(100–900), google/fonts `ofl/hahmlet/Hahmlet[wght].ttf` (커밋 c1eda92) | OFL 1.1 — `Hahmlet-OFL.txt`. 예약 글꼴 이름 없음 |
| `YeojidoSans-VF.subset.woff2` | 본문 · 표 · 단추 (`--sans`) | Pretendard Variable 1.309, orioncactus/pretendard `packages/pretendard/dist/public/variable/PretendardVariable.ttf` (커밋 7aeb069) | OFL 1.1 — `YeojidoSans-Pretendard-OFL.txt`. 예약 글꼴 이름 있음(아래) |
| `NotoSerifKR-VF.hanja.woff2` | 자료 속 한자 (CSS 별칭 `Yeojido Hanja`, 한자에만) | Noto Serif KR 2.003 가변, google/fonts `ofl/notoserifkr/NotoSerifKR[wght].ttf` | OFL 1.1 — `NotoSerifKR-OFL.txt`. 예약 글꼴 이름 없음 |
| `title-hanja.svg` (+ `title-hanja.woff2`) | 제호 곁글 한자 新輿地圖 | Yuji Syuku Regular, google/fonts `ofl/yujisyuku/YujiSyuku-Regular.ttf` | OFL 1.1 — `YujiSyuku-OFL.txt`. 예약 글꼴 이름 없음 |
| `seal.svg`, `seal-mask.svg` | 낙관 (한글 「신여지도」, 백문) | Hahmlet 굵기 900 의 윤곽 + 계산한 인변 | OFL 1.1 (Hahmlet) |
| `charset.txt` | 글자 범위 | KS X 1001 한글 2,350 + ASCII + 기호 + `site/data/*.json` · `site/yeojido/**` · `docs/YEOJIDO.md` 의 모든 글자 | — |

## Pretendard 의 예약 글꼴 이름

원본 LICENSE 첫머리: `Copyright (c) 2021, Kil Hyung-jin (https://github.com/orioncactus/pretendard), with Reserved Font Name 'Pretendard'.`
(바탕 글꼴의 예약 이름 'Source', 'Inter', 'M PLUS 1' 도 함께 적혀 있다.)
OFL 1.1 제3조는 수정본이 예약 글꼴 이름을 쓰지 못하게 한다. 글자를 줄인 파일은 수정본이므로
글꼴 안의 이름 레코드(1·3·4·6·16·25 와 가변 인스턴스 이름)를 `Yeojido Sans` / `YeojidoSans` 로 바꿨고, CSS 에서도 그 이름으로만 부른다.
저작권(0)·상표(7)·만든이(8·9)·이용허락(13·14) 레코드는 제2조에 따라 그대로 두었다. 짓는 스크립트가 이름에 예약 이름이 남으면 멈춘다.
화면이나 문서에서 이 글꼴을 가리킬 때는 "Pretendard 의 수정본(Yeojido Sans)"이라고 적는다.

## 한자 제호 바꾸기 (新輿地圖)

지금 것은 추사 김정희의 글씨가 **아니다**. 붓글씨 해서 글꼴 Yuji Syuku 에서 네 글자의 윤곽만 뽑은 것이다. 추사체라고 부르지 않는다.
진짜 글씨를 구하면 다음 가운데 하나로 바꾼다.

1. **파일만 바꾸기** — `title-hanja.svg` 를 같은 이름으로 덮어쓴다. 조건: 네 글자가 위에서 아래로 한 줄(세로로 긴 그림), 글자는 불투명·바탕은 투명
   (마스크로 쓰므로 빛깔은 무엇이든 된다. 투명 PNG 를 쓰려면 2번), viewBox 가 글자에 딱 붙을 것.
   가로세로 비가 달라지면 `css/fonts.css` 의 `--title-hanja-ratio` (지금 `974 / 3652`) 를 새 그림의 `가로 / 세로` 로 고친다.
2. **다른 파일을 가리키기** — `css/fonts.css` 의 `--title-hanja: url("../fonts/새파일.svg")` (또는 `.png`, `.webp`) 과 `--title-hanja-ratio` 를 고친다.
3. **연감의 표시 고치기** — `fonts.json` 에서 `"role": "제호 곁글 한자 新輿地圖"` 항목의 `family_shown` · `author` · `licence` · `source_url` · `note` 를 새 글씨의 것으로 고친다.
   `build_fonts.py` 를 다시 돌리면 `title-hanja.svg` 와 `fonts.json` 이 다시 쓰이므로, 손으로 바꾼 뒤에는 스크립트의 `build_title_hanja()` 호출과 그 항목을 빼거나 함께 고친다.

`--title-hanja` 와 `--seal` 은 `css/` 안의 스타일시트에서만 `var()` 로 쓴다 (사용자 정의 속성 안의 상대 주소는 쓰는 곳 기준으로 풀린다). 다른 곳에서는 `.title-hanja` `.seal` `.seal-ink` 클래스를 쓴다.
캔버스(내보내기)에서는 `new Image()` 로 `fonts/title-hanja.svg` · `fonts/seal.svg` 를 불러 그린다.

## 고른 까닭과 버린 후보

**한자 제호**: 네 글자(U+65B0 U+8F3F U+5730 U+5716)가 모두 있고 정자(번체)인지 글꼴 파일에서 확인하고 그려서 눈으로 보았다 (`tools/yeojido/fonts_src/cand_compare*.png`).
- Yuji Syuku / Yuji Boku / Yuji Mai (OFL, 원작자 배포, 예약 이름 없음): 네 글자 모두 있음. 한자 꼴은 셋이 거의 같아 기본형 Syuku 를 골랐다.
- Ma Shan Zheng · Zhi Mang Xing · Liu Jian Mao Cao · Long Cang (OFL): 간체 글꼴이라 輿 · 圖 가 없다. 탈락.
- Bakudai(莫大毛筆) · MasaFont (max32002): 네 글자 모두 있고 붓맛은 더 세다. 그러나 青柳衡山의 무료 글꼴을 제3자가 고쳐 OFL 로 내놓은 것이고,
  원 배포처(opentype.jp)의 조건은 "무료 · 상용 가능 · 제한 없음"일 뿐 개작·재허락을 밝히지 않는다. 허락의 사슬을 확인하지 못해 쓰지 않았다 (MasaFont 저장소에는 이용허락 파일도 없다).

**낙관**: 한자 전서 낙관은 접었다.
- LXGW Seal (OFL 1.1): 수록 글자가 적어 新 · 地 만 있고 輿 · 圖 가 없다.
- 開元小篆 Kaiyuan Small Seal (OFL 1.1): 《설문해자》 영인본을 따서 만드는 중인 미발행 글꼴로, 글자 맞춤을 한 자씩 검수하는 단계다(승인 1,197자). 네 글자의 맞춤을 믿을 근거가 없다.
- 崇羲篆體 같은 CC BY-ND 글꼴은 윤곽을 뽑아 고치는 것이 '변경 금지'에 걸릴 수 있어 살펴보지 않았다.
그래서 한글 낙관으로 물러섰다. 글자 윤곽은 Hahmlet 900 에서 그대로 뽑아 칸을 채우게 늘렸고, 인변과 이 빠진 자국은 정해진 수식으로 만든다(난수 없음, 손으로 그린 선 없음).

## 원본에 없는 글자

`build_fonts.py` 가 돌 때마다 찍고 `fonts.json` 의 `missing` 에 남긴다. 지금은:
- 한자: Hahmlet · Pretendard 에는 한자가 없다. 자료에 나오는 한자(조선왕릉 이름 등 70여 자)는 Noto Serif KR 서브셋이 맡는다.
- 기호: Hahmlet 에 없는 기호(※ ℃ ㎢ ① 「」 등)는 글꼴 차례에 따라 Yeojido Sans 로 넘어간다. 두 글꼴 모두에 없는 것은 `∙ ∼ ▴ ▸ ▾ ◂ ◎ ･` 와 시계·저울 그림문자 — 화면에서는 쓰지 않는다.
- 그림문자(이모지): 자료 JSON 의 `emoji` 필드에 있으나 신여지도는 쓰지 않는다.
