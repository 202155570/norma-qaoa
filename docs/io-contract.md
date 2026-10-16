# 입출력 계약 — norma-qaoa 컨테이너 배치

통합 스펙(`Faiseeker_NORMA_Hybrid_Portfolio_Integration_Spec_KR_v1.0.pdf`) 20쪽
노르마 납품물 ① "입출력 JSON 명세"에 해당한다. D01 연동 제공 방식은 **컨테이너 배치**로 확정됐다.

| | |
|---|---|
| 엔진 | `norma-qaoa` 0.1.0 |
| `schema_version` | `1.0` (유일하게 지원) |
| 실행 모드 | `quantum_circuit_simulator` 전용. 실제 QPU는 거부된다 |
| 기계 판독 스키마 | `docs/schema/request.schema.json`, `docs/schema/result.schema.json` |

스키마 파일은 엔진이 실제로 검증에 쓰는 pydantic 모델에서 생성된다. `scripts/check_schema.py`가
모델에서 재생성해 커밋본과 바이트 단위로 대조하므로, 명세가 구현과 어긋난 채로 남을 수 없다.

> **OpenAPI를 포함하지 않는 이유.** 스펙 8쪽의 4개 HTTP 엔드포인트는 구현되지 않았다.
> 컨테이너 납품에는 서버가 없으므로, 존재하지 않는 엔드포인트의 OpenAPI 문서를 내면 있는 것처럼 읽힌다.
> 입출력 JSON 자체는 스펙 8쪽 계약과 동일하므로, 나중에 API로 전환하면 이 스키마를 그대로 감싸면 된다.

---

## 1. 실행 방법

작업 하나당 컨테이너 실행 하나다.

```bash
mkdir -p job out
cp fixtures/synthetic_12_6.json job/request.json

docker run --rm \
  -v "$PWD/job:/in:ro" -v "$PWD/out:/out" \
  -e NORMA_IMAGE_REF="norma-qaoa:0.1.0" \
  -e NORMA_IMAGE_DIGEST="sha256:..." \
  --user "$(id -u):$(id -g)" \
  norma-qaoa:0.1.0
```

| 경로 | 내용 |
|---|---|
| `/in/request.json` | 요청 문서 (읽기 전용 마운트로 충분) |
| `/out/result.json` | 결과 문서 |
| `/out/manifest.json` | 실행 manifest |
| `/out/error.json` | 요청이 거부됐을 때만 생성. 결과가 나오면 삭제된다 |

마운트 경로는 `NORMA_IN_DIR` / `NORMA_OUT_DIR`로 바꿀 수 있다.
이미지 자체 점검은 `docker run --rm norma-qaoa:0.1.0 --selftest`.

**`NORMA_IMAGE_DIGEST`를 넘겨야 하는 이유**: 프로세스는 자기 이미지의 digest를 읽을 수 없다.
넘기지 않으면 manifest의 `container.image_digest`가 `null`이 되고, 스펙 19쪽이 요구하는
"어떤 이미지가 이 결과를 냈는가"를 증명할 수 없다. `scripts/build_image.sh`가 빌드 후 digest를 출력한다.

---

## 2. 요청 문서

필드 구성은 스펙 11쪽 예시와 같다. 여기서는 **의미와 단위**를 적는다.

### `data`

| 필드 | 형 | 의미 |
|---|---|---|
| `snapshot_id` | string | 입력 데이터 스냅샷 식별자. manifest에 그대로 기록된다 |
| `as_of_utc` | string | 스냅샷 기준 시각 |
| `base_currency` | string | 기준 통화 |
| `source_kind` | string \| null | 데이터 출처 구분 |
| `asset_ids` | string[N] | 자산 식별자. **이 순서가 모든 벡터·행렬의 축**이며 결과의 `asset_order`로 되돌아온다 |
| `utility` | float[N] | 기대효용 지표. **0 ≤ u ≤ 1** |
| `covariance_annual` | float[N][N] | 연율 공분산. 대칭이고 양반정부호여야 한다 |
| `overlap` | float[N][N] \| **null** | 보유 중복도. 0 ≤ O ≤ 1, 대각은 0 |

> **`overlap`이 없을 때는 반드시 `null`을 보낸다** (스펙 11쪽). 0 행렬로 미제공을 숨기면 안 된다.
> `null`로 보낼 때는 `model.weights.overlap`도 0이어야 하며, 아니면 `OVERLAP_WEIGHT_WITHOUT_DATA`로 거부된다.

### `constraints`

| 필드 | 의미 |
|---|---|
| `select_k` | 선택 개수 K. `0 < K ≤ N` |
| `must_include` | 반드시 담아야 하는 자산. `|must_include| ≤ K` |
| `must_exclude` | 담으면 안 되는 자산. `N − |must_exclude| ≥ K` |

### `model`

점수는 **낮을수록 좋다**.

```
G(x) = a·risk(x) + b·overlap(x) − d·utility(x)          (a,b,d = weights.risk, .overlap, .utility)
P(x) = Lk·(Σx − K)² + Lf·Σ_include(1−x_i) + Lf·Σ_exclude x_i
F(x) = G(x) + P(x)                                       (엔진이 최소화하는 값)

risk(x)    = xᵀ C x / K²
overlap(x) = 2·Σ_{i<j} O_ij x_i x_j / (K(K−1))           (K=1이면 0)
utility(x) = Σ u_i x_i / K
```

`weights`와 `penalties`의 모든 값은 유한하고 0 이상이어야 한다. `risk_scale`은 유한하고 0보다 커야 한다.

> **벌점 크기에 대한 측정 소견.** 현재 `fixtures/synthetic_12_6.json`은 `cardinality = fixed = 4.0`을 쓴다.
> 가해 조합 462개 전부를 비가해보다 위에 두는 데 필요한 최소값은 **0.2839**로, 지금 설정은 그 **14배**다.
> 벌점이 과하면 모든 자산 쌍의 Ising 결합계수가 0.9914~1.0000로 뭉쳐 알고리즘의 탐색 성능이 떨어진다.
> 운영 값은 단계 A에서 함께 정하기를 제안한다. (측정: `docs/proposals.md`)

### `execution`

| 필드 | 허용 범위 | 비고 |
|---|---|---|
| `mode` | `"quantum_circuit_simulator"` | 다른 값은 거부 |
| `algorithm` | `"QAOA"` | 다른 값은 거부 |
| `depth` | ≥ 1 | **2 이상은 엔진 설정 `allow_depth_gt_1`이 켜져야 한다** (기본 꺼짐) |
| `max_wall_seconds` | 0 < s ≤ **300** | |
| `max_objective_evaluations` | 1 ~ **60** | 그리드 + COBYLA + 최종 샘플링 합계 |
| `max_starts` | **정확히 1** | 1이 아니면 거부 |
| `shots_per_circuit` | 1 ~ **1024** | |
| `seed` | ≥ 0 | |
| `allow_qpu` | **`false`만 허용** | `true`는 거부 |
| `top_k` | 1 ~ **5** | 반환할 후보 수 |

`N`(자산 수)의 상한은 **16**이다.

---

## 3. 결과 문서

최상위 필드는 스펙 12쪽 예시와 **정확히 일치**한다 (누락·추가 없음, `scripts/check_schema.py`가 검사).

| 필드 | 의미 |
|---|---|
| `job_id` | 이 실행의 식별자 (UUID) |
| `status` | `SUCCEEDED` / `PARTIAL` / `FAILED` |
| `stop_reason` | 종료 사유 (아래 표) |
| `asset_order` | 입력 `asset_ids`와 동일. 모든 `bit_vector`의 축 |
| `candidates[]` | 유효 후보. 최대 `top_k`개 |
| `execution` | 실제 실행 요약 |
| `artifact_manifest_id` | 짝이 되는 manifest의 id |
| `proven_infeasible` | 전수 확인으로 가해 조합이 **하나도 없음**이 증명된 경우에만 `true` |

### status와 stop_reason

| status | stop_reason | 뜻 |
|---|---|---|
| `SUCCEEDED` | `COMPLETED` | 요청한 개수(`top_k`)의 유효 후보 확보. **전역 최적을 뜻하지 않는다** |
| `PARTIAL` | `TOP_K_NOT_REACHED` | 유효 후보는 있으나 `top_k` 미달 |
| `PARTIAL` | `TIME_LIMIT` | 시간 한도로 종료. 후보가 `top_k`개 있어도 PARTIAL이다 (스펙 5쪽) |
| `FAILED` | `NO_FEASIBLE_SAMPLE` | 유효 후보 0개 |
| `FAILED` | `SIMULATOR_ERROR` | 회로 준비·실행 실패. `manifest.error`에 사유 |

### candidate

| 필드 | 의미 |
|---|---|
| `bit_vector` | `asset_order` 순서의 0/1 |
| `origin` | `simulator_sample` / `classical_repair` / `classical_baseline` / `mock` |
| `objective_base` | G(x) |
| `objective_penalized` | F(x) |
| `components` | `risk`, `overlap`, `utility` 각각의 값 |
| `sample_count` | 그 비트열이 회로 표본에 나타난 횟수. **예측치가 아니다** |

> `origin`이 `classical_baseline` 또는 `mock`인 후보는 **양자 실행 결과로 표시하면 안 된다** (스펙 7쪽).

---

## 4. manifest

스펙 19쪽 "작업별 실행 manifest" 목록 대비 현황이다.

| 스펙 요구 | manifest 키 | 상태 |
|---|---|---|
| request_id / job_id / attempt_id | `request_id`, `job_id`, `attempt_id` | 있음 |
| snapshot_id / model_version | `snapshot_id`, `model_version` | 있음 |
| input_hash | `input_hash` | 있음 |
| QUBO·회로 해시 | `qubo_hash`, `circuit_hash`, `backend_circuit_hash` | 있음 |
| SDK·컨테이너 digest | `container.image_digest`, `container.image_ref` | 있음 (실행 시 주입) |
| backend / 실제 device | `backend` | 있음 |
| 모든 시드 | `seeds` (master·simulator·transpiler·optimizer·random_baseline) | 있음 |
| qubits / depth | `qubits`, `depth` | 있음 |
| evaluations / circuits / shots | `evaluations`, `circuits`, `shots` | 있음 |
| 실행·대기시간 | `elapsed_ms`, `queue_wait_ms` | 있음 |
| 자원 사용량 | `resources` | 있음 (아래 단서) |
| stop_reason / 후보 출처 / 후처리 | `stop_reason`, `candidate_origins`, `postprocessing` | 있음 |
| 승인·발행 버전 | — | **없음.** 승인은 엠버스 측 절차이므로 엠버스가 기록한다 |

`resources`의 한계를 분명히 해 둔다.

- `cpu_seconds` — 이 작업의 CPU 시간 (`time.process_time` 차분). 모든 플랫폼에서 유효
- `max_rss_bytes` — **프로세스 전체의 최고점**이지 이 작업만의 값이 아니다. OS가 구간값을 주지 않는다.
  POSIX 전용이라 Windows에서는 `null`
- `gpu` — **항상 `null`**. 시뮬레이터는 CPU로 돌며 표준 라이브러리로는 GPU를 관측할 수 없다
- `queue_wait_ms` — 요청 수락 시각부터 계산 시작까지. 호출자가 알려주지 않으면 `null`이며,
  **추측해서 0을 넣지 않는다**

### 재현성의 의미

같은 시드와 같은 입력이 모든 환경에서 같은 표본을 보장하지 **않는다** (스펙 19쪽).
manifest는 `versions`에 python·qiskit·qiskit-aer·numpy·scipy·pydantic·rustworkx 버전을 기록한다.

> 컨테이너 이미지는 `rustworkx` 버전이 개발 환경과 다르다. 개발 환경의 `rustworkx<0.18` 상한은
> 개발 머신의 Windows Smart App Control이 0.18.1의 DLL을 차단하기 때문이며 리눅스에는 해당하지 않아
> 이미지에서는 해제했다. 실제 설치된 버전은 매 manifest의 `versions.rustworkx`에 남는다.

---

## 5. 스키마가 보는 것과 엔진이 보는 것

JSON Schema는 **모양**만 규정한다. 아래는 스키마를 통과해도 엔진이 거부하는 항목이며,
전부 `error.json`의 `issues[]`에 코드와 함께 담긴다.

| 코드 | 조건 |
|---|---|
| `UNSUPPORTED_SCHEMA_VERSION` | `schema_version`이 `1.0`이 아님 |
| `TOO_MANY_ASSETS` | N > 16 |
| `DUPLICATE_ID` / `EMPTY_ID` | `asset_ids` 중복 또는 빈 문자열 |
| `DIMENSION_MISMATCH` | 벡터·행렬 크기가 N과 다름 |
| `NON_FINITE` | NaN 또는 무한대 |
| `OUT_OF_RANGE` | `utility`가 [0,1] 밖, `overlap`이 [0,1] 밖, 가중치·벌점이 음수, 실행 한도 초과 |
| `NOT_SYMMETRIC` | 공분산 또는 중복도 행렬이 비대칭 |
| `NOT_PSD` | 공분산의 최소 고유값이 임계값 미만. **자동 보정하지 않는다** |
| `NONZERO_DIAGONAL` | `overlap` 대각이 0이 아님 |
| `OVERLAP_WEIGHT_WITHOUT_DATA` | `overlap`이 null인데 가중치가 0이 아님 |
| `INVALID_K` | K가 (0, N] 밖 |
| `UNKNOWN_ID` | `must_include`/`must_exclude`에 모르는 자산 |
| `INCLUDE_EXCLUDE_CONFLICT` | 같은 자산이 양쪽에 |
| `INFEASIBLE_CONSTRAINTS` | `|include| > K` 또는 `N − |exclude| < K` |
| `QPU_NOT_ALLOWED` | `allow_qpu=true` |
| `UNSUPPORTED_MODE` / `UNSUPPORTED_ALGORITHM` | 시뮬레이터·QAOA 외 |
| `DEPTH_NOT_APPROVED` | `depth > 1`인데 엔진 설정이 허용하지 않음 |

**모든 위반을 한 번에 모아서 반환한다.** 첫 오류에서 멈추지 않으므로 한 번의 왕복으로 전부 고칠 수 있다.

---

## 6. 아직 없는 것

| 스펙 | 상태 |
|---|---|
| 8쪽 HTTP 엔드포인트 4종, 인증, `Idempotency-Key` | 없음. D01이 컨테이너로 정해져 범위 밖 |
| 작업 취소 | 비동기 작업 개념이 없다. 컨테이너에서의 대체 수단은 `docs/container-operations.md` |
| 승인·발행 버전 기록 | 엠버스 측 절차 |
| GPU 자원 측정 | 없음. 시뮬레이터가 CPU로 돈다 |

운영상의 한도·취소·재시도·오류 처리는 `docs/container-operations.md`에 있다.
