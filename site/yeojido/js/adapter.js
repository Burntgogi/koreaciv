// 자료 어댑터 — 화면 모듈이 자료를 읽는 단 하나의 문.
// ../data/*.json 의 모양(필드 이름·실림 꼴)은 js/adapter/ 안에서만 읽는다. 계약은 docs/YEOJIDO.md '어댑터' 참조.
export * from './adapter/core.js';
export * from './adapter/places.js';
export * from './adapter/reports.js';
export * from './adapter/sources.js';
export * from './adapter/layers.js';
