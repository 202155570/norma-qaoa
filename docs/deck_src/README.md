# 발표자료 소스

`docs/`의 PPT 세 개를 만드는 pptxgenjs 스크립트다. 내용(문구, 수치, 차트 데이터)은 스크립트 안에 직접 적혀 있다. 수치를 바꾸려면 스크립트를 고쳐 다시 만든다.

| 스크립트 | 만드는 파일 | 내용 |
|---|---|---|
| `achievements.js` | `qaoa_achievements_2026-11-19.pptx` (24장) | 성과 중심 발표 |
| `research_report.js` | `qaoa_research_report_2026-11-19.pptx` (24장) | 사내 상세 보고 |
| `baselines.js` | `qaoa_vs_baselines_2026-11-24.pptx` (13장) | 양자 방법과 대조군(무작위, 점수 상위 k개) 비교 |

## 다시 만들기

```bash
mkdir -p /tmp/deckbuild && cd /tmp/deckbuild && npm install pptxgenjs@3.12.0
NODE_PATH=/tmp/deckbuild/node_modules node <repo>/docs/deck_src/achievements.js out.pptx
```

- 스크립트 마지막 단계에서 `apply_theme.js`(pptx 스킬)로 테마 색과 글꼴을 파일에 써 넣는다.
- 경로는 환경변수 `APPLY_THEME`으로 바꿀 수 있다. 기본값은 이 서버의 스킬 경로다.
- 글꼴은 맑은 고딕이다. LibreOffice로 렌더링하면 다른 한글 글꼴로 대신 그려져 글자 간격이 조금 다르다.
- 수치의 출처는 각 장의 각주에 있는 `research/pado_pps/` 결과 파일이다.
