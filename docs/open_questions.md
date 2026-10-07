# 미결 사항 (Open Questions)

기준 문서: `docs/Faiseeker_NORMA_Hybrid_Portfolio_Integration_Spec_KR_v1.0.pdf` (v1.0 공동 검토안)
작성: 2026-10-07, NORMA 측 엔진 프로토타입 `norma-qaoa 0.1.0`

이 문서는 두 가지를 구분해 기록한다.
- **확정**: NORMA 측 담당자가 확정한 사항이다.
- **잠정**: 프로토타입 구현을 위해 임시로 정한 값이다. 사양에 정의가 없거나 사양과 지시가 다른 항목이며, 엠버스와 합의해야 한다. 잠정 값은 모두 config나 상수로 바꿀 수 있게 구현했다.

## A. 사양과 작업 지시가 달랐던 항목

| ID | 내용 | 처리 | 상태 |
|---|---|---|---|
| A1 | 시간 한도(TIME_LIMIT)로 중단됐지만 top_k개를 확보한 경우의 status. 사양 p.5는 PARTIAL을 "요청 개수 미달 또는 계산 한도로 종료"로 정의한다. | 사양을 따라 `PARTIAL / TIME_LIMIT`로 둔다. 후보가 0개면 `FAILED / TIME_LIMIT`이다. `NO_FEASIBLE_SAMPLE`은 정상 종료했는데 후보가 0개인 경우에만 쓴다. | 확정 (2026-10-07) |
| A2 | 최종 샘플링 전에 시간 한도에 걸린 경우 후보를 어디서 뽑는가 | 회로를 추가로 실행하지 않는다. 지금까지 평가 중 평균 F가 가장 낮았던 평가의 실제 표본에서 뽑고, origin은 `simulator_sample`이다. manifest의 `counts_source`에 `{"phase": "best_evaluation", "evaluation_index": k}` 형식으로 기록한다. | 확정 (2026-10-07) |
| A3 | 리포트의 "924개 조합 중 몇 위" | synthetic_12_6에는 must_include가 1개 있어 feasible 조합은 C(11,5) = 462개다. 순위는 feasible 462개 중 F 순위로 낸다. | 확정 (2026-10-07) |
| A4 | PSD 처리. 부록 A는 "PSD 검사·수정은 이력 보존"이라고 해서 보정을 허용한다. | NORMA 엔진은 보정하지 않고 `NOT_PSD`로 거부한다. 보정이 필요하면 엠버스 전처리 단계에서 하고, 그 이력을 snapshot에 남기는 방식을 제안한다. | 잠정 (합의 필요) |

## B. 사양에 정의가 없어 구현 시 정한 값

| ID | 내용 | 현재 구현 | 관련 결정 |
|---|---|---|---|
| B1 | 최종 샘플링을 `max_objective_evaluations`(60회)에 포함하는가 | config `count_final_in_budget`로 선택한다(기본값 true). 포함하면 격자 49 + COBYLA 최대 10 + 최종 1 = 60이다. 미포함이면 격자 49 + COBYLA 최대 11을 평가로 세고, 최종 샘플링은 별도 회로 1개로 센다. 어느 방식이었는지 manifest의 `budget.counting_rule`에 기록한다. | D03 |
| B2 | 정상 종료 시 `stop_reason` 값 | SUCCEEDED는 `COMPLETED`, PARTIAL은 `TOP_K_NOT_REACHED`다. 백엔드에서 예외가 나면 `FAILED / SIMULATOR_ERROR`이고, 다른 백엔드로 자동 전환하지 않는다. | 오류 코드 목록 |
| B3 | SIMULATOR_ERROR 시 이미 얻은 표본을 쓰는가 | 쓰지 않는다. 후보 0개로 FAILED 처리한다. TIME_LIMIT과 달리 실행 자체가 실패한 경우라서다. | 확인 필요 |
| B4 | 검증에 추가한 실행 한도 | 사양 p.9·p.17의 제안값을 상한으로 검사한다: `1 ≤ top_k ≤ 5`, `shots_per_circuit ≤ 1024`, `max_objective_evaluations ≤ 60`, `max_starts = 1`, `0 < max_wall_seconds ≤ 300`. `mode`는 `quantum_circuit_simulator`, `algorithm`은 `QAOA`, `schema_version`은 `"1.0"`만 받는다. | D03 (제안값이 확정되면 상수 수정) |
| B5 | result.execution에 추가한 필드 | `circuits_total`, `qubits`, `depth`. 사양 10 예시에는 없는 필드를 더한 것이다. | 스키마 버전 정책 |
| B6 | classical repair 알고리즘(기본 OFF) | 1. include를 1로, exclude를 0으로 고정한다. 2. 선택 개수가 K와 같아질 때까지 F 증가가 가장 작은 자산부터 하나씩 추가하거나 제거한다(greedy). 원래 비트열·count·변경 내역을 `repair.sources`에 보존한다. `sample_count`는 null이다. repair 후보는 원표본 후보로 채우지 못한 빈 자리만 채우고, 원표본 후보를 밀어내지 않는다. 원표본과 같은 조합이면 원표본 쪽을 남긴다. | 알고리즘·top_k 포함 여부 승인 |
| B7 | COBYLA 설정 | `rhobeg = 0.25`, bounds 없음. COBYLA가 시작점을 다시 평가하는 호출도 회로를 실제로 실행하므로 1회로 센다. 최종 파라미터는 COBYLA의 결과값이 아니라 전체 평가 중 비용이 가장 낮았던 점이다. optimizer seed는 기록만 한다(COBYLA는 결정적). | D03 |
| B8 | depth > 1(플래그를 켰을 때)의 격자 전략 | 격자 단계에서는 모든 층에 같은 (γ, β)를 쓰고, COBYLA는 2p차원에서 탐색한다. | p ≥ 2 승인 시 |
| B9 | 시간 한도 측정 범위 | `run_job` 진입 시점(검증 포함)부터 후보 추출까지다. 마감은 회로를 하나 실행하기 직전마다 확인하고, 실행 중인 회로는 끊지 않는다. 따라서 최대 회로 1개 실행 시간만큼 넘길 수 있다. | D03 |
| B10 | 대칭 허용오차 | `|M − Mᵀ| ≤ 1e-12 × max(1, max|M|)`. overlap 대각은 정확히 0이어야 한다. PSD 기준은 최소 고유값 ≥ −1e-10이다. | 부록 A |
| B11 | 요청의 추가 필드 | `data`와 최상위에는 운영 메타데이터(profile_id, 관측창, source_versions 등)를 허용한다. `constraints`, `model`, `execution`에서는 모르는 필드를 거부한다(오타가 조용히 무시되는 일을 막기 위해). `overlap`, `must_include`, `must_exclude`, `seed`는 필수 필드다(기본값으로 채우지 않음). | 부록 A |
| B12 | input_hash 대상 | 요청 원문 바이트가 아니라 파싱한 JSON 객체의 canonical 직렬화다. 공백이나 키 순서가 달라도 해시가 같다. | 해시 규칙 합의 |
| B13 | job_id | uuid4다. 같은 입력을 다시 실행하면 job_id가 달라진다. Idempotency-Key 처리는 API 범위다. | D01 |
| B14 | 리포트 seed 규칙 | 입력 `execution.seed` + 0, 1, 2, 3, 4. random 기준의 seed는 각 master seed에서 파생한다. | — |

## C. 모델·운영 관련 (측정 결과에서 나온 질문)

| ID | 내용 |
|---|---|
| C1 | **벌점 계수의 크기.** synthetic_12_6에서 Lk = Lf = 4.0이다. feasible 462개의 F 폭은 0.291인데, 벌점 단위는 4.0이다. 벌점 충분성 검사는 통과했다(infeasible 최저 F와 feasible 최저 F의 차이 4.007). 그러나 Hamiltonian을 max\|coef\|로 정규화하면 위험·중복·적합도 항의 상대 크기가 작아진다. 벌점 값을 결정하는 기준(D04)이 필요하다. |
| C2 | H2-1LE를 추가 백엔드로 두는 것이 사양 p.3의 "실행 환경 변경은 양사 승인" 대상인가. 현재 기본값은 Aer이고, H2-1LE는 내부 검증용 옵션이다. |
| C3 | Nexus 에뮬레이터나 Quantinuum 하드웨어로 확장할 때 정할 것(→ D03, D07): 300초 한도와 큐 대기를 어떻게 나눌지, HQC 예산·월 한도, 외부 반출 사전 승인(사양 16). `docs/quantinuum_integration.md` 참고. |
| C4 | `hardware_qpu_used`는 백엔드 kind에서 계산한다(`hardware_qpu`일 때만 true). 정책상 지금은 항상 false다. |
