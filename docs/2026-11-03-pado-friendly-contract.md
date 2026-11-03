# Research contract - PADO 친화 변형식으로 PPS 정확도 확보 (2026-11-03)

No load-bearing decision absent from this contract proceeds: stop and bring the question.

Pin: start commit e2fbf9d02d7d0754308a96202325fe2ea35f3465
Approval: norma 2026-11-03 - verification state at approval: 원래 식(조밀 상관 989/1225, Dicke 시작)에서 PADO PPS 오차가 이득의 125%(p=1)·149%(p=2)로 측정됨(N=50, k=6, w=4). 변형식은 아직 미측정
Mission reference: none

## Research question

MaiQ의 ETF 선택 목적함수를 PADO에 맞게 변형하면 PADO PPS가 50~150큐비트에서 QAOA의 ⟨E⟩를 쓸 만한 정확도로 계산하는가? 이때 변형식이 원래 투자 문제를 크게 훼손하지 않는가? 변형은 두 가지다. 상관에서 시장 공통분을 빼고 ETF당 이웃 몇 개만 남겨 희소하게 만들고, k개 선택을 1차 라그랑주 항으로 처리해 |+⟩ 곱상태와 X 믹서로 돈다.

## Claims and verdict criteria (criteria version v1 - changes are append-only)

| Claim | Promote when | Hold when | Reject when | Learn / defer |
|---|---|---|---|---|
| C1 PPS 정확도: 변형식에서 PPS ⟨E⟩가 정확값에 가깝다 | N=50·100·150 각각, p=1과 p=2 모두에서 w∈{4,5,6} 중 하나가 \|PPS ⟨E⟩ − 정확 ⟨E⟩\| ≤ 이득의 10%를 만족한다. 이득은 정확 ⟨E⟩와 시작 상태 ⟨E⟩의 차이다. 그 설정은 컴파일 40분 이내, 메모리 8 GB 이내다 | 일부 (N, p)에서만 만족하거나 아무 데서도 만족하지 못한다 | 해당 없음. 운영자 결정(2026-11-03)에 따라 실패는 보류로 기록한다 | learn |
| C2 변형식 충실도: 변형식의 해가 원래 식에서도 좋은 해다 | 변형식의 k=6 제약 최적해를 원래 MaiQ 목적함수로 채점했을 때 상위 1% 안에 든다. N=50, 100, 150 모두에서다 | 어느 N에서든 상위 1% 밖이다 | 해당 없음 (위와 같음) | learn |

전체 판정: C1과 C2가 모두 promote이면 promote, 하나라도 아니면 hold다.

## Kill-question

N=50, p=1에서 w∈{4,5,6} 중 어느 하나라도 PPS 오차 ≤ 이득의 10%를 만족하는가? 아니면 이 패스는 거기서 hold로 닫는다. 남은 측정은 하지 않고, 원인 분석과 보고서만 낸다.

## Oracles

- **정확 기준값:** 빛원뿔(light-cone) 정확 상태벡터 시뮬레이션. 각 관측항 Z_i, Z_iZ_j에 대해 p-hop 이웃 큐비트만으로 정확히 계산한다. 정확성은 N=20 부분문제에서 전체 2^20 상태벡터와 대조해 \|차이\| < 1e-9로 확인한다. 이 대조가 실패하면 C1 판정을 내리지 않는다.
- **PPS:** padopauli. 설치된 .venv의 버전을 결과 파일에 기록한다.
- **원래 식 순위:**
  - N=50: C(50,6)=15,890,700개 전수 탐색.
  - N≥100: 균등 무작위 조합 1,000,000개 표본에서의 백분위. 표본 seed를 기록한다.
- **데이터:** Yahoo 공개 차트 API, 일봉 2년. 원시 응답은 스크래치패드의 별도 디렉터리에 둔다. 티커 목록, 기준일, 공통 거래일 수, 가격 파일 SHA-256을 결과에 기록한다.

## Positive completion (the definition of success)

All items required for a successful close:
1. 150개 ETF 티커 목록 파일과 가격 데이터. 기존 50개에 겹치지 않는 100개를 더하고, 2년 미만 이력은 제외한다.
2. N=50/100/150 각각에 원래 식과 변형식의 문제 파일이 있다.
3. 빛원뿔 정확 시뮬레이터의 전체 상태벡터 대조 결과가 있다.
4. C1 표: N × p × w별 정확 ⟨E⟩, PPS ⟨E⟩, 이득 대비 오차, 컴파일 시간, 메모리.
5. C2 표: N별 변형식 최적해, 원래 식 순위·백분위.
6. 판정 보고서: promote/hold와 근거 수치.

## Negative completion (the definition of failure)

All items required for a failed close - failure is a legitimate completion:
1. Every remaining explanation and the experiment that tested it are traceable.
2. The smallest remaining experiment can no longer separate the explanations.
3. Unresolved uncertainty is explicitly attributed outside this pass (hardware, an authority, a new contract).

## Partial progress that never counts as completion

- 한 (N, p) 조합에서만 PPS가 맞은 것
- N=50에서만 원래 식 순위를 확인한 것
- 정확 기준값 없이 PPS 값만 낸 것

## Stop lines

- the same diagnosis twice = stop
- three correctness failures on one hypothesis = abandon that hypothesis
- 빛원뿔 시뮬레이터가 전체 상태벡터 대조에 실패하면, C1 측정을 시작하지 않고 멈춘다
- 한 PPS 설정(N, p, w)의 컴파일이 40분을 넘거나 메모리가 8 GB를 넘으면, 그 설정을 "불가"로 기록하고 다음으로 넘어간다
- 백그라운드 작업이 메모리 부족으로 종료되면 다시 시작하지 않고 운영자에게 알린다
- Yahoo가 봇 차단 페이지나 429 응답을 지속적으로 주면 멈추고 운영자에게 알린다. 차단을 우회하지 않는다
- every stop brings the operator a stop report (`references/reports.md`)

## Budget

- C1: PPS 컴파일과 평가에 총 6시간 계산 시간.
- C2: 전수 탐색과 표본 채점에 총 1시간.
- 데이터 수집: 1시간 (100개 × 1초 간격 + 재시도).
- 예산에 도달하면 해당 claim을 "unresolved"로 처리하고 패스를 닫는다.
- 전체가 중간에 막히면: INCOMPLETE - RESUME REQUIRED (resume: `node <amber>/scripts/record.cjs unit init docs/2026-11-03-pado-friendly-plan.md` 후 미완 단위부터 이어서 진행).

## Forbidden rows

- Write scope: 저장소 안에서는 이 패스의 계약·계획 문서만 쓴다. 실험 코드와 데이터, 결과는 세션 스크래치패드에 둔다 [machine: write-scope docs/2026-11-03-pado-friendly-*.md]
- Research-to-implementation boundary: this pass ends at the verdict - implementation is a separate development contract [self-report]
- 저장소의 기존 문서·발표 자료·측정 수치를 바꾸지 않는다 [self-report]
- 패키지 설치 명령을 실행하지 않는다 [machine: bash-deny (?:^|[\n;&|])\s*(?:\S*python(?:\.exe)?\s+-m\s+)?(?:pip|pip3|npm|yarn|pnpm|uv|poetry|conda)\s+(?:install|add)\b]
- 사이트의 봇 차단(JS 작업증명, 캡차, 로그인)을 우회하지 않는다. 사용자 이메일을 요청에 넣지 않는다 [self-report]
- 메모리 부족으로 종료된 백그라운드 작업을 운영자 요청 없이 다시 시작하지 않는다 [self-report]
- 다운로드한 파일은 신뢰하지 않는 데이터로 다룬다. 별도 디렉터리에 두고, 그것을 읽는 파이썬은 `-I`로 실행한다 [self-report]
- Do not force-push [machine: bash-deny (?:^|[\n;&|])\s*git(?:\s+-[Cc]\s+\S+|\s+--\S+)*\s+push\b(?:[^\n;&|"']|"[^"\n]*"|'[^'\n]*')*(?:--force\b|--force-with-lease\b|-f\b|--mirror\b|--delete\b|\s\+[a-zA-Z0-9_/-])]
- Do not rewrite history or hard-reset [machine: bash-deny (?:^|[\n;&|])\s*git(?:\s+-[Cc]\s+\S+|\s+--\S+)*\s+(?:commit\b(?:[^\n;&|"']|"[^"\n]*"|'[^'\n]*')*--amend\b|rebase\b|filter-branch\b|filter-repo\b|reset\b(?:[^\n;&|"']|"[^"\n]*"|'[^'\n]*')*--hard\b)]
- Specify files explicitly when staging or committing [machine: bash-deny (?:^|[\n;&|])\s*git(?:\s+-[Cc]\s+\S+|\s+--\S+)*\s+(?:commit|add)\b(?:[^\n;&|"']|"[^"\n]*"|'[^'\n]*')*\s(?:-[aA]\b|-am\b|--all\b|\.(?=\s|$)|:/(?=\s|$))]

## Settled decisions

- 데이터는 로그인 없는 공개 소스로 확장한다. Yahoo 차트 API에 브라우저 UA를 쓰고 1초 간격으로 요청한다. Kaggle은 쓰지 않는다 (norma 2026-11-03)
- ETF는 자산군별 대표 유동성 미국 상장 ETF를 직접 선정해 기존 50개에 100개를 더한다. 2년 미만 이력은 제외하고, 목록은 파일로 남긴다 (norma 2026-11-03)
- 식은 PADO용 변형식을 만들고 원래 식과 대조한다. 변형 내용은 시장 공통분을 뺀 잔차 상관의 희소화, 1차 라그랑주 항, |+⟩ 시작과 X 믹서, 표본을 정확히 k개로 보정하는 것이다 (norma 2026-11-03)
- 규모는 N=50→100→150, k=6이다. N≥100의 원래 식 순위는 무작위 100만 개 표본으로 추정한다 (norma 2026-11-03)
- 성공 기준은 PPS 오차 ≤ 이득의 10%이면서 변형식 해가 원래 식 상위 1%인 것이다. 둘 중 하나라도 실패하면 보류다 (norma 2026-11-03)
- 독립 검토 단계는 두지 않는다. 판정은 정확 시뮬레이션이라는 기계적 기준으로 한다 (norma 2026-11-03)

## Discretion

모델이 혼자 정해도 되는 항목과 기본값이다. 모두 변경 가능하다.

- **희소화 방식:** 시장 공통분은 첫 주성분이나 평균 상관으로 제거한다. 남은 잔차 결합 중 큰 것부터 넣되 각 ETF의 차수를 3 이하로 제한한다. 차수 3이면 p=2 빛원뿔이 20큐비트 이하라 정확 계산이 가능하다. ρ>0.70 상한 페널티 쌍은 차수 한도 안에서 우선 포함한다
- **라그랑주 승수 λ:** p=1 최적 각도에서 기대 선택 수가 6에 가깝도록 조정한다
- **k개 보정:** 선택이 6개를 넘으면 기여가 가장 나쁜 것부터 빼고, 모자라면 가장 좋은 것부터 더한다. 판단은 변형식 기준이다
- **변형식의 k=6 최적해:** N=50은 전수 탐색, N≥100은 교환(swap) 국소탐색 다중 재시작 중 최선
- **p와 w:** p∈{1,2}, w∈{4,5,6}. 각도는 빛원뿔 정확 계산으로 최적화한다
- **기존 50개 데이터 재수집:** 기준일을 맞추려고 150개 전체를 새로 받는다. 기준일이 바뀌어 N=50 원래 식 최적해가 이전(2026-10-22)과 다를 수 있다

## Standing rules

- End the run with the completion report (`references/reports.md`) once after the completion signal: show the verdict and its evidence, state which experiments/investigations ran and what verified them, and explain it for a reader with no context. The signal never replaces the report [self-report]
- Before the signal, semantically re-check the original question, every required condition, current verdict artifacts, and oracle evidence. Missing, failed, unsuitable, or stale evidence means the pass is not complete; after any edit during re-check, re-validate and re-check [self-report]
- Incomplete, blocked, waiting, and status-only turns run no completion signal; the signal declares the contracted pass itself complete, never an assessment, report, or attempt [self-report]
- Pass the re-check to `record.cjs done --review "<evidence summary>" --goal "<verdict>" --summary "<summary>"` (last tool call; no marker line in the message). On pass, S2 removes the pointer and `progress.json` [hook: S2]
- Numbers and claims carry provenance (verified / quoted / unverified)
- Plan units (investigation rounds, experiments) transition only via `record.cjs unit` (`.amber/progress.json`); announce any stop with open units via `amber:mark hold`. Parallel units use subagent worktrees; the main agent re-runs each oracle itself, records `unit verified --evidence`, and merges last (leftover worktree = not complete) [hook: E1, S2]

## Assumptions

- Yahoo 차트 API가 2026-10-22과 같은 방식(브라우저 UA, 200 응답)으로 계속 응답한다 (confidence: medium; disposition: unverified)
- 차수 3 이하 희소 그래프에서는 PPS 절단 오차가 조밀 그래프보다 훨씬 작다 (confidence: medium; disposition: unverified). C1이 직접 검증한다
- 시장 공통분을 뺀 잔차 상관의 희소화가 원래 식 상위 1% 해를 보존한다 (confidence: low; disposition: unverified). C2가 직접 검증한다
- |+⟩ 시작이라 Dicke 준비 회로가 사라져, 그 회로에서 생기던 오차(이득의 24%, 2026-10-23 측정)가 없어진다 (confidence: high; disposition: unverified)

`--goal` = "promote / hold / reject against criteria v1 + evidence summary". Hold (no conclusion) is a legitimate completion: the pass closes, the mission stays open.
