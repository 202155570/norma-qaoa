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
  const s = slide("COVER", "연구 보고 · 2026-11-24", "양자-고전 하이브리드로\nETF 선택 최적해 찾기",
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
    "결합 4배 N=20 인스턴스 3개, 보정 없는 원시 샷. 무작위로 뽑으면 상위 0.1%에 드는 비율은 0.1%. 출처: README.md §8",
    "결합을 키워 고전 탐욕법이 실패하는 문제입니다. 하드웨어 샘플의 9~31%가 에너지 상위 0.1%에 들었습니다. 무작위보다 90~310배 높고, 세 인스턴스 모두 p=1보다 깊은 회로가 나았습니다.");
  const hw = [[0.10, 0.22, 0.18, 0.12], [0.10, 0.18, 0.16, 0.31], [0.09, 0.13, 0.16, 0.23]];
  s.addChart(pres.charts.BAR, [0, 1, 2].map((i) => ({ name: ["s5", "s10", "s12"][i], labels: ["p=1", "p=2", "p=3", "p=4"], values: hw[i] })), {
    x: M, y: 1.9, w: 7.6, h: 4.75, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4, "7F8A99"], ...chartBase(),
    showTitle: true, title: "IBM 하드웨어: 에너지 상위 0.1%에 든 샷 비율 (무작위 0.1%)", dataLabelPosition: "outEnd", dataLabelFormatCode: "0%",
    valAxisMaxVal: 0.35, valAxisLabelFormatCode: "0%", showLegend: true, objectName: "chart-hw-k4",
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

// ---------------------------------------------------------------- 3b. hard problems
section("어려운 문제에서의 한계");
{
  const s = slide("CONTENT", "MILP가 느려지는 구조", "결합이 촘촘하고 강하며 부호가 섞이면 정확한 증명이 느려진다",
    "288문제: N=50·100·150 × k=6·15 × 쌍 항 3종 × 밀도 4 × 세기 4, HiGHS 단일 스레드 300초, 미증명 10개는 1시간 재실행. 출처: hard.md 결과 1~3",
    "MILP가 언제 느려지는지 찾으려고 목적식 구조를 바꿔 가며 288문제를 풀었습니다. 결합이 촘촘하고, 강하고, 부호가 섞이고, N과 k가 클수록 증명 시간이 늘었고 N=150, k=15에서는 1시간으로도 증명하지 못하는 문제가 나왔습니다. 반대로 실제 ETF 공분산으로 만든 평균-분산 식은 N=150에서도 10초 안에 증명됩니다. 실제 ETF 상관은 대부분 양수이고 소수 요인으로 설명되기 때문입니다.");
  lead(s, "상관에서 중앙값을 뺀 쌍 항(부호 섞임), 모든 쌍, 세기 ×16일 때의 증명 시간");
  table(s, ["", "k = 6", "k = 15"], [
    ["N = 50", "5.9초", "11.3초"],
    ["N = 100", "52.7초", "2,692초"],
    ["N = 150", "378초", { t: "1시간에 미증명 (갭 31%)", c: "hl" }],
  ], M, 2.25, 7.4, [1.8, 2.4, 3.2], 15, 0.55);
  const x = 8.4, w = W - M - x;
  stat(s, x, 2.1, w, 1.9, "278 / 288", "300초 안에 최적임을 증명한 문제", C.background2);
  stat(s, x, 4.25, w, 2.2, "10초 이내", "실무형 평균-분산 식(N=150)의 증명 시간. 실제 ETF 데이터는 쉬운 쪽에 있다", C.background2);
}
{
  const s = slide("CONTENT_ALT", "어려운 12문제 · 방법별 결과", "같은 문제에서 양자 방법은 최적해를 하나도 찾지 못했다",
    "MILP가 128~2,692초 걸려 증명한 가장 어려운 12문제(N=100·150). 양자 방법은 모두 고전 시뮬레이션, 각도는 정확 계산. SQA 설정은 12문제 중 2개로 골랐다. 출처: hard.md 결과 4~8",
    "MILP가 가장 오래 걸린 12문제를 여러 방법으로 풀었습니다. 정확히 k개를 유지하며 맞바꾸는 고전 탐색은 12문제 모두 1~3초 안에 최적해를 찾았습니다. RQAOA를 개수 세기와 빔으로 보강해도, 벌점이 필요 없는 XY 믹서 QAOA로 바꿔도 0/12였습니다. 양자 어닐링을 흉내 낸 SQA는 3/12였습니다.");
  s.addChart(pres.charts.BAR, [
    { name: "최적해 도달 (12개 중)", labels: ["개수 유지 스왑 탐색 (고전)", "개수 유지 SA (고전)", "SQA, 양자 어닐링 모형 (고전)", "병렬 템퍼링, 벌점 (고전)", "SA, 벌점 (고전)", "RQAOA p=1 (양자)", "RQAOA + 개수 세기 + 빔 (양자)", "XY 믹서 QAOA (양자)"], values: [12, 12, 3, 2, 0, 0, 0, 0] },
  ], {
    x: M, y: 1.9, w: 8.1, h: 4.85, barDir: "bar", barGapWidthPct: 40,
    chartColors: [THEME.colors.accent1], ...chartBase(),
    showTitle: true, title: "최적해에 도달한 문제 수 (12개 중)", dataLabelPosition: "outEnd", dataLabelFormatCode: "0",
    valAxisMaxVal: 13, valAxisMinVal: 0, valAxisLabelFormatCode: "0", showLegend: false, catAxisOrientation: "maxMin", catAxisLabelFontSize: 11, objectName: "chart-hard12",
  });
  const x = 9.05, w = W - M - x;
  stat(s, x, 2.0, w, 1.9, "0 / 12", "RQAOA 변형 5가지와 XY 믹서 QAOA 모두", C.background1, C.accent2);
  stat(s, x, 4.15, w, 2.3, "1~3초", "개수를 유지하는 고전 SA가 12문제를 모두 푼 시간 (문제당)", C.background1);
}
{
  const s = slide("CONTENT", "승패를 가른 요인", "결과를 가른 것은 양자냐 고전이냐보다 개수 제약을 다루는 방식이었다",
    "임베딩: 이상적인 Advantage 그래프에 완전 그래프 K_N을 올리고 실기기처럼 축척했다. 제어 오차 σ_J=0.02는 가정값이다. D-Wave 실기기는 QPU 시간이 없어 돌리지 못했다. 출처: hard.md 결과 6·8",
    "같은 담금질 기법이라도 정확히 k개를 유지하며 맞바꾸면 12/12, 개수를 벌점으로 넣고 한 비트씩 뒤집으면 0/12였습니다. 다른 k개 조합으로 가려면 개수가 틀린 상태를 거쳐야 하는데 벌점이 장벽이 되기 때문입니다. 양자 어닐러가 받는 입력이 바로 이 벌점 형태입니다. 칩에 올리면 사슬을 세게 잡아야 해서, 원래 목적식의 결합이 하드웨어 단위로 약 0.0001까지 작아집니다.");
  const w = (CW - 2 * 0.35) / 3;
  card(s, M, 2.0, w, 3.4, "개수 유지 이동: 12/12", "정확히 k개를 유지한 채 하나씩 맞바꾼다. 스왑 탐색과 SA 모두 12문제를 1~3초 안에 풀었다. XY 믹서는 이 이동을 양자로 구현한 것이다.", C.background2, { text: "1", color: C.accent1 });
  card(s, M + w + 0.35, 2.0, w, 3.4, "벌점 QUBO: 0~3/12", "개수를 벌점으로 넣으면 다른 조합으로 가는 길에 장벽이 생긴다. 한 비트 SA 0/12, 병렬 템퍼링 2/12, SQA 3/12. RQAOA는 벌점 때문에 46개를 고른 사례도 있었다.", C.background2, { text: "2", color: C.accent2 });
  card(s, M + 2 * (w + 0.35), 2.0, w, 3.4, "양자 어닐러: 정밀도 한계", "사슬 길이 10~14, 사슬을 세게 잡으면 목적식 결합이 약 0.0001로 줄어든다. 가정한 제어 오차 0.02를 넣으면 k개를 지킨 답이 하나도 없었다.", C.background2, { text: "3", color: C.accent2 });
  s.addText([{ text: "시사점 ", options: { bold: true, color: C.accent1 } }, { text: "양자 방법을 쓰려면 제약을 지키는 구조(XY 믹서, 제약 지원 솔버)가 전제다. 다만 같은 구조의 고전 탐색이 이미 수 초 만에 푼다.", options: { color: C.text1 } }],
    { x: M, y: 5.7, w: CW, h: 0.9, fontSize: 16, margin: 0, valign: "top", isTextBox: true, objectName: "takeaway" });
}
{
  const s = slide("CONTENT_ALT", "양자 샘플 + 고전 탐색", "양자 샘플은 깊을수록 좋아졌지만, 국소탐색과 합치면 이득이 사라졌다",
    "N=20, k=5 문제 40개, 정확한 상태벡터에서 측정 100회. 배수는 문제별 중앙값, 구간은 문제 단위 부트스트랩. 각도는 기대 비용 최소화로 학습. 출처: hard.md 결과 9",
    "작은 문제에서는 진짜 양자 측정 샘플을 뽑을 수 있습니다. 디키 상태에서 시작하는 완전 그래프 XY 믹서 QAOA는 깊이 p=3에서 최적해가 나올 확률이 무작위의 237배였습니다. 그런데 이 샘플을 국소탐색의 시작점으로 쓰면 성공률이 무작위 시작점과 1~2%p 안이고 구간이 0을 포함했습니다. 무작위 시작점에서 국소탐색을 돌리면 이미 76%가 최적해에 도달하기 때문입니다.");
  s.addChart(pres.charts.BAR, [
    { name: "XY 완전 그래프 믹서", labels: ["p=1", "p=2", "p=3"], values: [35, 103, 237] },
    { name: "XY 링 믹서", labels: ["p=1", "p=2", "p=3"], values: [6, 15, 24] },
    { name: "표준 QAOA (벌점)", labels: ["p=1", "p=2", "p=3"], values: [0.4, 0.7, 1.0] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.85, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4, "B8C0CC"], ...chartBase(),
    showTitle: true, title: "측정 1회에 최적해가 나올 확률, 무작위 대비 배수", dataLabelPosition: "outEnd", dataLabelFormatCode: "0.#",
    valAxisMaxVal: 270, valAxisMinVal: 0, valAxisLabelFormatCode: "0", showLegend: true, objectName: "chart-amplify",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "+1.3%p", "XY p=3 샘플을 시작점으로 쓴 국소탐색 성공률, 무작위 대비 (95% 구간 −1.1 ~ +3.6)", C.background1);
  stat(s, x, 4.2, w, 2.25, "약 30배", "무작위 시작 + 국소탐색의 성공률(76%)이 가장 좋은 양자 측정 1회의 성공률(2.6%)보다 높은 정도", C.background1, C.accent2);
}

{
  const s = slide("CONTENT", "크기 키우기 · N=16→28", "N이 커질수록 양자와 고전의 격차가 벌어졌다",
    "N마다 20문제(k=N/4, 쌍 항 강화 ×4·×16). 디키 시작 XY 완전 그래프 QAOA p=3, 무게 k 부분공간 정확 계산(N=28은 118만 차원, GPU). 고전은 무작위 시작 1,000개 + 스왑 국소탐색. 기하평균. 출처: hard.md 결과 10",
    "작은 문제는 양자 상태를 정확히 계산할 수 있어서, N을 16에서 28까지 키우며 추세를 봤습니다. 무작위 대비 배수는 150배에서 5,654배로 커졌지만 경우의 수가 더 빨리 늘어, 측정 1회에 최적해가 나올 확률은 8.2%에서 0.48%로 줄었습니다. 최적해를 한 번 보려면 13회에서 222회를 측정해야 합니다. 무작위 시작 국소탐색은 재시작 1.3회에서 1.65회로 거의 그대로였습니다. 격차는 10배에서 130배로 벌어졌고, 하이브리드 이득도 N=24부터 0과 구분되지 않았습니다.");
  const labels = ["N=16", "N=20", "N=24", "N=28"];
  s.addChart(pres.charts.LINE, [
    { name: "양자: 최적해를 한 번 보는 데 필요한 측정 수", labels, values: [13, 28, 80, 222] },
    { name: "고전: 필요한 국소탐색 재시작 수", labels, values: [1.29, 1.46, 1.64, 1.65] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.85, lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 8,
    chartColors: [THEME.colors.accent1, THEME.colors.accent2], ...chartBase(),
    showTitle: true, title: "최적해까지 필요한 시도 횟수 (로그 눈금)", dataLabelPosition: "t", dataLabelFormatCode: "General",
    valAxisLogScaleBase: 10, valAxisMinVal: 1, valAxisMaxVal: 1000, valAxisLabelFormatCode: "0", showLegend: true, objectName: "chart-scale",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "0.48%", "N=28에서 측정 1회에 최적해가 나올 확률 (p=3, N=16은 8.2%). 무작위 대비 배수는 커졌지만 확률은 줄었다", C.background2, C.accent2);
  stat(s, x, 4.2, w, 2.25, "+1.0%p", "N=28에서 양자 샘플을 시작점으로 쓴 국소탐색 성공률, 무작위 대비 (95% 구간 −1.4 ~ +3.4)", C.background2, C.accent2);
}
{
  const s = slide("CONTENT_ALT", "학습 기준 바꾸기 · CVaR", "CVaR로 양자 샘플은 약 2배 좋아졌지만, 격차는 약 50배다",
    "같은 80문제, 같은 회로(p=3). 각도만 기대 비용 대신 CVaR(비용이 낮은 쪽 10%의 평균)로 학습했다. 측정·재시작 수는 기하평균. 판정 기준은 실행 전 cvar.py에 고정. 출처: hard.md 결과 14",
    "크기 키우기에서 각도는 기대 비용으로 학습했습니다. 우리가 원하는 것은 최적해가 자주 나오는 것이므로, 비용이 낮은 쪽 10%의 평균(CVaR)으로 바꿔 학습했습니다. 실행 전에 N=24, 28에서 무작위 대비 배수가 중앙값 2배 이상 오르면 결론이 바뀐 것으로 보기로 정했고, 2.11배로 이 기준을 넘었습니다. 최적해까지 측정 수는 N=28에서 222회가 82회로 줄었습니다. 하지만 고전 재시작 수는 1.65회라서 격차는 130배에서 50배로 줄었을 뿐이고, 국소탐색과 합친 성공률은 1.5%p만 올랐습니다. 상위 1%로 학습한 경우는 평균 학습 각도에서 거의 움직이지 않았습니다.");
  const labels = ["N=16", "N=20", "N=24", "N=28"];
  const lineOpt = (color, pos) => ({ chartColors: [color], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 8, showValue: true, dataLabelPosition: pos, dataLabelFormatCode: "General", dataLabelFontSize: 11, dataLabelColor: THEME.colors.dk2, dataLabelFontFace: "+mn-lt" });
  s.addChart([
    { type: pres.charts.LINE, data: [{ name: "양자, 기대 비용으로 학습", labels, values: [13, 28, 80, 222] }], options: lineOpt(THEME.colors.accent4, "t") },
    { type: pres.charts.LINE, data: [{ name: "양자, CVaR 10%로 학습", labels, values: [10, 16, 39, 82] }], options: lineOpt(THEME.colors.accent1, "b") },
    { type: pres.charts.LINE, data: [{ name: "고전: 국소탐색 재시작 수", labels, values: [1.29, 1.46, 1.64, 1.65] }], options: lineOpt(THEME.colors.accent2, "t") },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.85, ...chartBase(),
    showTitle: true, title: "최적해까지 필요한 시도 횟수 (로그 눈금)",
    valAxisLogScaleBase: 10, valAxisMinVal: 1, valAxisMaxVal: 1000, valAxisLabelFormatCode: "0", showLegend: true, objectName: "chart-cvar",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "2.11배", "N=24·28에서 무작위 대비 배수가 기대 비용 학습의 몇 배인지 (중앙값). 실행 전에 정한 기준 2배를 넘었다", C.background1);
  stat(s, x, 4.2, w, 2.25, "약 50배", "N=28에서 양자 측정 82회 대 고전 재시작 1.65회. CVaR 전에는 약 130배. 국소탐색과 합친 성공률은 +1.5%p", C.background1, C.accent2);
}
{
  const s = slide("CONTENT", "실기기 가능성 · 로컬 회로 변환", "N=100 어려운 문제는 실기기 출력이 잡음에 묻힌다",
    "IBM 계정 접속 없이 변환만 했다. Nighthawk형 10×12 격자와 FakeFez(Heron), optimization level 3. 남는 신호 ≈ exp(−6.1e-4 × CZ), 11-09 ibm_phoenix N=20 실측 16개 회로에 맞춘 낙관적 추정. 출처: hard.md 결과 11·12",
    "어려운 12문제를 실기기에서 돌려 점수로 비교하는 안을 검토했습니다. 회로를 로컬에서 변환해 보니 가장 가벼운 회로도 2큐비트 게이트가 1만 개를 넘었습니다. 11월 9일 실측에서 게이트 수와 신호 유지율의 관계를 얻었는데, 이 관계로 보면 남는 신호가 0.1% 이하입니다. 측정 1만 회로도 무작위와 구분되지 않고, 정확히 15개를 고른 답도 거의 나오지 않습니다. 신호가 남는 크기는 N≲30으로, 정확한 시뮬레이션이 가능하고 고전이 앞선 바로 그 크기입니다.");
  table(s, ["회로", "2큐비트 게이트 (CZ)", "남는 신호"], [
    ["11-09 실측 · N=20 (결합 4배)", "83~375", { t: "75~94%", c: "ok" }],
    ["11-09 실측 · N=100 (ETF당 3쌍, 성긴 문제)", "599", { t: "73%", c: "ok" }],
    ["어려운 문제 N=100 · 결합 30% · XY 믹서", "10,782", { t: "0.14% (추정)", c: "hl" }],
    ["어려운 문제 N=100 · 전체 쌍 · 표준 (SWAP 네트워크)", "14,850", { t: "0.01% (추정)", c: "hl" }],
  ], M, 1.95, 7.6, [4.4, 1.7, 1.5], 13, 0.55);
  bullets(s, [
    "판정 기준선: 무작위 k개 1,000~10,000개 중 최고 점수의 갭이 12~55%다. 실기기 답은 이 선을 넘어야 잡음 이상의 정보가 있다.",
    "N=100 어려운 문제는 제출하지 않는 것을 제안한다. 결과가 무작위와 같을 것이 거의 확실하다.",
  ], M, 4.85, 7.6, 1.9, C.text2, 14);
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "1만 개 이상", "N=100 어려운 문제 p=1 회로의 2큐비트 게이트 수 (N=20 실측 회로의 30~50배)", C.background2, C.accent2);
  stat(s, x, 4.2, w, 2.25, "N ≲ 30", "모든 쌍을 잇는 문제에서 신호가 절반 이상 남는 크기 (N=28 50%, N=40 24%, N=50 11%)", C.background2);
}
{
  const s = slide("CONTENT_ALT", "양자 방법 종합 비교", "목적별로 가장 나은 양자 방법도 고전 국소탐색에는 못 미쳤다",
    "SQA·RQAOA·XY-QAOA는 모두 고전 컴퓨터에서 정확히(또는 모사로) 계산했다. 갭은 최적값 대비 상대 차이. 출처: hard.md 결과 4~12",
    "지금까지 시험한 양자 방법 중 목적별로 가장 나은 것을 골랐습니다. 점수로는 양자 어닐링을 고전으로 모사한 SQA가 가장 좋았지만 실제 칩에 올리는 과정을 모사하면 실패했습니다. 게이트형에서는 개수 세기와 빔을 붙인 RQAOA가 가장 나았지만 같은 절차의 고전판과 비겼습니다. 샘플러로서는 XY 완전 그래프 QAOA가 가장 좋았지만 크기를 키우면 고전과의 격차가 벌어졌고, CVaR로 학습해도 약 50배 격차가 남았습니다.");
  table(s, ["목적", "가장 나은 양자 방법", "결과", "한계"], [
    ["어려운 문제의 점수", "SQA (양자 어닐링 모사)", "3 / 12, 갭 1.2~4.2%", "칩 임베딩까지 모사하면 k개 지킨 답 0%"],
    ["게이트형 대표", "RQAOA + 개수 세기 + 빔", "0 / 12, 갭 중앙값 약 5%", "같은 절차의 고전판과 6승 6패"],
    ["샘플러 품질", "XY 완전 그래프 QAOA", "N=28 p=3에서 무작위의 5,654배", "필요 측정 수 13 → 222회 (CVaR로 82회), 고전 1.65회"],
    ["실기기 실행", "IBM ibm_phoenix", "N=20에서 신호 75~94% 유지", "N=100 어려운 문제는 신호 0.1% 이하"],
    [{ t: "기준: 고전 스왑 탐색", c: "ok" }, "—", { t: "12 / 12, 문제당 1~3초", c: "ok" }, "MILP 증명 없이도 최적해를 찾는다"],
  ], M, 1.95, CW, [2.4, 3.0, 3.2, 3.53], 14, 0.58);
  s.addText([{ text: "정리 ", options: { bold: true, color: C.accent1 } }, { text: "XY 완전 그래프 QAOA가 원리상 가장 좋은 샘플러였고 SQA가 가장 좋은 점수를 냈다. 어느 것도 개수를 지키는 고전 국소탐색을 넘지 못했고, 크기를 키우면 격차가 벌어졌다. CVaR로 학습해도 N=28 격차는 약 50배다.", options: { color: C.text1 } }],
    { x: M, y: 5.75, w: CW, h: 0.95, fontSize: 16, margin: 0, valign: "top", isTextBox: true, objectName: "takeaway" });
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
  const s = slide("CONTENT", "다음 단계", "양자 쪽은 깊은 회로에서 CVaR 추세를 한 번 더 보고 판단한다", null,
    "CVaR 학습은 실행 전에 정한 기준을 넘어 양자 샘플을 약 2배 좋게 했습니다. 그래서 예정대로 바로 정리하지 않고, 회로를 깊게 하면 N에 따른 추세가 바뀌는지 한 번 더 보겠습니다. 다만 N=28 격차가 아직 약 50배라 결론이 뒤집힐 가능성은 낮습니다. 실기기는 N=100 어려운 문제가 잡음에 묻히므로, 작은 크기에서 잡음 한계를 재는 용도로만 쓰는 것을 제안합니다.");
  numberedRows(s, [
    ["깊은 회로로 CVaR 추세 확인.", "CVaR 10%는 사전 기준을 넘었지만 N=28 격차는 약 50배다. p=4~6과 α 조정으로 N에 따른 추세가 바뀌는지만 보고, 바뀌지 않으면 양자 쪽은 정리한다."],
    ["IBM 실기기는 작은 크기에서 잡음 한계만 잰다.", "N=8~20 XY-QAOA로 신호가 남는 크기를 실측한다. N=100 어려운 문제는 제출하지 않는 것을 제안한다."],
    ["D-Wave는 정식화부터 바꿔서.", "벌점 QUBO로는 정밀도에 묻힌다. QPU 시간을 확보하면 개수 제약을 지원하는 하이브리드 솔버나 희소한 정식화로 시험한다."],
    ["MaiQ 실제 목적식 적용.", "적합도·공분산·ETF 목록으로 목적식을 확정(D04)하고 같은 절차로 다시 푼다."],
  ], 1.95, 0.98);
}
{
  const s = slide("STATEMENT", "정리", "실제 ETF 데이터에서 출발해 양자 알고리즘으로 최적해를 찾고,\n그 해가 최적임을 증명하는 절차를 완성했다", null,
    "핵심은 세 가지입니다. 실제 데이터로 만든 문제, 150큐비트까지 학습되는 GPU 각도 학습과 실제 양자 하드웨어 실행, 그리고 MILP로 최적성을 증명하는 검증 체계입니다. 같은 검증 체계로 한계도 확인했습니다. 일부러 어렵게 만든 문제에서는 개수를 지키는 고전 탐색이 수 초 만에 풀었고, 지금 시험한 양자 방법은 그에 못 미쳤습니다. 크기를 키우면 그 격차가 벌어졌고, 학습 기준을 CVaR로 바꿔도 약 50배 격차가 남았습니다.");
  bullets(s, [
    "실제 ETF 148개·101개, 두 기간의 가격으로 만든 문제",
    "150큐비트 회로 각도 학습, 100큐비트 IBM 하드웨어 실행",
    "RQAOA로 ETF 150개 문제까지 최적해 도달, MILP로 증명",
    "어려운 문제에서는 개수를 지키는 고전 탐색이 앞섰고(양자 0/12), 크기를 키우면 격차가 벌어졌다(CVaR 학습 후 약 50배)",
  ], M + 0.2, 3.85, CW - 0.4, 2.7, C.accent6, 18);
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
