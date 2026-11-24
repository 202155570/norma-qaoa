// 양자 방법 vs 무작위·점수 순 선택 — structured pptxgenjs deck (theme, layouts, sections, notes)
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
pres.title = "양자 방법과 무작위·점수 순 선택 비교";
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
function table(s, header, rows, x, y, w, colW, size = 14, rowH = 0.42, opt = {}) {
  const tone = { ok: C.accent1, hl: C.accent2, dim: C.accent3 };
  const al = (j) => (opt.align ? opt.align[j] : "left");
  const hdr = header.map((h, j) => ({ text: h, options: { bold: true, fill: { color: C.accent5 }, color: C.text1, align: al(j) } }));
  const body = rows.map((r, i) => r.map((c, j) => {
    const o = { align: al(j), ...(opt.fills && opt.fills[i] ? { fill: { color: opt.fills[i] } } : {}), ...(opt.bold && opt.bold[i] ? { bold: true } : {}) };
    return typeof c === "string" ? { text: c, options: { color: C.text1, ...o } } : { text: c.t, options: { color: tone[c.c], ...o } };
  }));
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
section("개요");
{
  const s = slide("COVER", "비교 보고 · 2026-11-24", "양자 방법과\n무작위·점수 순 선택 비교",
    "ETF 선택 문제 · padopauli(PADO PPS) · IBM 양자 하드웨어 · 이상적 양자 시뮬레이션 · RQAOA · SQA",
    "같은 ETF 선택 문제를 양자 방법과 두 가지 단순 대조군으로 풀어 비교했습니다. 대조군은 같은 개수를 무작위로 고르는 방법과, 점수가 높은 순서대로 고르는 방법입니다. 이 자료는 이 두 대조군과의 비교만 다룹니다.");
  s.addText("같은 문제, 같은 목적식 점수로 양자 방법의 답을 두 대조군과 비교했다", { placeholder: "body" });
}
{
  const s = slide("CONTENT", "비교 기준", "양자 방법의 답을 두 가지 단순 선택과 같은 목적식 점수로 비교했다",
    "목적식 G(T) = Σ 1차 항(점수) + Σ 쌍 항(상관·공분산), 정확히 k개 선택, 낮을수록 좋다. 최적값은 MILP로 증명했다. 출처: research/pado_pps/hard.md",
    "모든 비교는 같은 목적식 점수로 했습니다. 최적값은 혼합정수계획(MILP)으로 증명한 값이고, 갭은 최적값과의 상대 차이입니다. 대조군은 두 가지입니다. 무작위 선택은 양자 측정과 같은 횟수만큼 무작위로 뽑아 그중 가장 좋은 답을 쓰고, 점수 순 선택은 점수 상위 k개를 고릅니다. 더 강한 고전 방법과의 비교는 이 자료의 범위가 아닙니다.");
  const w = (CW - 2 * 0.35) / 3;
  card(s, M, 1.95, w, 3.7, "무작위 선택", "정확히 k개를 무작위로 고른다. 양자 측정 S회와 공정하게 비교하려고 S개를 뽑아 그중 가장 좋은 답을 쓴다(S = 1,000, 100,000).", C.background2, { text: "1", color: C.accent3 });
  card(s, M + w + 0.35, 1.95, w, 3.7, "점수 순 선택", "ETF 점수(1차 항) 상위 k개를 고른다. 종목 사이의 상관(쌍 항)은 보지 않는다. 실무에서 가장 먼저 떠올리는 단순 규칙이다.", C.background2, { text: "2", color: C.accent3 });
  card(s, M + 2 * (w + 0.35), 1.95, w, 3.7, "양자 방법", "padopauli로 각도를 학습한 IBM 하드웨어 QAOA(N=20·50·100)와 RQAOA(N=50~150), 이상적 시뮬레이션의 XY-QAOA(N=16~28), 양자 어닐링 모사 SQA.", C.background2, { text: "Q", color: C.accent1 });
  s.addText([{ text: "범위 ", options: { bold: true, color: C.accent2 } }, { text: "목적식을 보며 하나씩 고르는 탐욕법, 개수를 지키는 국소탐색, MILP 같은 더 강한 고전 방법은 이 비교에 넣지 않았다.", options: { color: C.text1 } }],
    { x: M, y: 5.95, w: CW, h: 0.8, fontSize: 15, margin: 0, valign: "top", isTextBox: true, objectName: "scope" });
}
{
  const s = slide("CONTENT_ALT", "요약", "양자 방법은 대부분의 비교에서 두 대조군보다 좋은 답을 냈다", null,
    "다섯 줄이 이 자료의 결론입니다. 큰 문제의 양자 회로 각도와 RQAOA 계산에는 GPU 시뮬레이터 padopauli를 썼습니다. 대부분의 비교에서 양자 방법이 두 대조군보다 좋았지만, IBM 하드웨어 N=50·100에서는 대조군이 앞섰습니다. 마지막 줄은 이 비교의 범위입니다.");
  numberedRows(s, [
    ["IBM 하드웨어는 N=20에서 앞섰고 N=50·100에서는 대조군이 앞섰다.", "N=20 상위 1% 샷 54%(점수 순 45%, 무작위 26%), 결합이 강한 문제에서 상위 0.1% 샷이 무작위의 90~310배. N=50·100은 점수 순·무작위가 더 높았다."],
    ["padopauli를 쓴 RQAOA가 N=50~150 문제 6개 모두에서 최적해를 찾았다.", "점수 순 선택과 무작위 1,000개 중 최고는 6문제 모두 최적해가 아니었다."],
    ["작은 문제(N=16~28)에서 측정 1,000회 안에 최적해가 89~100% 나왔다.", "무작위 1,000개는 0.1~42%, 점수 순 선택은 80문제 중 0개였다(이상적 시뮬레이션)."],
    ["큰 어려운 문제(N=100~150)에서 갭이 대조군의 1/4 이하였다.", "갭 중앙값: SQA 2.3%, RQAOA 5.2%, 무작위 10만 개 중 최고 22%, 점수 순 32%."],
    ["이 비교는 단순 대조군과의 비교다.", "더 강한 고전 방법은 넣지 않았고, 그 방법들은 이 문제들에서 양자 방법보다 좋은 답을 냈다(연구 보고서 참고)."],
  ], 1.95, 0.97);
}

// ---------------------------------------------------------------- padopauli
section("padopauli 활용");
{
  const s = slide("CONTENT", "padopauli (PADO PPS)", "150큐비트 회로의 각도를 GPU에서 학습했다",
    "capture = 정확 학습 대비 PPS 각도의 에너지 개선 비율. N=20 지도: d=3~5, p=2~5, 인스턴스 10개씩. 출처: research/pado_pps/README.md, hard.md 결과 4·13",
    "padopauli는 파울리 전파 방식으로 QAOA 회로의 기댓값과 기울기를 GPU에서 계산하는 근사 시뮬레이터입니다. 큐비트가 100개를 넘으면 상태벡터로는 계산할 수 없어서, 큰 문제의 회로 각도 학습과 RQAOA 상관값 계산에 이 도구를 썼습니다. 정확 계산과 대조해 w=5에서 정확 학습의 90% 이상 성능을 확인했습니다.");
  const w = (CW - 2 * 0.35) / 3;
  stat(s, M, 1.95, w, 2.0, "150 큐비트", "padopauli로 회로 각도를 학습한 가장 큰 문제 (상태벡터로는 불가능한 크기)", C.background2);
  stat(s, M + w + 0.35, 1.95, w, 2.0, "0.90 이상", "w=5로 학습한 각도의 성능, 정확 학습 대비 (N=20 지도 전 조건, 최저 0.901)", C.background2);
  stat(s, M + 2 * (w + 0.35), 1.95, w, 2.0, "3곳", "IBM 하드웨어 회로(N=20·50·100), RQAOA(N=50~150), 어려운 문제 p=2(N=100)", C.background2);
  bullets(s, [
    "쓰임 1 · IBM 하드웨어: 실제 장비에서 돌린 QAOA 회로의 각도를 padopauli로 학습했다.",
    "쓰임 2 · RQAOA: 변수를 하나씩 정할 때마다 필요한 상관값을 padopauli로 계산했다(N=150, p=2까지).",
    "주의: GPU 메모리 피크가 한계에 닿으면 잘못된 값을 낸다(160 GB 넘은 계산은 제외). 모든 쌍을 섞는 회로(완전 그래프 XY 믹서)는 계산이 무너진다.",
  ], M, 4.3, CW, 2.4, C.text2, 15);
}


// ---------------------------------------------------------------- 2. hardware
section("IBM 양자 하드웨어");
{
  const s = slide("CONTENT", "IBM 하드웨어 · 원래 문제 (N=20)", "실제 양자 장비의 샘플이 두 대조군보다 좋은 해를 더 많이 냈다",
    "2026-11-09 ibm_phoenix(120큐비트), 회로당 10,000샷, 각도는 padopauli w=5로 학습. 샷마다 6개로 보정한 뒤 평가. 점수 순 배정: 하드웨어와 같은 선택 확률을 점수 순으로 배정한 샘플. 출처: README.md §8",
    "padopauli로 학습한 각도의 QAOA 회로를 IBM 장비에서 실행했습니다. 목적식 상위 1%에 든 샷의 비율이 무작위 26%, 점수 순 배정 33~45%에 비해 하드웨어 QAOA는 36~54%였고, 깊이를 늘릴수록 올라갔습니다.");
  s.addChart(pres.charts.BAR, [
    { name: "IBM 하드웨어 QAOA", labels: ["p=1", "p=2", "p=3"], values: [0.36, 0.45, 0.54] },
    { name: "점수 순 배정", labels: ["p=1", "p=2", "p=3"], values: [0.33, 0.40, 0.45] },
    { name: "무작위", labels: ["p=1", "p=2", "p=3"], values: [0.26, 0.26, 0.26] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.85, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4, "B8C0CC"], ...chartBase(),
    showTitle: true, title: "목적식 상위 1%에 든 샷 비율", dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
    valAxisMaxVal: 0.6, valAxisMinVal: 0, valAxisLabelFormatCode: "0.0", showLegend: true, objectName: "chart-hw-n20",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "54%", "p=3 하드웨어 샷 중 상위 1%에 든 비율 (점수 순 45%, 무작위 26%)", C.background2);
  stat(s, x, 4.2, w, 2.25, "깊을수록 ↑", "p=1 36% → p=2 45% → p=3 54%. 하드웨어 잡음 속에서도 깊이의 효과가 남았다", C.background2);
}
{
  const s = slide("CONTENT_ALT", "IBM 하드웨어 · 결합이 강한 문제 (N=20)", "좋은 해가 무작위보다 90~310배 자주 나왔다",
    "결합 4배 N=20 인스턴스 3개, 각도는 padopauli w=5와 정확 학습, 보정 없는 원시 샷 10,000회. 무작위로 뽑으면 상위 0.1%에 드는 비율은 0.1%. 출처: README.md §8",
    "종목 사이의 결합을 강하게 만든 문제입니다. 하드웨어 샘플의 9~31%가 에너지 상위 0.1%에 들었습니다. 무작위로 뽑으면 0.1%이므로 90~310배입니다. 10,000샷 중 정확한 최적해를 직접 맞힌 샷도 최대 13개로, 무작위 기대값 0.01개보다 훨씬 많았습니다.");
  const hw = [[0.10, 0.22, 0.18, 0.12], [0.10, 0.18, 0.16, 0.31], [0.09, 0.13, 0.16, 0.23]];
  s.addChart(pres.charts.BAR, [0, 1, 2].map((i) => ({ name: ["문제 s5", "문제 s10", "문제 s12"][i], labels: ["p=1", "p=2", "p=3", "p=4"], values: hw[i] })), {
    x: M, y: 1.9, w: 7.6, h: 4.85, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4, "7F8A99"], ...chartBase(),
    showTitle: true, title: "에너지 상위 0.1%에 든 샷 비율 (무작위 0.1%)", dataLabelPosition: "outEnd", dataLabelFormatCode: "0%",
    valAxisMaxVal: 0.35, valAxisMinVal: 0, valAxisLabelFormatCode: "0%", showLegend: true, objectName: "chart-hw-k4",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "90~310배", "상위 0.1%에 든 샷 비율, 무작위 대비", C.background1);
  stat(s, x, 4.2, w, 2.25, "13개", "10,000샷 중 정확한 최적해를 맞힌 샷 수 최대값 (무작위 기대값 0.01개)", C.background1);
}

{
  const s = slide("CONTENT", "IBM 하드웨어 · N=50·100 (padopauli 각도)", "N=50·100에서는 두 대조군이 하드웨어보다 앞섰다",
    "같은 작업(2026-11-09), 샷마다 6개로 보정. 이 실험의 무작위는 종목마다 50% 확률로 고른 뒤 보정한 것이라, 보정 단계가 사실상 탐욕 탐색을 한다. 출처: README.md §8.2",
    "같은 실험에서 큰 회로도 돌렸습니다. padopauli로 학습한 각도로 N=50과 N=100 회로를 실행했지만, 목적식 상위 1%에 든 샷의 비율은 점수 순 배정과 무작위가 더 높았습니다. N=100 회로는 2큐비트 게이트가 599개로 신호의 약 73%가 남았지만, 원시 샷이 최적해와 같았던 경우는 10,000샷 중 0이었습니다. 이 실험에서 좋은 해를 찾은 것은 양자 회로보다 6개로 고치는 보정 단계였습니다.");
  table(s, ["회로", "하드웨어 QAOA", "점수 순 배정", "무작위 + 보정"], [
    ["N=20, p=1 / 2 / 3", { t: "36% / 45% / 54%", c: "ok" }, "33% / 40% / 45%", "26%"],
    ["N=50, p=1 / 2", { t: "36% / 39%", c: "hl" }, "51% / 51%", "92%"],
    ["N=100, p=1", { t: "77%", c: "hl" }, "95%", "100%"],
  ], M, 1.95, CW, [3.2, 3.0, 3.0, 2.93], 15, 0.55, { align: ["left", "center", "center", "center"] });
  bullets(s, [
    "값은 목적식 상위 1%에 든 샷의 비율이다. N=20에서만 하드웨어가 앞섰다.",
    "N=50·100에서 원시 샷이 최적해와 같았던 경우는 10,000샷 중 0이었다. 최선해는 보정 단계가 찾았다.",
    "이 문제는 1차 항이 결합항보다 5~8배 커서, 종목마다 거의 따로 정해도 되는 쉬운 문제다.",
  ], M, 4.35, CW, 2.4, C.text2, 15);
}

// ---------------------------------------------------------------- RQAOA + padopauli
section("RQAOA + padopauli");
{
  const s = slide("CONTENT_ALT", "RQAOA + padopauli · N=50~150", "RQAOA + padopauli가 6문제 모두에서 최적해를 찾았다",
    "problem_{50,100,150}.json, 결합 1배·4배, 바닥 상태가 6개를 고르도록 λ 설정. 상관값은 padopauli w=8(GPU). 최적값은 MILP로 증명(0.01초). 무작위 열은 1,000개 중 최고를 20회 반복해 최적해가 나온 횟수. 출처: rqaoa_big*.jsonl",
    "실제 ETF 데이터로 만든 N=50·100·150 문제를 결합 1배와 4배로 만들어 RQAOA로 풀었습니다. 변수를 하나씩 정할 때 필요한 상관값을 padopauli로 계산했고, p=1에서 3문제, 나머지 3문제는 p=2에서 증명된 최적해에 도달했습니다. 점수 순 선택과 무작위 1,000개 중 최고는 여섯 문제 모두 최적해가 아니었습니다.");
  table(s, ["문제", "RQAOA + padopauli", "시간", "점수 순 선택", "무작위 1,000개 중 최고"], [
    ["N=50, 결합 1배", { t: "최적 (p=1)", c: "ok" }, "17초", "최적 아님", "0 / 20회"],
    ["N=50, 결합 4배", { t: "최적 (p=1)", c: "ok" }, "25초", "최적 아님", "0 / 20회"],
    ["N=100, 결합 1배", { t: "최적 (p=1)", c: "ok" }, "84초", "최적 아님", "0 / 20회"],
    ["N=100, 결합 4배", { t: "최적 (p=2)", c: "ok" }, "12분", "최적 아님", "0 / 20회"],
    ["N=150, 결합 1배", { t: "최적 (p=2)", c: "ok" }, "20분", "최적 아님", "0 / 20회"],
    ["N=150, 결합 4배", { t: "최적 (p=2)", c: "ok" }, "26분", "최적 아님", "0 / 20회"],
  ], M, 1.95, 8.3, [2.2, 1.9, 0.9, 1.5, 1.8], 14, 0.52, { align: ["left", "center", "right", "center", "center"] });
  const x = 9.25, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "6 / 6", "RQAOA + padopauli가 증명된 최적해에 도달한 문제 수", C.background1);
  stat(s, x, 4.2, w, 2.25, "0 / 6", "점수 순 선택, 무작위 1,000개 중 최고가 최적해를 고른 문제 수", C.background1, C.accent2);
}

// ---------------------------------------------------------------- 3. simulation
section("이상적 양자 시뮬레이션");
{
  const s = slide("CONTENT", "작은 문제 · XY-QAOA (N=16~28)", "측정 1,000회 안에 최적해가 나올 확률이 대조군보다 훨씬 높았다",
    "N마다 20문제(k=N/4, 쌍 항 강화 ×4·×16). 디키 시작 XY 완전 그래프 QAOA p=3, 잡음 없는 정확 계산. 확률은 1−(1−P)^1000의 문제 평균. 점수 순 선택은 결정적이라 최적해이거나 아니다. 출처: hard.md 결과 10",
    "작은 문제는 양자 상태를 정확히 계산할 수 있습니다. 측정 1,000회 안에 최적해가 한 번이라도 나올 확률이 XY-QAOA는 89~100%였고, 같은 개수의 무작위 선택은 N이 커질수록 42%에서 0.1%로 떨어졌습니다. 점수 순 선택은 80문제 중 최적해가 하나도 없었고 갭 중앙값이 28~59%였습니다. 잡음 없는 이상적인 장비를 가정한 결과입니다.");
  const labels = ["N=16", "N=20", "N=24", "N=28"];
  s.addChart(pres.charts.BAR, [
    { name: "XY-QAOA p=3 (이상적)", labels, values: [100, 100, 97, 89] },
    { name: "무작위 1,000개", labels, values: [42.3, 6.2, 0.7, 0.1] },
    { name: "점수 순 선택", labels, values: [0, 0, 0, 0] },
  ], {
    x: M, y: 1.9, w: 7.6, h: 4.85, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55,
    chartColors: [THEME.colors.accent1, "B8C0CC", THEME.colors.accent2], ...chartBase(),
    showTitle: true, title: "측정(또는 시도) 1,000회 안에 최적해가 나올 확률 (%)", dataLabelPosition: "outEnd", dataLabelFormatCode: "General",
    valAxisMaxVal: 110, valAxisMinVal: 0, valAxisLabelFormatCode: "0", showLegend: true, objectName: "chart-small",
  });
  const x = 8.55, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "5,654배", "N=28에서 측정 1회에 최적해가 나올 확률, 무작위 대비 (N=16은 150배)", C.background2);
  stat(s, x, 4.2, w, 2.25, "0 / 80", "점수 순 선택이 최적해를 고른 문제 수 (갭 중앙값 28~59%)", C.background2, C.accent2);
}
{
  const s = slide("CONTENT_ALT", "큰 어려운 문제 (N=100~150)", "양자 방법의 갭은 대조군의 1/4 이하였다",
    "MILP가 128~2,692초 걸려 증명한 12문제(N=100·150, k=6·15). RQAOA·SQA는 잡음 없는 고전 시뮬레이션. RQAOA는 변형(p=1, 개수 처리, 빔, 벌점 없음) 중 최선. 무작위는 20회 반복 중앙값. 출처: hard.md 결과 4~8·11",
    "MILP 증명에 수 분에서 45분이 걸린 어려운 문제 12개입니다. 갭 중앙값이 점수 순 선택은 32%, 무작위 1,000개 중 최고는 31%, 무작위 10만 개 중 최고도 22%인데, RQAOA는 5.2%, 양자 어닐링을 모사한 SQA는 2.3%였습니다. SQA는 12문제 중 3개에서 최적해를 정확히 찾았습니다.");
  s.addChart(pres.charts.BAR, [
    { name: "갭 중앙값 (%)", labels: ["점수 순 선택", "무작위 1,000개 중 최고", "무작위 100,000개 중 최고", "RQAOA p=1", "RQAOA 보강 최선", "SQA (양자 어닐링 모사)"], values: [31.9, 30.6, 22.0, 5.5, 5.2, 2.3] },
  ], {
    x: M, y: 1.9, w: 7.9, h: 4.85, barDir: "bar", barGapWidthPct: 40,
    chartColors: ["B8C0CC", "B8C0CC", "B8C0CC", THEME.colors.accent1, THEME.colors.accent1, THEME.colors.accent1], ...chartBase(),
    showTitle: true, title: "최적값 대비 갭 중앙값 (%, 낮을수록 좋음)", dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
    valAxisMaxVal: 36, valAxisMinVal: 0, valAxisLabelFormatCode: "0", showLegend: false, catAxisOrientation: "maxMin", catAxisLabelFontSize: 12, objectName: "chart-hard12",
  });
  const x = 8.85, w = W - M - x;
  stat(s, x, 2.0, w, 1.95, "12 / 12", "RQAOA·SQA가 점수 순 선택보다 좋은 답을 낸 문제 수", C.background1);
  stat(s, x, 4.2, w, 2.25, "3 / 12", "SQA가 최적해를 정확히 찾은 문제 수 (점수 순·무작위 10만 개는 0개)", C.background1);
}
{
  const s = slide("CONTENT", "큰 어려운 문제 · 문제별", "문제별로 봐도 양자 방법이 거의 모든 문제에서 앞섰다",
    "갭(%) = (G − 최적값) / |최적값|. 상관형 N=150 k=6 ×16에서는 RQAOA p=1이 46개를 골라 실패해 벌점 없는 변형의 값(45.9)을 적었다. 상관형 N=100 k=15 전체 ×16은 padopauli p=2(약 2시간)도 4.3%였다. 출처: hard.md 결과 4·5·8·11",
    "열두 문제 각각의 갭입니다. RQAOA와 SQA는 12문제 모두에서 점수 순 선택보다 좋았고, RQAOA는 한 문제를 빼면 무작위 10만 개 중 최고보다도 좋았습니다. 그 한 문제(상관형 N=150, k=6, ×16, 주황색)는 RQAOA가 약했던 문제로, 무작위 10만 개 중 최고(8.4%)가 RQAOA(45.9%)보다 좋았습니다.");
  // gap (%) per problem; columns: family, N, k, density, strength | score, rand 1k, rand 100k, RQAOA best, SQA
  const raw = [
    ["상관형", 150, 6, "전체", 16, "62.2", "15.3", "8.4", "45.9", "3.7"],
    ["무작위형", 100, 15, "전체", 4, "29.8", "33.8", "25.2", "8.9", "2.2"],
    ["무작위형", 100, 15, "전체", 16, "80.8", "52.5", "40.5", "3.8", "2.4"],
    ["무작위형", 150, 15, "전체", 4, "23.2", "41.1", "31.7", "3.9", "1.6"],
    ["공분산형", 150, 15, "전체", 16, "108.6", "47.6", "31.0", "17.1", "0.0"],
    ["상관형", 100, 15, "전체", 16, "16.6", "25.3", "15.5", "4.3", "3.7"],
    ["상관형", 150, 15, "30%", 4, "5.7", "26.8", "18.2", "1.3", "2.7"],
    ["무작위형", 150, 15, "30%", 16, "48.7", "54.9", "46.1", "6.6", "0.0"],
    ["상관형", 100, 15, "30%", 16, "13.6", "27.1", "17.5", "6.2", "4.2"],
    ["공분산형", 100, 15, "전체", 16, "110.7", "43.7", "30.0", "16.0", "0.0"],
    ["상관형", 150, 6, "전체", 4, "34.0", "15.9", "7.1", "0.4", "2.9"],
    ["공분산형", 150, 15, "전체", 4, "19.2", "27.4", "18.8", "4.3", "1.2"],
  ];
  const fam = ["공분산형", "상관형", "무작위형"];
  raw.sort((a, b) => fam.indexOf(a[0]) - fam.indexOf(b[0]) || a[2] - b[2] || a[1] - b[1] || (a[3] === "30%" ? 0 : 1) - (b[3] === "30%" ? 0 : 1) || a[4] - b[4]);
  const rows = raw.map((r) => [r[0], `N=${r[1]}`, `k=${r[2]}`, r[3], `×${r[4]}`, r[5], r[6], r[7],
    { t: r[8], c: Number(r[8]) > Number(r[7]) ? "hl" : "ok" }, { t: r[9], c: "ok" }]);
  rows.push(["중앙값", "", "", "", "", "31.9", "30.6", "22.0", { t: "5.2", c: "ok" }, { t: "2.3", c: "ok" }]);
  const band = { 공분산형: C.background1, 상관형: C.background2, 무작위형: C.background1 };
  const fills = raw.map((r) => band[r[0]]).concat([C.accent5]);
  const bold = raw.map(() => false).concat([true]);
  lead(s, "값은 최적값 대비 갭(%), 0이면 최적해. 무작위 열은 S개 중 최고. 쌍 항 종류 → k → N → 밀도 → 세기 순.");
  table(s, ["쌍 항", "N", "k", "밀도", "세기", "점수 순", "무작위 1천", "무작위 10만", "RQAOA 최선", "SQA"], rows, M, 2.05, CW,
    [1.3, 0.85, 0.75, 0.8, 0.75, 1.4, 1.6, 1.65, 1.6, 1.433], 12, 0.31,
    { align: ["left", "right", "right", "center", "right", "right", "right", "right", "right", "right"], fills, bold });
}

// ---------------------------------------------------------------- 4. limits
section("범위와 해석");
{
  const s = slide("CONTENT_ALT", "범위와 주의점", "이 결과를 인용할 때 함께 밝혀야 할 네 가지",
    "출처: research/pado_pps/hard.md 결과 1~13, README.md §8",
    "이 자료는 단순 대조군과의 비교입니다. 인용할 때는 네 가지를 함께 밝혀야 오해가 없습니다. 특히 더 강한 고전 방법은 이 문제들에서 양자 방법보다 좋은 답을 냈으므로, 이 자료를 양자 우위의 근거로 쓰면 안 됩니다.");
  const w = (CW - 0.35) / 2, h = 2.15;
  card(s, M, 1.95, w, h, "대조군은 단순 규칙이다", "목적식을 보며 하나씩 고르는 탐욕법, 개수를 지키는 국소탐색, MILP는 넣지 않았다. 그 방법들은 같은 문제에서 양자 방법보다 좋은 답을 냈다(연구 보고서 참고).", C.background1, { text: "1", color: C.accent2 });
  card(s, M + w + 0.35, 1.95, w, h, "실기기는 N=20에서만 앞섰다", "N=50·100 하드웨어는 대조군보다 못했다. 나머지는 잡음 없는 시뮬레이션이고, padopauli는 근사 계산이다.", C.background1, { text: "2", color: C.accent2 });
  card(s, M, 1.95 + h + 0.3, w, h, "SQA는 고전 모사다", "양자 어닐링을 고전 컴퓨터로 흉내 낸 방법이다. 실제 어닐러에 올리는 과정(임베딩, 정밀도)을 모사하면 개수를 지킨 답이 나오지 않았다.", C.background1, { text: "3", color: C.accent2 });
  card(s, M + w + 0.35, 1.95 + h + 0.3, w, h, "후처리를 붙이면 차이가 줄어든다", "양자 샘플과 무작위 선택에 같은 국소탐색을 붙이면 최종 성공률은 구분되지 않았다. 이 비교는 후처리 없는 원래 답의 비교다.", C.background1, { text: "4", color: C.accent2 });
}
{
  const s = slide("STATEMENT", "정리", "양자 방법은 대부분의 비교에서\n무작위·점수 순 선택보다 좋은 답을 냈다", null,
    "IBM 장비 N=20, padopauli를 쓴 RQAOA, 이상적인 시뮬레이션, 큰 어려운 문제에서 양자 방법이 두 단순 대조군을 앞섰습니다. IBM 장비 N=50·100에서는 대조군이 앞섰습니다. 다만 더 강한 고전 방법과의 비교는 별도이고, 그 비교에서는 고전이 앞섰다는 점을 함께 전달해야 합니다.");
  bullets(s, [
    "IBM 하드웨어: N=20 상위 1% 샷 54% (점수 순 45%, 무작위 26%), N=50·100은 대조군이 앞섬",
    "RQAOA + padopauli N=50~150: 6문제 모두 최적해 (점수 순·무작위 0문제)",
    "이상적 시뮬레이션 N=16~28: 측정 1,000회 안에 최적해 89~100% (무작위 0.1~42%, 점수 순 0%)",
    "N=100~150 어려운 문제: 갭 중앙값 SQA 2.3%, RQAOA 5.2% (무작위 10만 개 22%, 점수 순 32%)",
    "범위: 단순 대조군과의 비교이며, 더 강한 고전 방법은 양자보다 좋은 답을 냈다",
  ], M + 0.2, 3.85, CW - 0.4, 2.7, C.accent6, 18);
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
