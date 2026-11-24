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

// ---------------------------------------------------------------- 1. intro
section("보고 범위와 결론 요약");
{
  const s = slide("COVER", "사내 보고 · 2026-11-24", "ETF 선택 QAOA\n연구 보고",
    "대상 기간 2026-11-03 ~ 11-24 · 저장소 202155570/norma-qaoa (비공개) · research/pado_pps",
    "MaiQ 위성 ETF 식(N개 중 6개 선택)을 기준으로 지난 3주 동안 한 실험을 정리했습니다. 11-19 보고서 이후에 MILP가 느려지는 문제 구조, 그 어려운 문제에서의 양자 방법 시험(RQAOA 변형, XY 믹서 QAOA, 어닐링류, 양자 샘플 하이브리드)이 추가됐습니다. 11-24에는 크기 키우기 실험(N=16→28), CVaR 학습 확인, 실기기 회로 변환 검토, 양자 방법 종합 비교를 더했습니다.");
  s.addText("PADO PPS 각도 학습, IBM 하드웨어 검증, 고전 최적해 인증, RQAOA와 어려운 문제 시험", { placeholder: "body" });
}
{
  const s = slide("CONTENT", "요약", "지금 ETF 문제에서 양자가 고전보다 낫다는 근거는 없다", null,
    "다섯 줄이 이 발표 전체의 결론입니다. 1~4번은 양자 쪽, 5번은 식 자체의 문제입니다. 4번이 11-19 이후 바뀐 부분입니다. 일부러 어렵게 만든 문제에서도 양자 방법은 개수를 지키는 고전 탐색에 못 미쳤습니다.");
  numberedRows(s, [
    ["padopauli 각도 학습은 조건부로 쓸 수 있다.", "표준 QAOA, 절단 가중치 w=5, 원래 결합 세기에서 정확 학습과 같은 성능을 냈다."],
    ["IBM 하드웨어 QAOA는 원래 문제의 해 찾기에 기여하지 않았다.", "최적해는 고전 보정 단계가 찾았다."],
    ["고전 MILP가 N=150 실무형 식을 수 초 안에 증명한다.", "MILP가 1시간 넘게 걸리는 어려운 문제도 개수를 지키는 고전 탐색은 1~3초 안에 풀었다."],
    ["RQAOA는 쉬운 문제에선 잘 맞지만 어려운 문제에선 0/12였다.", "보강해도 0/12였고 양자 샘플 하이브리드도 이득이 없었다. N=16→28로 키우자 격차가 10배에서 130배로 벌어졌고, CVaR 학습 후에도 약 50배다."],
    ["선택 식 자체의 투자 성과가 확인되지 않았다.", "샤프비율 0.33으로 전 종목 동일가중 0.48보다 낮다."],
  ], 2.0, 1.02);
}

// ---------------------------------------------------------------- 2. quantum
section("padopauli 학습, IBM 하드웨어, ma-QAOA");
{
  const s = slide("CONTENT_ALT", "문제 설정", "세 가지 문제를 다뤘다",
    "출처: research/pado_pps/README.md, problem_{50,100,150}.json, ibm_hard_prep.py",
    "변형식은 padopauli가 다룰 수 있게 결합을 희소화한 식입니다. 1차 항이 크면 ETF마다 거의 따로 결정해도 되기 때문에 양자 회로가 할 일이 적습니다. 그래서 결합을 인위적으로 키운 시험 문제를 따로 만들었습니다.");
  lead(s, "이징 형태: E(z) = Σ h_i z_i + Σ J_ij z_i z_j 이고, z_i = −1이면 그 ETF를 고른다.");
  const w = (CW - 2 * 0.35) / 3;
  card(s, M, 2.45, w, 3.6, "MaiQ 원래 식", "N개 ETF 중 정확히 6개를 고른다. ETF 점수(1차 항)와 상관이 높은 쌍의 벌점(결합항)으로 이뤄진다. N=50·100·150.", C.background1, { text: "1", color: C.accent1 });
  card(s, M + w + 0.35, 2.45, w, 3.6, "양자 회로용 변형식", "결합을 ETF당 최대 d개로 줄이고, 개수 제약은 벌점 λ로 바꿨다. 1차 항이 결합항보다 5~8배 크다.", C.background1, { text: "2", color: C.accent1 });
  card(s, M + 2 * (w + 0.35), 2.45, w, 3.6, "결합 4배 시험 문제", "분산 투자 벌점을 4배로 키워 고전 탐욕법이 실패하게 만든 N=20 인스턴스다. 더 이상 MaiQ 식이 아니다.", C.background1, { text: "3", color: C.accent2 });
}
{
  const s = slide("CONTENT", "padopauli 각도 학습", "절단 가중치 w=5면 정확 학습과 같은 각도가 나온다",
    "capture = padopauli 각도의 추가 이득 ÷ 정확 학습 각도의 추가 이득(p=1 대비). 출처: README.md §5, small.jsonl, large.jsonl",
    "w=5는 모든 조건에서 10개 인스턴스가 모두 기준을 넘었습니다. w=4는 p≤2에서만 안전합니다. GPU 버그는 padopauli 담당 팀에 제보해야 합니다.");
  lead(s, "N=20 인스턴스 10개, capture 최솟값. 기준은 0.90 이상이다.");
  table(s, ["결합 차수 d", "w=4 (p=3 / 4 / 5)", "w=5 (p=3 / 4 / 5)"], [
    ["3", { t: "0.995 / 0.889 미달 / 0.921", c: "hl" }, { t: "0.950 / 1.000 / 0.999", c: "ok" }],
    ["4", { t: "0.912 / 0.875 미달 / 0.397 미달", c: "hl" }, { t: "0.991 / 0.994 / 0.971", c: "ok" }],
    ["5", { t: "0.795 미달 / 0.765 미달 / 0.477 미달", c: "hl" }, { t: "0.960 / 0.955 / 0.901", c: "ok" }],
  ], M, 2.2, CW, [2.2, 4.95, 4.98]);
  bullets(s, [
    "큰 N에서 쓸 수 있는 깊이는 시간이 아니라 GPU 메모리가 정한다. N=150은 d=3에서 p≤3, d=5에서 p=1까지다.",
    "결합을 4배로 키우면 w=5도 부족할 수 있다. 3개 중 1개에서 p=4 capture가 0.158로 떨어졌다.",
    "padopauli 2.0.2는 GPU 메모리 한계(약 191 GB)에서 오류 없이 틀린 값을 낸다. 160 GB를 넘은 값은 쓰지 않는다.",
  ], M, 4.25, CW, 2.4);
}
{
  const s = slide("CONTENT_ALT", "IBM 하드웨어 · 원래 문제", "최적해를 찾은 것은 양자 회로가 아니라 고전 보정이었다",
    "2026-11-09 ibm_phoenix, 동적 디커플링과 twirling 사용. 출처: README.md §8, ibm/ (작업 2건, QPU 과금 12초)",
    "모든 회로에서 최선해는 원래 식의 최적해였지만, 그건 보정 단계가 해 준 일입니다. 큰 N에서는 무작위 비트로 시작해도 보정만으로 최적해가 나옵니다.");
  lead(s, "회로당 10,000샷. 샷을 6개로 보정한 뒤 원래 식 상위 1%에 든 비율.");
  table(s, ["회로", "하드웨어 QAOA", "점수순 배정", "균등 무작위"], [
    ["N=20, p=1 / 2 / 3", { t: "0.36 / 0.45 / 0.54 최고", c: "ok" }, "0.33 / 0.40 / 0.45", "0.26"],
    ["N=50, p=1 / 2", "0.36 / 0.39", "0.51 / 0.51", { t: "0.92 최고", c: "ok" }],
    ["N=100, p=1", "0.77", "0.95", { t: "1.00 최고", c: "ok" }],
  ], M, 2.2, CW, [3.2, 3.2, 2.9, 2.83]);
  bullets(s, [
    "보정 전 샷이 최적해와 같았던 비율은 N=20에서 0.04~0.14%, N=50·100에서는 10,000샷 중 0이었다.",
    "N=50·100에서는 무작위 비트를 같은 방식으로 보정한 비교군이 가장 좋았다.",
    "변형식은 1차 항이 결합항보다 5~8배 커서 ETF마다 거의 따로 정해도 된다. 양자 회로가 할 일이 적다.",
  ], M, 4.25, CW, 2.4);
}
{
  const s = slide("CONTENT", "IBM 하드웨어 · 결합 4배 문제", "깊이를 쌓는 효과는 하드웨어에도 남았지만 절반 정도다",
    "인스턴스 3개, 작업 1회. 출처: README.md §8",
    "양자 효과가 보인 유일한 경우지만 결합을 인위적으로 키운 문제이고, 이 크기에서는 고전 국소탐색이 훨씬 빠릅니다.");
  lead(s, "N=20 인스턴스 3개, 보정 없는 원시 샷. 에너지 상위 0.1%에 든 비율 (무작위는 0.1%).");
  // native clustered bar: mean over the 3 instances, hardware vs noiseless
  const hw = [[0.10, 0.22, 0.18, 0.12], [0.10, 0.18, 0.16, 0.31], [0.09, 0.13, 0.16, 0.23]];
  const nl = [[0.12, 0.42, 0.48, 0.34], [0.12, 0.31, 0.37, 0.71], [0.12, 0.21, 0.39, 0.53]];
  const mean = (a) => [0, 1, 2, 3].map((k) => Math.round((a[0][k] + a[1][k] + a[2][k]) / 3 * 100) / 100);
  s.addChart(pres.charts.BAR, [
    { name: "노이즈 없는 계산", labels: ["p=1", "p=2", "p=3", "p=4"], values: mean(nl) },
    { name: "IBM 하드웨어", labels: ["p=1", "p=2", "p=3", "p=4"], values: mean(hw) },
  ], {
    x: M, y: 2.2, w: 6.2, h: 4.4, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
    chartColors: [THEME.colors.accent4, THEME.colors.accent1],
    showTitle: true, title: "인스턴스 3개 평균", titleFontSize: 14, titleColor: THEME.colors.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: THEME.colors.dk2, dataLabelFontFace: "+mn-lt",
    dataLabelFormatCode: "0%",
    catAxisLabelColor: THEME.colors.accent3, valAxisLabelColor: THEME.colors.accent3, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", valAxisMaxVal: 0.7, valAxisLabelFormatCode: "0%",
    valGridLine: { color: "E3E7ED", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: THEME.colors.dk2, legendFontFace: "+mn-lt",
    objectName: "chart-hw-k4",
  });
  table(s, ["인스턴스", "p=1", "p=2", "p=3", "p=4"], [
    ["s5", "10%/12%", "22%/42%", "18%/48%", "12%/34%"],
    ["s10", "10%/12%", "18%/31%", "16%/37%", "31%/71%"],
    ["s12", "9%/12%", "13%/21%", "16%/39%", "23%/53%"],
  ], 7.15, 2.3, 5.58, [0.9, 1.17, 1.17, 1.17, 1.17], 12);
  s.addText("칸: 하드웨어 / 노이즈 없는 계산", { x: 7.15, y: 4.12, w: 5.58, h: 0.3, fontSize: 11, color: C.accent3, margin: 0, isTextBox: true });
  bullets(s, [
    "p≥2에서는 노이즈 없는 값의 40~60%가 남았다.",
    "바닥 상태를 맞힌 샷은 10,000샷 중 1~13개. 고전 국소탐색은 시작점 하나당 10~20%로 닿는다.",
  ], 7.15, 4.6, 5.58, 2.0, C.text2, 14);
}
{
  const s = slide("CONTENT_ALT", "ma-QAOA 비교 · 노이즈 없는 계산", "각도 70개짜리 회로가 정답을 냈지만, 푼 것은 고전 최적화기다",
    "출처: README.md §9, maqaoa.jsonl, logs/maqaoa_check.log",
    "큐비트마다 각도가 따로 있으면 곱상태로 어떤 비트열이든 만들 수 있습니다. 그래서 70개 각도 최적화는 고전 문제를 연속 변수로 바꿔 푸는 것과 같습니다. padopauli로 각도가 많은 회로를 학습하려면, 에너지가 알려진 하한보다 낮으면 거부하는 점검이 필요합니다.");
  lead(s, "결합 4배 N=20 인스턴스 3개. 바닥 상태 확률 P_gs, p=1 / 2 / 3.");
  table(s, ["인스턴스", "표준 QAOA (각도 2p개)", "ma-QAOA, 정확 학습", "ma-QAOA, padopauli"], [
    ["s5", "0.0004 / 0.0023 / 0.0021", "0.52 / 1.00 / 1.00", { t: "0.52 / 1.00 / 0.00 깨짐", c: "hl" }],
    ["s10", "0.0006 / 0.0005 / 0.0008", "1.00 / 1.00 / 1.00", { t: "1.00 / 0.00 / 0.00 깨짐", c: "hl" }],
    ["s12", "0.0003 / 0.0008 / 0.0021", "1.00 / 1.00 / 1.00", { t: "1.00 / 0.00 / 0.00 깨짐", c: "hl" }],
  ], M, 2.2, CW, [1.6, 3.6, 3.3, 3.63]);
  bullets(s, [
    "p=1에서 학습된 결합 회전각이 모두 π의 배수(오차 0.036 이하)였다. 얽힘이 없는 곱상태 회로이고, 반올림해도 P_gs가 그대로다.",
    "padopauli로 학습하면 p≥2에서 최적화기가 절단 오차를 이용했다. 예: s10 p=3 에너지 −53.9, 실제 바닥 상태 −33.7.",
  ], M, 4.25, CW, 2.4);
}

// ---------------------------------------------------------------- 3. classical
section("고전 최적해 인증과 λ 설정");
{
  const s = slide("CONTENT", "고전 최적해 인증 · MILP", "이 크기에서는 고전 계산이 최적해를 몇 초 만에 증명한다",
    "이전 결과(N=50 전수 탐색, N=100·150 국소탐색)와 6개 문제 모두 같은 해. 출처: mip.py, mip_result.json, mip_bt.json",
    "양자 최적화의 목표를 정해진 식의 최적해 찾기로 두면, 지금 크기에서는 고전 MILP가 그 일을 정확히, 빠르게 해 냅니다. PADO 변형식은 국소탐색이 3개월에서 최적해를 놓쳤고, 최적해로 바꾸면 샤프가 조금 오르지만 여전히 원래 식보다 낮습니다.");
  lead(s, "혼합정수계획(HiGHS)으로 6개 선택 문제를 풀고, 최적성 간격 0까지 확인했다.");
  const w = (CW - 2 * 0.35) / 3;
  [["0.3초", "N=50 원래 식, 최적 증명"], ["0.8초", "N=100 원래 식, 최적 증명"], ["2.5초", "N=150 원래 식, 최적 증명"]]
    .forEach(([n, l], i) => stat(s, M + i * (w + 0.35), 2.2, w, 1.6, n, l, C.background2));
  table(s, ["백테스트 108개월", "국소탐색이 최적이었던 달", "MILP 해로 다시 계산한 샤프"], [
    ["MaiQ 원래 식", "108 / 108", "0.326 (변화 없음)"],
    ["PADO 변형식", { t: "105 / 108 (3개월 놓침)", c: "hl" }, "0.124 → 0.147"],
    ["군집당 1개 제약 식", "108 / 108", "0.172 (변화 없음)"],
  ], M, 4.15, CW, [4.1, 4.0, 4.03]);
}
{
  const s = slide("CONTENT_ALT", "발견한 문제 · 개수 벌점 λ", "기존 λ에서는 이징 문제의 정답이 “아무것도 고르지 않기”였다",
    "N=50 결합 4배는 정확히 6개가 되는 λ가 없어 5개(λ=1.411)로 했다. 출처: rqaoa.py lambda_gs, rqaoa_big.jsonl",
    "깊이를 올려 QAOA가 더 좋은 에너지를 찾을수록 선택 개수가 줄어드는 구조였습니다. 큰 N의 기존 결과를 해석할 때 주의해야 합니다.");
  lead(s, "기존 λ는 p=1 QAOA가 평균 6개를 고르도록 맞춘 값이다. 이 λ에서는 1차 항이 모두 음수다.");
  table(s, ["문제", "기존 λ", "기존 λ의 바닥 상태", "다시 맞춘 λ (6개 선택)"], [
    ["N=50", "2.909", { t: "0개 선택", c: "hl" }, "1.359"],
    ["N=100", "4.705", { t: "0개 선택", c: "hl" }, "1.500"],
    ["N=150", "6.196", { t: "0개 선택", c: "hl" }, "1.875"],
  ], M, 2.2, CW, [2.0, 3.2, 3.4, 3.53]);
  bullets(s, [
    "기존 QAOA는 빈 집합을 향해 에너지를 낮추고 있었다. 6개가 나온 것은 깊이가 얕아 거기까지 못 간 결과다.",
    "다시 맞춘 λ의 바닥 상태는 MILP로 구한 변형식의 6개 최적해와 같은 종목이다. 이후 RQAOA는 이 λ를 쓴다. README에 아직 기록되지 않았다.",
  ], M, 4.25, CW, 2.4);
}

// ---------------------------------------------------------------- 4. RQAOA
section("RQAOA 시험");
{
  const s = slide("CONTENT", "RQAOA · 원리", "샘플링 대신 상관값으로 변수를 하나씩 정한다",
    "구현: research/pado_pps/rqaoa.py. 상관값은 정확 계산(N=20) 또는 padopauli(N=50~150)로 구했다.",
    "표준 QAOA는 회로에서 샘플을 뽑아 좋은 해가 나오길 기다립니다. RQAOA는 상관값만 보고 가장 확실한 결정부터 하나씩 내리므로, 확률이 낮아도 방향만 맞으면 됩니다. N=150이면 140단계를 거칩니다.");
  lead(s, "Recursive QAOA (Bravyi 외, PRL 125, 260505, 2020). 1차 항이 있는 문제로 확장해 썼다.");
  const steps = [
    ["QAOA 학습", "현재 남은 변수로 깊이 p 회로의 각도를 학습한다."],
    ["상관값 계산", "모든 ⟨Z_i⟩와 결합된 쌍의 ⟨Z_i Z_j⟩를 구한다."],
    ["하나 결정", "1차 항이면 z_i를 고정하고, 결합이면 z_j = ±z_i로 묶는다."],
    ["대입하고 반복", "변수가 하나 준다. 10개가 남으면 전수 탐색 후 거꾸로 대입한다."],
  ];
  const aw = 0.42, w = (CW - 3 * (aw + 0.2)) / 4;
  steps.forEach(([t, b], i) => {
    const x = M + i * (w + aw + 0.2);
    card(s, x, 2.6, w, 3.2, t, b, C.background2, { text: String(i + 1), color: C.accent1 });
    if (i < 3) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + w + 0.1, y: 4.0, w: aw, h: 0.4, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `arrow-${i + 1}` });
  });
}
{
  const s = slide("CONTENT_ALT", "RQAOA · 결합 4배 N=20", "같은 깊이에서 표준 QAOA보다 훨씬 자주 정답에 닿는다",
    "29개 인스턴스(seed 0~29 중 λ를 맞출 수 없는 1개 제외), 마지막 10개 변수는 전수 탐색. 출처: rqaoa_n20.jsonl, rqaoa_n20_nc4.jsonl",
    "표준 QAOA는 같은 문제에서 바닥 상태를 뽑을 확률이 0.03~0.2%였습니다. RQAOA는 확률이 아니라 상관값의 부호만 맞으면 되기 때문에 훨씬 잘 됩니다. 다만 결정 대부분이 1차 항에서 나왔다는 것은, 확실한 ETF부터 하나씩 정하는 고전적 순차 결정에 가깝다는 뜻입니다.");
  const w = (CW - 2 * 0.35) / 3;
  stat(s, M, 1.85, w, 1.75, "27 / 29", "RQAOA p=1이 바닥 상태를 찾은 인스턴스", C.background1);
  stat(s, M + w + 0.35, 1.85, w, 1.75, "26 / 29", "RQAOA p=2가 바닥 상태를 찾은 인스턴스", C.background1);
  stat(s, M + 2 * (w + 0.35), 1.85, w, 1.75, "0.2% 이하", "표준 QAOA p=1~3의 바닥 상태 확률 (인스턴스 3개)", C.background1, C.accent2);
  bullets(s, [
    "놓친 인스턴스의 에너지 오차는 0.1~1.4%다. 마지막 전수 탐색을 4개로 줄이면 p=1 25/29, p=2 26/29다.",
    "padopauli와 정확 계산이 29개 인스턴스의 모든 단계에서 같은 변수를 골랐다. 상관값 오차는 p=1에서 1e-15, p=2(w=6)에서 1e-4 이하다.",
    "결정의 84~92%는 결합이 아니라 1차 항 ⟨Z_i⟩로 변수를 고정한 것이다.",
  ], M, 3.95, CW, 2.7);
}
{
  const s = slide("CONTENT", "RQAOA · N=50~150, padopauli", "p=1에서 놓친 세 문제를 p=2로 모두 풀었다",
    "p=2는 AMD MI300X GPU에서 계산했다(CPU로는 문제당 하루 이상). GPU 메모리 최대 N=100 148 GB, N=150 27 GB. 출처: rqaoa_big.jsonl, rqaoa_big_p2.jsonl",
    "p=1에서 놓친 세 문제를 p=2로 다시 돌려 모두 바닥 상태를 찾았습니다. 고른 종목 수도 정답과 같은 6개입니다. GPU 메모리는 모두 신뢰 기준 160 GB 이하였습니다. 다만 N=20에서는 p=2가 26개로 p=1의 27개보다 나아지지 않았으므로, 깊이 효과는 문제에 따라 다릅니다.");
  lead(s, "정답은 MILP 바닥 상태. 다시 맞춘 λ, 절단 가중치 w=8, 마지막 10개 변수는 전수 탐색.");
  table(s, ["문제", "p=1 결과", "선택 수 (정답)", "p=1 시간", "p=2 결과"], [
    ["N=50 원래 결합", { t: "정답", c: "ok" }, "6 (6)", "17초", { t: "필요 없음", c: "dim" }],
    ["N=50 결합 4배", { t: "정답", c: "ok" }, "5 (5)", "25초", { t: "필요 없음", c: "dim" }],
    ["N=100 원래 결합", { t: "정답", c: "ok" }, "6 (6)", "84초", { t: "필요 없음", c: "dim" }],
    ["N=100 결합 4배", { t: "오차 0.006%", c: "hl" }, "6 (6)", "103초", { t: "정답 (725초)", c: "ok" }],
    ["N=150 원래 결합", { t: "오차 0.02%", c: "hl" }, "5 (6)", "187초", { t: "정답 (1,203초)", c: "ok" }],
    ["N=150 결합 4배", { t: "오차 8.3%", c: "hl" }, "24 (6)", "256초", { t: "정답 (1,531초)", c: "ok" }],
  ], M, 2.2, CW, [2.9, 2.4, 2.3, 1.9, 2.63]);
  bullets(s, ["p=1은 크기와 결합 세기가 커질수록 나빠졌다(N=150 결합 4배: 140단계 중 17단계가 결합). p=2에서는 세 문제 모두 정답이고, 결합 단계는 8~12개였다."], M, 5.3, CW, 1.3);
}
{
  const s = slide("CONTENT_ALT", "RQAOA · 해석", "잘 맞는 방법이지만 아직 양자 우위의 근거는 아니다",
    "하드웨어 RQAOA는 단계마다 회로를 새로 제출해야 한다. N=20이면 작업 약 16개.",
    "하드웨어로 가기 전에 상관값을 유한 샷 추정치로 바꿔서 성공률이 얼마나 떨어지는지 먼저 보는 것이 순서입니다.");
  const w = (CW - 2 * 0.35) / 3;
  card(s, M, 1.95, w, 3.5, "잘 된 점", "N=150까지 6개 문제 모두 정답을 찾았다(3개는 p=2). 표준 QAOA 샘플링은 N=20에서도 바닥 상태 확률이 0.2% 이하였다.", C.background1, { text: "+", color: C.accent1 });
  card(s, M + w + 0.35, 1.95, w, 3.5, "한계", "p=1 RQAOA는 고전적으로 정확히 계산할 수 있고, padopauli도 고전 시뮬레이터다. 1차 항이 강해 확실한 ETF부터 정하는 고전 순차 결정에 가깝다.", C.background1, { text: "−", color: C.accent2 });
  card(s, M + 2 * (w + 0.35), 1.95, w, 3.5, "양자가 의미를 가질 조건", "고전 계산이 어려워지는 문제와 깊은 회로다. 어려운 문제는 찾았지만, 그 문제에서 시험한 양자 방법은 모두 고전에 못 미쳤다(다음 섹션).", C.background1, { text: "?", color: C.accent1 });
}

// ---------------------------------------------------------------- 4b. hard problems
section("어려운 문제와 양자 방법");
{
  const s = slide("CONTENT", "MILP가 느려지는 구조", "결합이 촘촘하고 강하며 부호가 섞이면 증명이 느려진다",
    "288문제(N=50·100·150 × k=6·15 × 쌍 항 3종 × 밀도 4 × 세기 4), HiGHS 단일 스레드 300초, 미증명 10개는 1시간 재실행. 세기 ×1은 쌍 항 크기가 점수 차이와 비슷하다는 뜻이다. 출처: hard.md 결과 1~3",
    "부호가 섞인 쌍 항은 상관에서 중앙값을 빼거나 부호를 무작위로 만든 인위적 변형입니다. 실제 ETF 상관은 중앙값 0.34, 음수 14%이고 첫 요인이 39%를 설명해서, 평균-분산 식은 쉬운 쪽에 있습니다. 증명이 막힌 문제에서도 스왑 탐색은 1초 안에 같은 최적해를 찾았습니다.");
  table(s, ["조건", "결과"], [
    ["300초 안에 증명", "278 / 288"],
    ["1시간 재실행으로 증명", "6개 (378~2,692초)"],
    ["1시간에도 미증명", { t: "4개, 모두 N=150 k=15 부호 섞임 (갭 5.9~42%)", c: "hl" }],
    ["실무형 평균-분산 (cov, 모든 쌍, ×1), N=150", { t: "5.5초 (k=6), 9.2초 (k=15)", c: "ok" }],
    ["스왑 탐색 101회가 최적해를 찾은 문제", "증명된 284개 중 283개"],
  ], M, 1.95, CW, [5.6, 6.53], 15, 0.5);
  bullets(s, [
    "MILP 시간은 결합 세기 ×4 이상, 밀도 30% 이상, 부호 섞임이 겹칠 때 늘고, N과 k가 클수록 길어진다.",
    "이 크기에서는 \"최적임을 증명하기\"가 \"좋은 답 찾기\"보다 먼저 어려워진다.",
  ], M, 5.45, CW, 1.3, C.text2, 14);
}
{
  const s = slide("CONTENT_ALT", "어려운 12문제 · 방법별 결과", "양자 방법은 0/12, 개수를 지키는 고전 탐색은 12/12다",
    "MILP가 128~2,692초 걸려 증명한 12문제. 양자 방법은 고전 시뮬레이션(정확 계산). SQA 설정은 12문제 중 2개로 골랐다. 임베딩 SA의 제어 오차는 가정값. 출처: hard.md 결과 4~8",
    "RQAOA는 개수 벌점이 상관값을 덮어 46개를 고르기도 했습니다. 개수 세기로 그 문제를 막고 빔으로 경로를 늘려도 0/12였고, 같은 절차의 고전판(seqfix)과 6:6으로 비겼습니다. XY 믹서는 벌점이 없지만 p=1 링 믹서가 이웃끼리만 비교해서 오히려 정보가 적었습니다. 벌점 QUBO에서는 고전 어닐링류도 0~3/12였고, 칩에 올리면 목적식 결합이 하드웨어 단위로 약 0.0001까지 줄어 정밀도에 묻혔습니다.");
  table(s, ["방법", "개수 처리", "최적해", "갭 (못 찾은 문제)", "문제당 시간"], [
    ["스왑 탐색 · 개수 유지 SA (고전)", "개수 유지", { t: "12 / 12", c: "ok" }, "—", "1~3초"],
    ["SQA · 병렬 템퍼링 (고전)", "2차 벌점", "3 / 12 · 2 / 12", "1.1~9.6%", "약 20초"],
    ["한 비트 SA (고전)", "2차 벌점", { t: "0 / 12", c: "hl" }, "1.2~14.5%", "0.5초"],
    ["RQAOA p=1", "2차 벌점", { t: "0 / 12", c: "hl" }, "0.5~18% (1문제 46개 선택)", "2~19분"],
    ["RQAOA + 개수 세기 + 빔 5", "벌점 + 개수 확인", { t: "0 / 12", c: "hl" }, "0.4~91%", "최대 94분"],
    ["XY 믹서 + 디키 상태 QAOA", "개수 유지", { t: "0 / 12", c: "hl" }, "3.2~86%", "5~26분 (GPU)"],
    ["임베딩 SA (QPU 약점 모형)", "2차 벌점", { t: "0 / 12", c: "hl" }, "잡음 넣으면 k개 지킨 답 0%", "약 50초"],
  ], M, 1.95, CW, [3.7, 2.0, 1.6, 3.13, 1.7], 13, 0.5);
}
{
  const s = slide("CONTENT", "양자 샘플 하이브리드와 D-Wave", "양자 샘플은 이득이 없었고, D-Wave는 돌리지 못했다",
    "하이브리드: N=20, k=5 문제 40개, 측정 100회, 문제 단위 부트스트랩. D-Wave: 접속·토큰·임베딩은 확인, 1회 시험 제출은 \"남은 QPU 시간 부족\"으로 거절(비용 없음). 출처: hard.md 결과 9",
    "작은 문제에서 진짜 양자 샘플을 뽑아 국소탐색 시작점으로 썼습니다. XY 완전 그래프 믹서 p=3 샘플은 최적해가 나올 확률이 무작위의 237배였지만, 국소탐색 후 성공률은 무작위 시작점과 구분되지 않았습니다. 큰 문제에서는 정확히 계산한 p=1 확률이 거의 균일해서 무작위와 같았습니다. D-Wave 실행 준비는 끝났지만 계정의 QPU 시간이 0초입니다.");
  const w = (CW - 2 * 0.35) / 3;
  stat(s, M, 1.95, w, 1.9, "237배", "XY 완전 그래프 p=3에서 측정 1회에 최적해가 나올 확률, 무작위 대비 (p=1 35배, p=2 103배)", C.background2);
  stat(s, M + w + 0.35, 1.95, w, 1.9, "+1.3%p", "그 샘플을 시작점으로 쓴 국소탐색 성공률, 무작위 대비 (95% 구간 −1.1 ~ +3.6)", C.background2, C.accent2);
  stat(s, M + 2 * (w + 0.35), 1.95, w, 1.9, "0초", "D-Wave 계정의 남은 QPU 시간. 시험 제출 1회는 거절됐다", C.background2, C.accent2);
  bullets(s, [
    "무작위 시작 + 국소탐색의 성공률은 76%로, 가장 좋은 양자 측정 1회(2.6%)의 약 30배다. 양자 샘플은 비용이 낮은 쪽으로 몰리지만, 최적해로 이어지는 골짜기로 몰아주지는 못했다.",
    "어려운 12문제에서 RQAOA 최종 답에 국소탐색을 붙이면 9/12, 같은 절차의 고전판도 9/12였다.",
    "D-Wave에 벌점 QUBO로 올리면 정밀도에 묻힐 가능성이 크다. 시험하려면 개수 제약을 지원하는 하이브리드 솔버나 희소한 정식화가 필요하다.",
  ], M, 4.2, CW, 2.5, C.text2, 14);
}

{
  const s = slide("CONTENT_ALT", "크기 키우기 · N=16→28", "N이 커질수록 양자와 고전의 격차가 벌어졌다",
    "N마다 20문제(k=N/4, 쌍 항 강화 ×4·×16). 디키 시작 XY 완전 그래프 QAOA, 무게 k 부분공간 정확 계산(N=28은 118만 차원, GPU), 측정 200회. 고전은 무작위 시작 1,000개 + 스왑 국소탐색. 측정·재시작 수는 기하평균, 구간은 부트스트랩. 출처: hard.md 결과 10",
    "양자 샘플의 이득이 N에 따라 고전 국소탐색보다 빨리 커지는지 봤습니다. 무작위 대비 배수는 커졌지만 경우의 수가 더 빨리 늘어 측정 1회 최적해 확률은 줄었습니다. 고전 국소탐색 성공률은 거의 줄지 않아, 필요한 시도 수의 격차가 10배에서 130배로 벌어졌습니다. 하이브리드 이득도 N=24부터 0과 구분되지 않았습니다. 각도는 기대 비용으로 학습했고 p는 3까지입니다.");
  table(s, ["N", "차원", "무작위 대비 배수 (p=3)", "측정 1회 최적해 확률", "필요 측정 수 (양자)", "국소탐색 성공률 (고전)", "필요 재시작 수 (고전)", "하이브리드 이득"], [
    ["16", "1,820", "150배", "8.2%", "13회", "81%", "1.3회", { t: "+4.6%p", c: "ok" }],
    ["20", "15,504", "597배", "3.9%", "28회", "73%", "1.5회", { t: "+3.2%p", c: "ok" }],
    ["24", "134,596", "1,913배", "1.4%", { t: "80회", c: "hl" }, "68%", "1.6회", { t: "+1.1%p (0 포함)", c: "dim" }],
    ["28", "1,184,040", "5,654배", "0.48%", { t: "222회", c: "hl" }, "70%", "1.65회", { t: "+1.0%p (0 포함)", c: "dim" }],
  ], M, 1.95, CW, [0.7, 1.4, 1.65, 1.6, 1.55, 1.65, 1.6, 1.98], 13, 0.52);
  bullets(s, [
    "무작위 대비 배수는 대략 D^0.56으로 커졌지만, 측정 1회 최적해 확률은 D^−0.44로 줄었다(D는 경우의 수).",
    "고전에 필요한 재시작 수는 1.3 → 1.65회로 거의 그대로다. 두 추세가 만나는 지점은 보이지 않는다.",
    "무작위 시작 성공률이 50% 아래인 어려운 20문제만 봐도 하이브리드 이득은 p=3에서 +0.0%p였다.",
  ], M, 4.75, CW, 2.0, C.text2, 14);
}
{
  const s = slide("CONTENT", "학습 기준 바꾸기 · CVaR", "CVaR 학습은 사전 기준을 넘었지만, 격차는 약 50배로 남았다",
    "같은 80문제, 같은 회로(p=3). 각도만 CVaR_α(비용이 낮은 쪽 α의 평균)로 학습했고, 기대 비용 학습 각도도 시작점에 넣었다. 측정·재시작 수는 기하평균, 구간은 문제 단위 부트스트랩. 판정 기준은 실행 전 cvar.py에 고정. 출처: hard.md 결과 14",
    "크기 키우기 결과가 학습 기준 탓인지 보려고 각도를 CVaR로 다시 학습했습니다. 실행 전에 N=24, 28에서 (a) 무작위 대비 배수가 중앙값 2배 이상 오르거나 (b) 하이브리드 성공률이 5%p 이상 오르면 결론이 바뀐 것으로 보기로 정했습니다. 상위 10%로 학습하면 (a)가 2.11배로 충족됐고, (b)는 1.5%p로 미달이었습니다. 양자 샘플은 분명히 좋아졌지만 N=28에서 측정 82회 대 고전 재시작 1.65회로, 격차는 130배에서 50배로 줄었을 뿐입니다. 상위 1%로 학습하면 평균 학습 각도의 최적해 확률이 이미 1%를 넘는 문제에서 기울기가 0이 되어 거의 움직이지 않았습니다.");
  lead(s, "p=3. 화살표는 기대 비용 학습 → CVaR 10% 학습. 배수 비·하이브리드 차이는 CVaR 10% 대 기대 비용.");
  table(s, ["N", "배수 비", "최적해 확률", "필요 측정 수 (양자)", "측정 수 (CVaR 1%)", "필요 재시작 수 (고전)", "하이브리드 차이"], [
    ["16", "1.31배", "8.2% → 10.7%", "13 → 10회", "13회", "1.3회", { t: "+0.7%p (0 포함)", c: "dim" }],
    ["20", "1.57배", "3.9% → 7.8%", "28 → 16회", "28회", "1.5회", { t: "+2.3%p", c: "ok" }],
    ["24", { t: "1.81배", c: "ok" }, "1.4% → 3.0%", "80 → 39회", "62회", "1.6회", { t: "+1.4%p (0 포함)", c: "dim" }],
    ["28", { t: "2.44배", c: "ok" }, "0.48% → 1.4%", { t: "222 → 82회", c: "hl" }, "115회", "1.65회", { t: "+1.5%p (0 포함)", c: "dim" }],
  ], M, 2.15, CW, [0.7, 1.45, 1.95, 1.95, 1.75, 1.75, 2.58], 13, 0.5);
  bullets(s, [
    "사전 기준(N=24·28, p=3): (a) 배수 비 중앙값 ≥ 2배 → 2.11배로 충족. (b) 하이브리드 +5%p → +1.5%p [+0.2, +2.9]로 미달.",
    "최적해 확률의 감소가 D^−0.44에서 D^−0.33으로 느려졌다. 그래도 계속 줄어서, 두 추세가 만나는 지점은 여전히 보이지 않는다.",
    "CVaR 1%는 N=16·20에서 하나도 움직이지 않았다. 평균 학습 각도의 최적해 확률이 이미 1%를 넘어 기울기가 0이다.",
  ], M, 4.95, CW, 1.8, C.text2, 14);
}
{
  const s = slide("CONTENT_ALT", "실기기 가능성 · 로컬 회로 변환", "N=100 어려운 문제는 실기기 출력이 잡음에 묻힌다",
    "IBM 계정 접속 없이 변환만 했다. Nighthawk형 10×12 격자와 FakeFez(Heron), optimization level 3. 남는 신호 ≈ exp(−6.1e-4 × CZ), 11-09 ibm_phoenix N=20 실측 16개 회로에 맞춘 낙관적 추정. 출처: hard.md 결과 11·12",
    "어려운 12문제를 실기기에서 돌려 목적식 점수로 비교하는 안을 검토했습니다. 먼저 무작위 답의 기준선을 구했고, 회로를 로컬에서 변환했습니다. 가장 가벼운 회로도 CZ가 1만 개를 넘어, 11월 9일 실측 관계로 보면 남는 신호가 0.1% 이하입니다. 표준 회로에서 무작위 비트열이 정확히 15개를 고를 확률은 2×10⁻¹³이라 개수를 지킨 답도 거의 없습니다. 실기기가 의미 있는 크기(N≲30)는 정확한 시뮬레이션이 가능하고 고전이 앞선 크기입니다.");
  table(s, ["회로", "CZ 수", "2큐비트 깊이", "남는 신호"], [
    ["11-09 실측 · N=20 결합 4배 (16개 회로)", "83~375", "22~107", { t: "75~94%", c: "ok" }],
    ["11-09 실측 · N=100 ETF당 3쌍", "599", "—", { t: "73%", c: "ok" }],
    ["어려운 N=100 · 결합 30% · XY 믹서 · 격자", "10,782", "2,459", { t: "0.14% (추정)", c: "hl" }],
    ["어려운 N=100 · 전체 쌍 · 표준 · SWAP 네트워크", "14,850", "300", { t: "0.01% (추정)", c: "hl" }],
    ["어려운 N=100 · 전체 쌍 · XY 믹서 · Heron", "16,103", "1,032", { t: "0.005% (추정)", c: "hl" }],
  ], M, 1.95, CW, [6.0, 1.9, 2.0, 2.23], 14, 0.5);
  bullets(s, [
    "판정 기준선(결과 11): 무작위 k개 1,000~10,000개 중 최고 점수의 갭이 12~55%다. 잡음 없는 RQAOA는 0.4~17%, 스왑 탐색은 0%다.",
    "모든 쌍을 잇는 문제에서 남는 신호 추정: N=20 71%, N=28 50%, N=40 24%, N=50 11%.",
    "N=100 어려운 문제는 제출하지 않는 것을 제안한다. 결과가 무작위와 같을 것이 거의 확실하다.",
  ], M, 5.1, CW, 1.7, C.text2, 14);
}
{
  const s = slide("CONTENT", "양자 방법 종합 비교", "목적별로 가장 나은 양자 방법도 고전 국소탐색에는 못 미쳤다",
    "SQA·RQAOA·XY-QAOA는 모두 고전 컴퓨터에서 정확히(또는 모사로) 계산했다. 갭은 최적값 대비 상대 차이. 출처: hard.md 결과 4~12",
    "파트너에게는 이렇게 설명하는 것이 방어하기 쉽습니다. XY 완전 그래프 QAOA가 원리상 가장 좋은 샘플러였고 SQA가 어려운 문제에서 가장 좋은 점수를 냈지만, 어느 방법도 개수를 지키는 고전 국소탐색을 넘지 못했고 크기를 키우면 격차가 벌어졌습니다. CVaR로 학습해도 약 50배 격차가 남았습니다.");
  table(s, ["목적", "가장 나은 양자 방법", "결과", "한계"], [
    ["어려운 문제의 점수", "SQA (양자 어닐링 모사)", "3 / 12, 갭 1.2~4.2%", "칩 임베딩까지 모사하면 k개 지킨 답 0%"],
    ["게이트형 대표", "RQAOA + 개수 세기 + 빔", "0 / 12, 갭 중앙값 약 5%", "같은 절차의 고전판과 6승 6패"],
    ["샘플러 품질", "XY 완전 그래프 QAOA", "N=28 p=3에서 무작위의 5,654배", "필요 측정 수 13 → 222회 (CVaR로 82회), 고전 1.65회"],
    ["실기기 실행", "IBM ibm_phoenix", "N=20에서 신호 75~94% 유지", "N=100 어려운 문제는 신호 0.1% 이하"],
    [{ t: "기준: 고전 스왑 탐색", c: "ok" }, "—", { t: "12 / 12, 문제당 1~3초", c: "ok" }, "MILP 증명 없이도 최적해를 찾는다"],
  ], M, 1.95, CW, [2.4, 3.0, 3.2, 3.53], 14, 0.58);
  bullets(s, [
    "각도를 CVaR(상위 10%)로 학습하면 양자 샘플은 약 2배 좋아지지만, N=28에서 고전과의 격차는 여전히 약 50배다.",
  ], M, 5.85, CW, 0.9, C.text2, 15);
}

// ---------------------------------------------------------------- 5. investment
section("선택 식의 투자 성과");
{
  const s = slide("CONTENT_ALT", "선택 식의 투자 성과", "최적해를 찾아도 식의 성과는 무작위 6개 수준이다",
    "양자 최적화는 쓰지 않은 실험이다. PADO 변형식은 2017~2026년 0.12(이전 기간 측정 안 함). 출처: bt.md, diag.md",
    "점수 순위와 다음 달 수익 순위의 상관은 평균 +0.024(t=0.90)로 예측력이 확인되지 않습니다. 상관 벌점은 변동성과 수익을 함께 낮춥니다. 이 문제는 양자와 별개입니다.");
  lead(s, "매월 말 최적 6개를 동일가중으로 한 달 보유한 샤프비율 (편도 거래비용 10bp, 단기국채 초과수익 기준).");
  const labels = ["MaiQ 원래 식", "점수 상위 6개", "무작위 6개", "전 종목 동일가중", "SPY"];
  s.addChart(pres.charts.BAR, [
    { name: "2017-11 ~ 2026-11 (148개)", labels, values: [0.33, 0.44, 0.29, 0.48, 0.67] },
    { name: "2008-05 ~ 2016-10 (101개)", labels, values: [0.12, 0.24, 0.16, 0.29, 0.43] },
  ], {
    x: M, y: 2.2, w: 7.6, h: 4.45, barDir: "bar", barGrouping: "clustered", barGapWidthPct: 50,
    chartColors: [THEME.colors.accent1, THEME.colors.accent4],
    showTitle: true, title: "샤프비율", titleFontSize: 14, titleColor: THEME.colors.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: THEME.colors.dk2, dataLabelFontFace: "+mn-lt",
    dataLabelFormatCode: "0.00",
    catAxisLabelColor: THEME.colors.dk2, valAxisLabelColor: THEME.colors.accent3, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", valAxisMaxVal: 0.8, valAxisLabelFormatCode: "0.0",
    catAxisOrientation: "maxMin",
    valGridLine: { color: "E3E7ED", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: THEME.colors.dk2, legendFontFace: "+mn-lt",
    objectName: "chart-sharpe",
  });
  bullets(s, [
    "원래 식과 동일가중의 차이는 두 기간 모두 −0.16이지만 95% 신뢰구간이 0을 포함한다.",
    "무작위 6개(0.29)가 전 종목 동일가중(0.48)보다 낮다. 6개만 보유하는 것 자체가 불리하다.",
    "점수의 예측력은 확인되지 않는다. 점수 순위와 다음 달 수익 순위의 상관은 +0.024다.",
  ], 8.55, 2.35, 4.18, 4.2, C.text2, 14);
}
{
  const s = slide("CONTENT", "문헌 기반 수정 후보 · 사전등록", "수정안 중 확정된 것은 없다",
    "사전등록 cand_prereg.md, oos_prereg.md. 출처: cand.md, oos.md",
    "위험 회피 세기의 최적값은 시기에 따라 뒤집힙니다. 원래 세기는 2008~2016년에 가장 좋았고 2017~2023년에 가장 나빴습니다. 공분산 위험 항을 쓰려면 새 데이터로 먼저 검증해야 합니다.");
  lead(s, "원래 식 대비 샤프 차이. 2017~2023 선택, 2023~2026 확인, 2008~2016 독립 검증.");
  table(s, ["후보", "2008~2012", "2012~2016", "2017~2023", "2023~2026"], [
    ["12-1 모멘텀 신호", { t: "−0.26", c: "hl" }, "+0.13", "+0.20", "+0.49"],
    ["공분산 위험 항, 약함", "+0.18", "+0.16", "+0.19", "+0.12"],
    ["공분산 위험 항, 중간", "+0.32", "+0.25", "+0.06", "+0.06"],
    ["공분산 위험 항, 원래 세기", "+0.89", "+0.43", { t: "−0.22", c: "hl" }, "+0.02"],
    ["추세 필터", "+0.10", { t: "−0.02", c: "hl" }, "+0.02", "+0.04"],
    ["변동성 역수 비중", "+0.16", { t: "−0.13", c: "hl" }, "+0.20", { t: "−0.06", c: "hl" }],
  ], M, 2.2, CW, [3.93, 2.05, 2.05, 2.05, 2.05]);
  bullets(s, ["12-1 모멘텀은 독립 검증에서 기각됐다. 공분산 위험 항(약함·중간)은 네 구간 모두 앞섰지만 결과를 본 뒤의 관찰이고, 통계적으로 확정되지 않는다."], M, 5.4, CW, 1.2);
}

// ---------------------------------------------------------------- 6. wrap-up
section("종합, 결정 사항, 다음 단계");
{
  const s = slide("STATEMENT", "종합 해석", "“양자가 수익을 높인다”가 아니라\n“정해진 식의 최적해를 정확히 찾는 절차와 그 한계”로 설명한다", null,
    "파트너에게 설명할 때 가장 방어하기 쉬운 표현입니다. 다만 지금 크기에서는 고전 방법으로도 같은 최적해가 정확히 나온다는 점을 함께 밝혀야 합니다.");
  bullets(s, [
    "지금 ETF 문제는 1차 항이 지배적이라 양자에 유리하지 않다. 같은 최적해가 고전 MILP로 몇 초 만에 나온다.",
    "MILP가 느려지는 어려운 문제에서도 개수를 지키는 고전 탐색이 수 초 만에 풀었고, 시험한 양자 방법(RQAOA 변형, XY 믹서 QAOA, 양자 샘플 하이브리드)은 모두 못 미쳤다. 크기를 키우면 격차가 벌어졌고, CVaR로 학습해도 약 50배가 남았다.",
    "식의 투자 성과는 양자와 별개의 문제이고, 원래 식과 수정안 모두 성과가 확인되지 않았다.",
  ], M + 0.2, 3.85, CW - 0.4, 2.8, C.accent6, 16);
}
{
  const s = slide("CONTENT", "결정이 필요한 사항", "다섯 가지를 정해야 한다",
    "버그 재현 조건: N=50, d=3, p=4, w=6, 고정 각도. GPU 피크가 한계에 닿으면 −83.67 대신 −9.38이 나온다.",
    "앞의 세 가지는 MaiQ에 요청할 사항이고, 뒤의 두 가지는 사내에서 정할 사항입니다.");
  table(s, ["결정", "누가", "제안"], [
    ["목적식 유지 또는 위험 항 교체", "MaiQ", "유지한다. 바꾸려면 새 데이터로 먼저 검증한다."],
    ["보유 개수 6개 유지 여부", "MaiQ", "6개 집중이 불리하다는 결과를 공유한다."],
    ["검증용 ETF 목록과 가격 제공", "MaiQ", "요청한다. 가진 데이터는 모두 사용했다."],
    ["padopauli 버그 제보", "사내 PADO 담당", "바로 제보한다. 재현 조건이 정리돼 있다."],
    ["양자 쪽 목표", "사내", "CVaR로 샘플은 약 2배 좋아졌지만 격차는 약 50배다. 깊은 회로로 추세만 한 번 더 보고, 바뀌지 않으면 정리한다. 실기기는 작은 크기의 잡음 측정만 한다."],
  ], M, 1.95, CW, [3.9, 2.0, 6.23], 15, 0.62);
}
{
  const s = slide("CONTENT_ALT", "다음 단계", "양자 쪽은 깊은 회로에서 CVaR 추세를 한 번 더 보고 판단한다", null,
    "CVaR 학습은 실행 전에 정한 기준 (a)를 넘었으므로, 예정대로 바로 정리하지 않고 한 번 더 확인합니다. 다만 N=28 격차가 아직 약 50배이고 추세가 만나는 지점이 보이지 않아, 결론이 뒤집힐 가능성은 낮습니다. 3~4번은 문서와 파트너 쪽 일입니다.");
  numberedRows(s, [
    ["깊은 회로로 CVaR 추세 확인.", "CVaR 10%는 사전 기준 (a)를 넘었지만 N=28 격차는 약 50배다. p=4~6과 α 조정으로 N에 따른 추세가 바뀌는지만 보고, 바뀌지 않으면 양자 쪽은 정리한다."],
    ["실기기는 잡음 한계 측정으로만.", "IBM에서 N=8~20 XY-QAOA로 신호가 남는 크기를 실측한다. N=100 어려운 문제는 제출하지 않는 것을 제안한다. D-Wave는 QPU 시간을 확보하면 개수 제약 하이브리드 솔버로 시험한다."],
    ["README와 보고서 정리.", "MILP 난이도 지도, 어려운 문제, 하이브리드, 크기 키우기, CVaR, 실기기 변환 결과를 반영한다."],
    ["MaiQ에 결과 공유.", "결정 세 가지를 요청하고, 공분산 위험 항은 새 데이터로 검증한다."],
  ], 2.0, 1.02);
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
