// ETF 선택 QAOA 연구 보고 — structured pptxgenjs deck (theme, layouts, sections, notes)
const pptxgen = require("pptxgenjs");
// apply_theme.js writes THEME's colours and fonts into the theme part (pptx skill); set APPLY_THEME to its path
const { applyTheme } = require(process.env.APPLY_THEME ||
  "/home/Tail/.claude/skills/synced/24b6895f-7b00-4bc4-ba5d-c7787f258c12_29a5a7f7-d65c-4cfc-9f25-fa958a37de75/pptx/scripts/apply_theme.js");

const OUT = process.argv[2] || "deck.pptx";
const THEME = {
  name: "ETF QAOA Report",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "16213A", lt1: "FFFFFF", dk2: "46505F", lt2: "EEF1F5",
    accent1: "1F5FCC", accent2: "A84B0C", accent3: "5E6573", accent4: "8FB4F5",
    accent5: "DCE2EB", accent6: "C9D3E3", hlink: "1F5FCC", folHlink: "6B4FA0",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "ETF 선택 QAOA 연구 보고";
pres.author = "norma-qaoa";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const W = 13.333, M = 0.6, CW = W - 2 * M;

// ---------------------------------------------------------------- layouts
const eyebrowPh = (color) => ({ placeholder: { options: { name: "eyebrow", type: "body", x: M, y: 0.42, w: CW, h: 0.35, fontSize: 12, bold: true, color, charSpacing: 1, margin: 0, valign: "top" }, text: "" } });
const titlePh = (color) => ({ placeholder: { options: { name: "title", type: "title", x: M, y: 0.78, w: CW, h: 0.85, fontSize: 28, bold: true, color, margin: 0, valign: "top", align: "left" }, text: "" } });
const footPh = (color) => ({ placeholder: { options: { name: "foot", type: "body", x: M, y: 6.92, w: 11.2, h: 0.32, fontSize: 10, color, margin: 0, valign: "top" }, text: "" } });

pres.defineSlideMaster({
  title: "COVER", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: M + 0.2, y: 2.05, w: 10, h: 0.4, fontSize: 14, bold: true, color: C.accent4, charSpacing: 1, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M + 0.2, y: 2.55, w: 11, h: 1.9, fontSize: 48, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M + 0.2, y: 4.55, w: 11, h: 0.6, fontSize: 18, color: C.accent6, margin: 0, valign: "top" }, text: "" } },
    { placeholder: { options: { name: "foot", type: "body", x: M + 0.2, y: 6.6, w: 11.5, h: 0.4, fontSize: 11, color: C.accent6, margin: 0 }, text: "" } },
  ],
});
for (const [name, bg] of [["CONTENT", C.background1], ["CONTENT_ALT", C.background2]]) {
  pres.defineSlideMaster({
    title: name, background: { color: bg },
    objects: [eyebrowPh(C.accent1), titlePh(C.text1), footPh(C.accent3)],
    slideNumber: { x: W - M - 0.6, y: 6.92, w: 0.6, h: 0.32, fontSize: 10, color: C.accent3, align: "right" },
  });
}
pres.defineSlideMaster({
  title: "STATEMENT", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: M + 0.2, y: 1.2, w: 10, h: 0.4, fontSize: 14, bold: true, color: C.accent4, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M + 0.2, y: 1.7, w: CW - 0.4, h: 1.9, fontSize: 32, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
  slideNumber: { x: W - M - 0.6, y: 6.92, w: 0.6, h: 0.32, fontSize: 10, color: C.accent6, align: "right" },
});

// ---------------------------------------------------------------- helpers
let sectionTitle = "";
function section(t) { pres.addSection({ title: t }); sectionTitle = t; }
function slide(master, eyebrow, title, foot, notes) {
  const s = pres.addSlide({ masterName: master, sectionTitle });
  if (eyebrow) s.addText(eyebrow, { placeholder: "eyebrow" });
  if (title) s.addText(title, { placeholder: "title" });
  if (foot) s.addText(foot, { placeholder: "foot" });
  if (notes) s.addNotes(notes);
  return s;
}
function lead(s, text, y = 1.62) {
  s.addText(text, { x: M, y, w: CW, h: 0.45, fontSize: 16, color: C.text2, margin: 0, isTextBox: true, valign: "top", objectName: "lead" });
}
function bullets(s, items, x, y, w, h, color = C.text2, size = 15) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 18 }, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontSize: size, color, margin: 0, valign: "top", isTextBox: true, objectName: "bullets" });
}
// table: rows of cells; a cell is a string or {t, c: "ok"|"hl"|"dim"}
function table(s, header, rows, x, y, w, colW, size = 14, rowH = 0.42) {
  const tone = { ok: C.accent1, hl: C.accent2, dim: C.accent3 };
  const hdr = header.map((h) => ({ text: h, options: { bold: true, fill: { color: C.accent5 }, color: C.text1 } }));
  const body = rows.map((r) => r.map((c) => typeof c === "string"
    ? { text: c, options: { color: C.text1 } }
    : { text: c.t, options: { color: tone[c.c] } }));
  s.addTable([hdr, ...body], { x, y, w, colW, fontSize: size, fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.75, color: "C9CFD8" }, margin: [4, 8, 4, 8], valign: "middle", rowH, objectName: "table" });
}
function card(s, x, y, w, h, title, body, fill, tag) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.12, objectName: "card" });
  let ty = y + 0.3;
  if (tag) {
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.3, w: 0.42, h: 0.42, fill: { color: tag.color }, line: { color: tag.color }, objectName: "card-badge" });
    s.addText(tag.text, { x: x + 0.3, y: y + 0.3, w: 0.42, h: 0.42, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    ty = y + 0.88;
  }
  s.addText(title, { x: x + 0.3, y: ty, w: w - 0.6, h: 0.45, fontSize: 18, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "card-title" });
  s.addText(body, { x: x + 0.3, y: ty + 0.5, w: w - 0.6, h: h - (ty - y) - 0.75, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "card-body", lineSpacingMultiple: 1.15 });
}
function stat(s, x, y, w, h, num, label, fill, numColor = C.accent1) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.12, objectName: "stat" });
  s.addText(num, { x: x + 0.3, y: y + 0.22, w: w - 0.6, h: 0.85, fontSize: 40, bold: true, color: numColor, margin: 0, valign: "top", isTextBox: true, objectName: "stat-num" });
  s.addText(label, { x: x + 0.3, y: y + 1.08, w: w - 0.6, h: h - 1.25, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "stat-label" });
}
function numberedRows(s, rows, y0, gap) {
  rows.forEach(([head, rest], i) => {
    const y = y0 + i * gap;
    s.addShape(pres.shapes.OVAL, { x: M, y, w: 0.46, h: 0.46, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `row-${i + 1}-badge` });
    s.addText(String(i + 1), { x: M, y, w: 0.46, h: 0.46, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: head + " ", options: { bold: true, color: C.text1 } }, { text: rest, options: { color: C.text2 } }],
      { x: M + 0.7, y: y - 0.02, w: CW - 0.7, h: gap - 0.12, fontSize: 16, margin: 0, valign: "top", isTextBox: true, objectName: `row-${i + 1}` });
  });
}

// ================================================================ achievements deck
const chartBase = () => ({
  titleFontSize: 14, titleColor: THEME.colors.dk1, titleFontFace: "+mn-lt",
  showValue: true, dataLabelFontSize: 11, dataLabelColor: THEME.colors.dk2, dataLabelFontFace: "+mn-lt",
  catAxisLabelColor: THEME.colors.dk2, valAxisLabelColor: THEME.colors.accent3, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  valGridLine: { color: "E3E7ED", size: 0.75 }, catGridLine: { style: "none" },
  legendPos: "b", legendFontSize: 12, legendColor: THEME.colors.dk2, legendFontFace: "+mn-lt",
});
function flow(s, steps, y, h, fill, numColor = C.accent1) {
  const aw = 0.36, gap = 0.14, n = steps.length;
  const w = (CW - (n - 1) * (aw + 2 * gap)) / n;
  steps.forEach(([t, b], i) => {
    const x = M + i * (w + aw + 2 * gap);
    card(s, x, y, w, h, t, b, fill, { text: String(i + 1), color: numColor });
    if (i < n - 1) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + w + gap, y: y + h / 2 - 0.18, w: aw, h: 0.36, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `arrow-${i + 1}` });
  });
}

// ---------------------------------------------------------------- 1. intro
section("개요와 핵심 성과");
{
  const s = slide("COVER", "연구 보고 · 2026-11-19", "양자-고전 하이브리드로\nETF 선택 최적해 찾기",
    "실제 ETF 가격 데이터 · NORMA padopauli(PADO PPS) · IBM 양자 하드웨어 · RQAOA",
    "실제 ETF 가격과, MaiQ 스펙의 구조를 본뜬 대리 목적식으로 만든 선택 문제를 양자 회로로 옮기고, GPU에서 회로 각도를 학습해 IBM 양자 하드웨어와 RQAOA로 풀었습니다. 찾은 해는 고전 최적화로 최적임을 증명했습니다.");
  s.addText("데이터에서 양자 회로, 하드웨어 실행, 최적성 증명까지 이어지는 전체 절차", { placeholder: "body" });
}
{
  const s = slide("CONTENT", "핵심 성과", "ETF 150개 문제까지 양자 알고리즘으로 최적해에 도달했다",
    "최적해 여부는 혼합정수계획(MILP)으로 증명했다. 출처: research/pado_pps (rqaoa_big*.jsonl, rqaoa_n20.jsonl, small.jsonl, ibm/)",
    "네 숫자가 이번 연구의 핵심입니다. RQAOA가 ETF 150개 문제까지 최적해를 찾았고, 어려운 N=20 문제 29개 중 27개를 맞혔습니다. 120큐비트 IBM 장비에서 100큐비트 회로를 실행했고, padopauli 각도 학습은 모든 조건에서 정확 학습 수준을 냈습니다.");
  const w = (CW - 0.35) / 2, h = 2.15;
  stat(s, M, 1.95, w, h, "N = 150", "RQAOA가 ETF 150개 중 6개를 고르는 문제의 최적해에 도달 (원래 결합, 결합 4배 모두)", C.background2);
  stat(s, M + w + 0.35, 1.95, w, h, "27 / 29", "고전 탐욕법이 실패하도록 만든 어려운 N=20 문제에서 RQAOA가 최적해를 찾은 수", C.background2);
  stat(s, M, 1.95 + h + 0.3, w, h, "100 큐비트", "IBM ibm_phoenix(120큐비트)에서 ETF 100개 문제 회로를 실행", C.background2);
  stat(s, M + w + 0.35, 1.95 + h + 0.3, w, h, "0.90 이상", "padopauli로 학습한 각도의 성능, 정확 학습 대비 (N=20 지도 전 조건)", C.background2);
}
{
  const s = slide("CONTENT_ALT", "사용한 데이터", "실제 ETF 가격과 파트너 스펙을 본뜬 목적식으로 문제를 만들었다",
    "목적식은 MaiQ가 확정한 식이 아니다. 실제 적합도·공분산·가중치는 공동 확정 예정(D04). 가격 출처: Yahoo 공개 차트 API. 출처: build.py, bt.md, oos.md",
    "가격은 합성이 아닌 실제 시장 데이터입니다. 목적식은 MaiQ 스펙의 구조(점수와 중복 벌점, 6개 선택)를 따르되, MaiQ가 줄 적합도 대신 공개 가격으로 만든 모멘텀 점수를 썼습니다. 실제 적합도와 공분산을 받으면 같은 절차에 그 값만 넣으면 됩니다.");
  const w = (CW - 2 * 0.35) / 3;
  card(s, M, 1.95, w, 4.6, "ETF 가격 데이터", "2017-11 ~ 2026-11: ETF 148개\n2008-05 ~ 2016-10: ETF 101개\n일별 가격, 2017~2026년 매월 말 리밸런싱 108회", C.background1, { text: "1", color: C.accent1 });
  card(s, M + w + 0.35, 1.95, w, 4.6, "대리 목적식", "MaiQ 스펙 구조를 따른 식. 점수는 3·6·12개월 수익률 순위, 벌점은 ETF 쌍의 상관이다. N개 중 정확히 6개를 고른다.", C.background1, { text: "2", color: C.accent1 });
  card(s, M + 2 * (w + 0.35), 1.95, w, 4.6, "문제 크기", "N = 20 · 50 · 100 · 150\nN=150이면 가능한 6개 조합이 약 143억 개다. 결합을 4배로 키운 어려운 시험 문제도 따로 만들었다.", C.background1, { text: "3", color: C.accent1 });
}

// ---------------------------------------------------------------- 2. method
section("방법: 데이터에서 양자 회로까지");
{
  const s = slide("CONTENT", "문제를 양자 형태로", "ETF 하나를 큐비트 하나로, 최적 포트폴리오를 바닥 상태로",
    "z_i = −1이면 i번째 ETF를 고른다. 개수 제약(6개)은 벌점 λ로 넣었다.",
    "포트폴리오 선택 문제를 이징 모델로 바꾸면, 에너지가 가장 낮은 상태가 곧 최적 포트폴리오입니다. 양자 회로는 이 낮은 에너지 상태를 찾는 데 쓰입니다.");
  lead(s, "E(z) = Σ h_i z_i + Σ J_ij z_i z_j  (h: ETF 점수와 개수 벌점, J: 상관 벌점)");
  flow(s, [
    ["점수와 상관", "가격 데이터에서 ETF별 점수와 ETF 쌍의 상관을 계산한다."],
    ["이징 모델", "점수는 1차 항 h, 상관 벌점은 결합항 J가 된다."],
    ["큐비트 배치", "ETF 하나가 큐비트 하나. N=100이면 100큐비트 회로다."],
    ["최저 에너지 해", "에너지가 가장 낮은 비트열이 최적 6개 조합이다."],
  ], 2.45, 3.3, C.background2);
}
{
  const s = slide("CONTENT_ALT", "전체 절차", "학습, 실행, 증명을 하나의 절차로 묶었다",
    "GPU: AMD Instinct MI300X(192 GB). 양자 장비: IBM ibm_phoenix(120큐비트).",
    "각 단계가 독립적으로 검증되도록 만들었습니다. 특히 마지막 MILP 단계 덕분에 양자 알고리즘이 찾은 해가 진짜 최적인지 확인할 수 있습니다.");
  flow(s, [
    ["문제 생성", "실제 가격으로 목적식과 이징 문제를 만든다."],
    ["GPU 각도 학습", "고전 시뮬레이터 padopauli로 장비에 올릴 회로의 각도를 미리 학습한다."],
    ["양자 실행", "IBM 하드웨어 샘플링 또는 RQAOA로 해를 찾는다."],
    ["최적성 증명", "MILP로 그 해가 최적인지 증명한다."],
  ], 2.3, 3.4, C.background1);
}
{
  const s = slide("CONTENT", "padopauli · 양자 회로 시뮬레이터", "150큐비트 회로의 각도를 GPU에서 미리 학습한다",
    "capture = padopauli 각도의 추가 이득 ÷ 정확 학습 각도의 추가 이득. 기준 0.90. 출처: README.md §5, small.jsonl, large.jsonl, map.json",
    "padopauli는 문제를 직접 푸는 도구가 아니라, 양자 장비에 올릴 회로를 고전 컴퓨터에서 설계하고 학습하고 검증하는 시뮬레이터입니다. 150큐비트 상태벡터는 어떤 컴퓨터로도 저장할 수 없는데, padopauli는 파울리 경로를 절단해 이런 회로의 기대값과 기울기를 계산합니다. 장비 시간을 학습에 쓰지 않아도 되는 것이 장점입니다. 풀이 속도로는 고전 탐색과 경쟁하지 않습니다.");
  lead(s, "문제를 직접 푸는 도구가 아니라, 장비에 올릴 회로를 고전 컴퓨터에서 설계·학습·검증하는 시뮬레이터다.");
  const w = (CW - 2 * 0.35) / 3;
  stat(s, M, 2.2, w, 1.75, "9 / 9 조건", "w=5에서 인스턴스 10개가 모두 통과한 조건", C.background2);
  stat(s, M + w + 0.35, 2.2, w, 1.75, "0.995 이상", "p=2에서의 capture (모든 조건)", C.background2);
  stat(s, M + 2 * (w + 0.35), 2.2, w, 1.75, "30초 이하", "N=150 회로까지 컴파일 시간", C.background2);
  table(s, ["문제 크기", "학습한 깊이 (결합 차수 d=3)", "큰 N 수렴 점검 (w=6 대비 차이)"], [
    ["N=50", "p ≤ 5", "p=2 0.0004, p=3 0.013"],
    ["N=100", "p ≤ 4", "p=2 0.0001"],
    ["N=150", "p ≤ 3", "p=2 0.0001"],
  ], M, 4.3, CW, [2.6, 4.6, 4.93]);
}
{
  const s = slide("CONTENT_ALT", "IBM 양자 하드웨어 실행", "100큐비트 회로까지 실제 양자 장비에서 돌렸다",
    "2026-11-09, 회로당 10,000샷, 동적 디커플링과 twirling 사용. 출처: README.md §8, ibm/ (작업 2건)",
    "padopauli로 학습한 각도를 그대로 하드웨어에 올렸습니다. N=20에서는 하드웨어 QAOA 샘플이 두 비교군보다 좋은 해를 더 많이 냈고, 깊이를 늘릴수록 좋아졌습니다. 모든 회로에서 최종 최선해는 기준 목적식의 최적해였습니다.");
  s.addChart(pres.charts.BAR, [
    { name: "IBM 하드웨어 QAOA", labels: ["p=1", "p=2", "p=3"], values: [0.36, 0.45, 0.54] },
    { name: "점수순 배정", labels: ["p=1", "p=2", "p=3"], values: [0.33, 0.40, 0.45] },
    { name: "균등 무작위", labels: ["p=1", "p=2", "p=3"], values: [0.26, 0.26, 0.26] },
  ], {
    x: M, y: 1.9, w: 7.0, h: 4.75, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4, "B8C0CC"], ...chartBase(),
    showTitle: true, title: "N=20: 기준 목적식 상위 1%에 든 샷 비율", dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
    valAxisMaxVal: 0.6, valAxisLabelFormatCode: "0.0", showLegend: true, objectName: "chart-hw-n20",
  });
  bullets(s, [
    "N=20에서 하드웨어 QAOA가 두 비교군보다 높고, 깊이 p를 늘릴수록 올라갔다.",
    "N=20·50·100의 모든 회로에서 샘플을 6개로 보정한 최선해가 기준 목적식의 최적해였다.",
    "노이즈 없는 계산 대비 에너지 유지율은 N=20에서 0.87~0.94다.",
  ], 7.95, 2.1, 4.78, 4.4, C.text2, 15);
}
{
  const s = slide("CONTENT", "IBM 하드웨어 · 결합이 강한 문제", "하드웨어에서도 깊은 회로일수록 좋은 해가 나왔다",
    "결합 4배 N=20 인스턴스 3개, 보정 없는 원시 샷. 무작위로 뽑으면 0.001. 출처: README.md §8",
    "결합을 키워 고전 탐욕법이 실패하는 문제입니다. 하드웨어 샘플의 9~31%가 에너지 상위 0.1%에 들었습니다. 무작위보다 90~310배 높고, 세 인스턴스 모두 p=1보다 깊은 회로가 나았습니다.");
  const hw = [[0.10, 0.22, 0.18, 0.12], [0.10, 0.18, 0.16, 0.31], [0.09, 0.13, 0.16, 0.23]];
  s.addChart(pres.charts.BAR, [0, 1, 2].map((i) => ({ name: ["s5", "s10", "s12"][i], labels: ["p=1", "p=2", "p=3", "p=4"], values: hw[i] })), {
    x: M, y: 1.9, w: 7.6, h: 4.75, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4, "7F8A99"], ...chartBase(),
    showTitle: true, title: "IBM 하드웨어: 에너지 상위 0.1%에 든 샷 비율", dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
    valAxisMaxVal: 0.35, valAxisLabelFormatCode: "0.00", showLegend: true, objectName: "chart-hw-k4",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.75, "90~310배", "무작위 샘플 대비 상위 0.1% 비율", C.background2);
  stat(s, x, 4.0, w, 1.75, "최대 13개", "10,000샷 중 정확한 바닥 상태를 맞힌 샷 (무작위 기대값 0.01개)", C.background2);
}

// ---------------------------------------------------------------- 3. RQAOA
section("RQAOA: 최적해에 도달한 양자 알고리즘");
{
  const s = slide("CONTENT_ALT", "RQAOA 원리", "QAOA 상관값으로 확실한 결정부터 하나씩 내린다",
    "Bravyi 외, PRL 125, 260505 (2020). 1차 항이 있는 문제로 확장해 구현: research/pado_pps/rqaoa.py",
    "표준 QAOA는 샘플에서 최적해가 나오길 기다리지만, RQAOA는 상관값의 부호만 맞으면 됩니다. 그래서 같은 얕은 회로로도 훨씬 자주 최적해에 닿습니다.");
  flow(s, [
    ["QAOA 학습", "남은 변수로 깊이 p 회로를 학습한다."],
    ["상관값 계산", "⟨Z_i⟩와 ⟨Z_i Z_j⟩를 padopauli로 구한다."],
    ["하나 결정", "가장 확실한 변수를 고정하거나 둘을 묶는다."],
    ["반복 후 마무리", "10개가 남으면 전수 탐색하고 거꾸로 대입한다."],
  ], 2.3, 3.4, C.background1);
}
{
  const s = slide("CONTENT", "RQAOA · 어려운 N=20 문제", "어려운 문제 29개 중 27개에서 최적해를 찾았다",
    "결합 4배 N=20 인스턴스 29개. 표준 QAOA 확률은 인스턴스 3개 기준. 출처: rqaoa_n20.jsonl, maqaoa.jsonl",
    "같은 문제에서 표준 QAOA로 샘플링하면 최적해가 나올 확률이 0.2% 이하입니다. RQAOA는 같은 깊이의 회로 정보로 29개 중 26~27개를 정확히 맞혔고, 놓친 문제도 최적값과 1.4% 이내였습니다.");
  s.addChart(pres.charts.BAR, [
    { name: "최적해 도달 비율", labels: ["표준 QAOA 샘플링 (p=1~3, 최대)", "RQAOA p=2", "RQAOA p=1"], values: [0.23, 89.7, 93.1] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.75, barDir: "bar", barGapWidthPct: 45,
    chartColors: [THEME.colors.accent1], ...chartBase(),
    showTitle: true, title: "최적해 도달 (%)", dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
    valAxisMaxVal: 100, valAxisLabelFormatCode: "0", showLegend: false, objectName: "chart-rqaoa-n20",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.75, "1.4% 이내", "최적해를 놓친 경우의 에너지 차이", C.background2);
  stat(s, x, 4.0, w, 1.75, "100% 일치", "padopauli와 정확 계산이 고른 변수 (29개 문제, 모든 단계)", C.background2);
}
{
  const s = slide("CONTENT_ALT", "RQAOA · 실제 크기 문제", "ETF 50·100·150개 문제 6개 모두에서 최적해를 찾고 증명했다",
    "다시 맞춘 λ, 절단 가중치 w=8. 정답은 MILP로 증명한 최적해. p=2 시간은 AMD MI300X GPU 시뮬레이션 기준. 출처: rqaoa_big.jsonl, rqaoa_big_p2.jsonl",
    "실제 데이터로 만든 ETF 50개, 100개, 150개 문제 6개 모두에서 RQAOA가 찾은 6개 조합이 MILP로 증명한 최적해와 정확히 같았습니다. 세 문제는 p=1로 풀었고, p=1에서 놓친 세 문제는 회로 깊이를 늘린 p=2로 다시 풀어 모두 최적해를 찾았습니다. ETF 150개 결합 4배 문제는 p=1에서 에너지 차이가 8.3%였던 문제입니다.");
  table(s, ["문제", "RQAOA 결과", "MILP 최적해와 비교", "소요 시간"], [
    ["ETF 50개, 원래 결합", { t: "최적해 도달 (p=1)", c: "ok" }, "같은 6개 조합", "17초"],
    ["ETF 50개, 결합 4배", { t: "최적해 도달 (p=1)", c: "ok" }, "같은 조합", "25초"],
    ["ETF 100개, 원래 결합", { t: "최적해 도달 (p=1)", c: "ok" }, "같은 6개 조합", "84초"],
    ["ETF 100개, 결합 4배", { t: "최적해 도달 (p=2)", c: "ok" }, "같은 6개 조합", "725초"],
    ["ETF 150개, 원래 결합", { t: "최적해 도달 (p=2)", c: "ok" }, "같은 6개 조합", "1,203초"],
    ["ETF 150개, 결합 4배", { t: "최적해 도달 (p=2)", c: "ok" }, "같은 6개 조합", "1,531초"],
  ], M, 1.95, CW, [3.3, 3.2, 3.2, 2.43], 15, 0.5);
  bullets(s, [
    "p=1로 못 푼 세 문제(100개 결합 4배, 150개 두 문제)를 p=2가 모두 풀었다. 깊이를 늘리는 효과가 실제로 나타났다.",
  ], M, 5.65, CW, 1.0, C.text2, 15);
}

{
  const s = slide("CONTENT", "RQAOA · 실무형 목적식", "실무형 평균-분산 식에서도 최적해에 도달했다",
    "목적식: −(평균 점수) + γ·(연율 분산), Ledoit–Wolf 공분산. 150개 γ=12는 5개 최적해 기준. 출처: mv.py, rqaoa_mv.jsonl",
    "마코위츠형 평균-분산 식은 실무에서 가장 널리 쓰는 포트폴리오 목적식이고, 파트너 스펙의 위험 항(공분산)과 같은 형태입니다. 모든 ETF 쌍이 결합된 식이라 p=1 QAOA 상관값을 닫힌 식으로 정확히 계산했습니다(상태벡터와 1e-16 이내 일치). 6개 문제 중 3개에서 MILP로 증명한 최적 조합을 정확히 찾았고, 나머지도 최적 조합과 3~5개가 겹쳤습니다. 위험 가중치가 큰 γ=12에서 더 어려웠습니다.");
  lead(s, "같은 가격 데이터, 공분산 위험 항. 정답은 MILP로 증명한 최적 조합(4초 이내).");
  table(s, ["문제", "RQAOA p=1 결과", "최적 조합과 비교", "소요 시간"], [
    ["ETF 50개, γ=4", { t: "최적해 도달", c: "ok" }, "같은 6개 조합", "9초"],
    ["ETF 50개, γ=12", "근사해", "5개 선택, 4개 일치", "6초"],
    ["ETF 100개, γ=4", { t: "최적해 도달", c: "ok" }, "같은 6개 조합", "33초"],
    ["ETF 100개, γ=12", "근사해", "4개 선택, 3개 일치", "57초"],
    ["ETF 150개, γ=4", "근사해", "6개 중 5개 일치", "406초"],
    ["ETF 150개, γ=12", { t: "최적해 도달", c: "ok" }, "같은 5개 조합", "380초"],
  ], M, 2.2, 8.3, [2.2, 2.4, 2.4, 1.3], 14, 0.5);
  const x = 9.25, w = W - M - x;
  stat(s, x, 2.2, w, 1.75, "3 / 6", "MILP 최적 조합을 정확히 찾은 문제", C.background2);
  stat(s, x, 4.15, w, 2.1, "−30%", "ETF 100개 최적 조합의 변동성 (평균-분산 8.5%, 대리 목적식 12.2%)", C.background2);
}

{
  const s = slide("CONTENT_ALT", "풀이 방법 비교", "양자 상관값이 같은 절차의 고전 규칙보다 나은 결정을 냈다",
    "41개 문제(N=20 29개, 대리 목적식 6개, 평균-분산 6개). 다중 시작: 내림 200회·교환 31회·담금질 20회. p=2 재시도는 평균-분산 문제에는 계산량 때문에 못 했다. 출처: compare.md",
    "같은 41개 문제를 고전 방법으로도 풀었습니다. 고전 순차 고정은 RQAOA와 절차가 같고 결정 근거만 다릅니다. QAOA 상관값 대신 계수 자체를 봅니다. p=1 기준으로 RQAOA가 33개, 고전 순차 고정이 29개를 맞혔고, RQAOA만 맞힌 문제가 6개, 고전 순차 고정만 맞힌 문제가 2개였습니다. 양자 상관값이 결정에 실제로 기여했다는 근거입니다. p=1에서 놓친 문제를 p=2로 다시 풀면 37개가 됩니다. 다만 이 크기에서는 여러 시작점에서 반복하는 고전 탐색이 41개를 모두 1.6초 안에 풀었습니다. RQAOA는 결정을 되돌릴 수 없는 순차 방식이라 이보다 약합니다. padopauli는 풀이 속도 경쟁용이 아니라 회로 설계·학습용 시뮬레이터입니다.");
  s.addChart(pres.charts.BAR, [
    { name: "최적해 도달 (41개 중)", labels: ["탐욕법 (1회)", "고전 순차 고정", "RQAOA p=1", "RQAOA p=1, 실패 시 p=2", "고전 다중 시작 탐색"], values: [22, 29, 33, 37, 41] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.75, barDir: "bar", barGapWidthPct: 45,
    chartColors: [THEME.colors.accent1], ...chartBase(),
    showTitle: true, title: "최적해에 도달한 문제 수 (41개 중)", dataLabelPosition: "outEnd", dataLabelFormatCode: "0",
    valAxisMaxVal: 45, valAxisMinVal: 0, valAxisLabelFormatCode: "0", showLegend: false, catAxisOrientation: "maxMin", objectName: "chart-solvers",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.75, "6 대 2", "RQAOA만 맞힌 문제 대 고전 순차 고정만 맞힌 문제", C.background1);
  stat(s, x, 4.0, w, 2.1, "1.6초 이하", "고전 다중 시작 탐색이 41개를 모두 푸는 시간. 이 크기는 고전으로도 쉽다", C.background1, C.accent2);
}

// ---------------------------------------------------------------- 4. trust
section("검증 체계와 포트폴리오 개선");
{
  const s = slide("CONTENT", "검증 체계", "결과를 믿을 수 있게 만드는 장치를 갖췄다",
    "출처: mip.py, mip_result.json, rqaoa.py, large.py, cand_prereg.md, oos_prereg.md",
    "양자 결과는 검증 없이는 설득력이 없습니다. 이번 연구에서는 최적성 증명, 계산 일치 확인, 이상값 차단, 사전등록 백테스트의 네 가지 장치를 갖췄습니다. 이 장치 덕분에 개수 벌점 λ 설정의 문제도 찾아 고쳤습니다.");
  const w = (CW - 0.35) / 2, h = 2.15;
  card(s, M, 1.95, w, h, "최적성 증명", "MILP로 ETF 150개 문제의 최적해를 2.5초 안에 증명한다. 양자 알고리즘의 답을 바로 채점할 수 있다.", C.background2, { text: "1", color: C.accent1 });
  card(s, M + w + 0.35, 1.95, w, h, "계산 일치 확인", "padopauli 결과를 정확 계산과 대조했다. RQAOA 29개 문제의 모든 결정이 일치했다.", C.background2, { text: "2", color: C.accent1 });
  card(s, M, 1.95 + h + 0.3, w, h, "이상값 차단", "GPU 메모리 한계에서 생기는 잘못된 값을 찾아내고, 160 GB를 넘은 계산은 자동으로 제외한다.", C.background2, { text: "3", color: C.accent1 });
  card(s, M + w + 0.35, 1.95 + h + 0.3, w, h, "사전등록 백테스트", "식 수정안과 판정 규칙을 실행 전에 고정하고, 2008~2016년 새 데이터로 독립 검증했다.", C.background2, { text: "4", color: C.accent1 });
}
{
  const s = slide("CONTENT_ALT", "포트폴리오 개선 후보", "공분산 기반 위험 항이 네 구간 모두에서 앞섰다",
    "기준 목적식(대리 목적식) 대비 샤프비율 차이. 결과를 본 뒤의 관찰이라 새 데이터로 확인이 필요하다. 출처: cand.md, oos.md",
    "문헌에서 가져온 수정안 중 공분산 기반 위험 항은 약한 설정과 중간 설정 모두 네 구간에서 기준 목적식보다 샤프비율이 높았습니다. 가장 일관된 개선 방향이고, MaiQ의 실제 데이터로 확인하는 것이 다음 단계입니다.");
  const labels = ["2008~2012", "2012~2016", "2017~2023", "2023~2026"];
  s.addChart(pres.charts.BAR, [
    { name: "공분산 위험 항, 약함", labels, values: [0.18, 0.16, 0.19, 0.12] },
    { name: "공분산 위험 항, 중간", labels, values: [0.32, 0.25, 0.06, 0.06] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.75, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4], ...chartBase(),
    showTitle: true, title: "기준 목적식 대비 샤프비율 개선", dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.00",
    valAxisMaxVal: 0.4, valAxisMinVal: 0, valAxisLabelFormatCode: "0.0", showLegend: true, objectName: "chart-cov-risk",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.75, "4 / 4 구간", "두 설정 모두 기준 목적식보다 높은 구간 수", C.background1);
  stat(s, x, 4.0, w, 1.75, "최대 +0.32", "구간별 샤프비율 개선 폭 +0.06 ~ +0.32", C.background1);
}

// ---------------------------------------------------------------- 5. next
section("다음 단계");
{
  const s = slide("CONTENT", "다음 단계", "실제 규모는 하드웨어로, 큰 문제는 하이브리드로", null,
    "파트너 스펙의 실제 규모는 후보 12~16개라 지금 장비에 그대로 올라갑니다. 150개를 넘는 문제는 ETF 하나에 큐비트 하나를 쓰는 지금 방식으로는 장비에 들어가지 않으므로, 쉬운 결정은 고전으로 줄이고 얽힌 핵심만 양자로 푸는 하이브리드가 현실적입니다. 양자의 차별점은 크기보다 고전 탐색이 어려워지는 문제 구조에서 찾아야 합니다.");
  numberedRows(s, [
    ["파트너 실제 규모로 하드웨어 실행.", "스펙 기준 후보 12개 중 6개(확대 16개)는 12~16큐비트라 지금 장비에 바로 올라간다. 결과는 고전 전수 계산으로 검증한다."],
    ["하드웨어 RQAOA.", "상관값을 샷 추정치로 바꿔 성공률을 먼저 보고, ibm_phoenix에서 N=20 RQAOA를 실행한다."],
    ["150개를 넘는 문제는 하이브리드로.", "RQAOA 결정의 80~95%는 고전 규칙으로도 맞는 확실한 고정이다. 이 부분은 고전으로 줄이고, 결합이 얽힌 핵심만 장비 크기에 맞춰 양자로 푼다. 큐비트 절약 인코딩도 검토한다."],
    ["양자에 유리한 문제 구조 찾기.", "고전 다중 시작 탐색의 성공률이 급격히 떨어지는 문제를 찾는다. 크기보다 결합 구조가 관건이다."],
    ["MaiQ 실제 목적식 적용.", "적합도·공분산·ETF 목록으로 목적식을 확정(D04)하고 같은 절차로 다시 푼다."],
  ], 1.95, 0.98);
}
{
  const s = slide("STATEMENT", "정리", "실제 ETF 데이터에서 출발해 양자 알고리즘으로 최적해를 찾고,\n그 해가 최적임을 증명하는 절차를 완성했다", null,
    "핵심은 세 가지입니다. 실제 데이터로 만든 문제, 150큐비트까지 학습되는 GPU 각도 학습과 실제 양자 하드웨어 실행, 그리고 MILP로 최적성을 증명하는 검증 체계입니다.");
  bullets(s, [
    "실제 ETF 148개·101개, 두 기간의 가격으로 만든 문제",
    "150큐비트 회로 각도 학습, 100큐비트 IBM 하드웨어 실행",
    "RQAOA로 ETF 150개 문제까지 최적해 도달, MILP로 증명",
  ], M + 0.2, 4.0, CW - 0.4, 2.4, C.accent6, 18);
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
