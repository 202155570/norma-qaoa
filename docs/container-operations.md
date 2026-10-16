# 운영 가이드 — 한도 · 취소 · 재시도 · 오류 처리

통합 스펙 20쪽 노르마 납품물 ⑥에 해당한다. 대상은 이 컨테이너를 배치로 돌리는 엠버스 측 운영자다.
입출력 형식은 `docs/io-contract.md`를 본다.

컨테이너 실행은 **작업 하나당 프로세스 하나**이고, 상태를 들고 있는 서버가 없다.
그래서 한도·취소·재시도의 의미가 API 연동과 다르다. 아래는 그 차이를 그대로 적은 것이다.

---

## 1. 한도

### 요청으로 지정하는 한도

| 필드 | 상한 | 넘기면 |
|---|---|---|
| `max_wall_seconds` | 300 | 요청 거부 (`OUT_OF_RANGE`) |
| `max_objective_evaluations` | 60 | 요청 거부 |
| `shots_per_circuit` | 1024 | 요청 거부 |
| `top_k` | 5 | 요청 거부 |
| `max_starts` | 정확히 1 | 1이 아니면 거부 |
| `asset_ids` 길이 N | 16 | 요청 거부 (`TOO_MANY_ASSETS`) |

**한도 초과는 거부이지 절삭이 아니다.** 엔진이 값을 알아서 깎아 실행하는 일은 없다.

### 평가 횟수가 소비되는 방식

`max_objective_evaluations`는 세 단계가 **합쳐서** 쓴다.

```
그리드 탐색(grid_size²) + COBYLA + 최종 샘플링 1회  ≤  max_objective_evaluations
```

기본 설정은 `grid_size = 7`이므로 그리드가 49회, 최종 샘플링이 1회를 예약하고,
남은 10회를 COBYLA가 쓴다 (60 − 49 − 1 = 10). manifest의 `budget`에 실제 배분이 기록된다.

> `max_objective_evaluations`를 그리드 + 1보다 작게 주면 실행 전에 `ConfigError`로 거부된다
> (종료 코드 11). 기본 설정에서 **실질 하한은 50**이다.
>
> 더 작은 예산으로 돌리려면 엔진 설정의 `grid_size`를 함께 낮춰야 하고, 그러려면 설정 파일을
> 컨테이너 안에 넣고 `NORMA_CONFIG`로 가리켜야 한다:
>
> ```bash
> echo '{"grid_size": 4}' > conf/engine.json     # 그리드 16 + 최종 1 → 하한 17
> docker run --rm \
>   -v "$PWD/job:/in:ro" -v "$PWD/out:/out" -v "$PWD/conf:/conf:ro" \
>   -e NORMA_CONFIG=/conf/engine.json \
>   norma-qaoa:0.1.0
> ```

### 시간 한도가 작동하는 방식

**마감은 회로 실행 **전에**만 확인하고, 이미 돌기 시작한 회로는 중단하지 않는다.**
따라서 실제 경과 시간이 `max_wall_seconds`를 조금 넘을 수 있다. 회로 한 개의 실행 시간이
초과분의 상한이다. 컨테이너 바깥에서 더 엄격한 벽시계가 필요하면 `docker run --stop-timeout`과
오케스트레이터 쪽 타임아웃을 함께 건다.

시간 한도로 끝나면 결과는 **버려지지 않는다**. `status = PARTIAL`, `stop_reason = TIME_LIMIT`으로
그때까지 확보한 후보가 반환된다. 후보가 `top_k`개 다 있어도 PARTIAL이다 (스펙 5쪽).

### 월·일 사용량 한도

엔진에는 없다. 컨테이너는 자기가 몇 번째 실행인지 모른다.
스펙 17쪽의 월/일 한도와 `BUDGET_LIMIT` 처리는 **엠버스 측 스케줄러가 건다.**
노르마가 제공하는 것은 작업 1건당 자원 기록(`manifest.resources`, `manifest.elapsed_ms`)이며,
이를 합산해 한도를 집계하는 것은 호출자의 몫이다.

---

## 2. 취소

**작업 취소 API는 없다.** 스펙 8쪽의 `POST .../cancel`은 D01이 컨테이너로 정해지면서 범위 밖이 됐다.
컨테이너에서의 대체 수단은 프로세스 종료다.

```bash
docker stop <container>     # SIGTERM 후 유예시간이 지나면 SIGKILL
docker kill <container>     # 즉시 SIGKILL
```

**알아 두어야 할 동작 두 가지.**

1. 엔트리포인트는 작업이 **끝난 뒤에** `result.json`과 `manifest.json`을 쓴다.
   중간에 죽이면 이번 실행의 산출물은 **하나도 생기지 않는다.** 부분 결과는 남지 않는다.
2. 엔트리포인트는 시작할 때 출력 디렉터리의 `result.json`·`manifest.json`·`error.json`을 **먼저 지운다.**
   따라서 실행이 끝났을 때 그 디렉터리에 있는 것은 이번 실행의 것이다.
   **다만 중간에 죽이면 지우기까지만 끝난 상태로 남을 수 있다** — 즉 디렉터리가 빈 채로 남는다.
   이전 결과를 보존해야 한다면 실행마다 **출력 디렉터리를 따로 주어야 한다.**

그래서 취소에는 두 가지 선택지가 있다.

| 원하는 것 | 방법 |
|---|---|
| 지금까지 찾은 후보라도 받고 싶다 | 죽이지 말고 **`max_wall_seconds`를 짧게 주어 재실행**한다. 시간 한도로 끝나면 PARTIAL로 후보가 나온다 |
| 자원을 즉시 회수해야 한다 | `docker stop`. 출력은 없고, 소비한 자원은 기록되지 않는다 |

취소된 실행은 manifest를 남기지 않으므로, **실사용량 보존이 필요하면 호출자가
컨테이너 시작·종료 시각과 종료 사유를 자기 쪽에 기록해야 한다.**

---

## 3. 재시도

스펙 17쪽: *"한도 내 자동 재실행은 최대 1회 제안입니다. 재실행은 새 계산 시도 ID로 기록하고
예산에서 차감합니다. 단순 네트워크 재요청은 동일 작업으로 본다."*

컨테이너에는 네트워크 왕복이 없으므로 "단순 네트워크 재요청"은 발생하지 않는다.
재실행은 곧 컨테이너를 다시 띄우는 것이고, 그때마다 **새 시도**다.

### 시도 식별자

| 식별자 | 재실행 시 |
|---|---|
| `request_id` | **그대로 유지**. 호출자가 넣는 값 |
| `job_id` | 매번 새로 생성 (UUID) |
| `attempt_id` | 매번 새로 생성. `--attempt-id` 또는 `NORMA_ATTEMPT_ID`로 지정 가능 |

재시도 집계가 필요하면 `attempt_id`를 호출자가 직접 매겨 넣는 편이 낫다.

```bash
docker run --rm -e NORMA_ATTEMPT_ID="req-001-attempt-2" ...
```

### 재시도해도 되는 경우와 아닌 경우

| 종료 코드 | 재시도 | 이유 |
|---|---|---|
| 0 (SUCCEEDED/PARTIAL) | 불필요 | 결과가 나왔다. PARTIAL을 개선하려면 한도를 올려 **새 요청**으로 보낸다 |
| 1 (FAILED) | **조건부** | `stop_reason`을 본다. 아래 표 참조 |
| 10 (요청 거부) | **금지** | 요청을 고치기 전에는 몇 번을 보내도 같은 결과다 |
| 11 (설정·정책 거부) | **금지** | 설정이나 정책을 바꿔야 한다 |
| 12 (입출력 문제) | 가능 | 마운트·권한을 고친 뒤 |
| 13 (예상치 못한 실패) | 1회 | `error.json`의 traceback을 보관하고 노르마에 전달한다 |

`status = FAILED`일 때:

| `stop_reason` | 재시도 | 설명 |
|---|---|---|
| `NO_FEASIBLE_SAMPLE` | **조건부** | 표본에서 가해 조합이 안 나왔다. `shots_per_circuit`이나 `seed`를 바꿔 한 번 더 해볼 수 있다. 단 `proven_infeasible = true`면 제약 자체가 불가능하다는 뜻이므로 **재시도 금지**, 제약을 고쳐야 한다 |
| `TIME_LIMIT` | **조건부** | 시간 한도 안에 가해 후보를 하나도 못 찾았다(후보가 1개 이상이면 PARTIAL이다). `max_wall_seconds`를 올려 **새 요청**으로 보낸다. 같은 한도로 재시도하면 같은 결과다 |
| `SIMULATOR_ERROR` | 1회 | 회로 준비·실행 실패. `manifest.error`에 사유가 있다. 같은 사유로 두 번 실패하면 노르마에 전달한다 |

**자동 재시도는 최대 1회로 제한하기를 권한다** (스펙 17쪽). 같은 실패가 반복되면 그건 재시도로
풀 문제가 아니다.

---

## 4. 오류 처리

### 종료 코드

| 코드 | 뜻 | 출력 |
|---|---|---|
| 0 | 결과 생성. `status`는 `SUCCEEDED` 또는 `PARTIAL` | `result.json`, `manifest.json` |
| 1 | 결과 생성. `status = FAILED` (쓸 수 있는 후보 없음) | `result.json`, `manifest.json` |
| 10 | 요청 거부 — 스키마·차원·버전·제약 충돌 | `error.json` |
| 11 | 설정 또는 정책이 거부 | `error.json` |
| 12 | 입출력 문제 — 요청 없음/읽기 실패, 출력 디렉터리 사용 불가 | `error.json`. **단 출력 디렉터리 자체가 막혔으면 아무것도 없고 stderr만 남는다** |
| 13 | 예상치 못한 실패 | `error.json` (traceback 포함) |

**0과 1에서만 결과 파일이 생긴다.** 나머지는 `error.json`만 본다.
`error.json`은 요청 거부뿐 아니라 **12·13에서도 쓰인다** — 즉 "`error.json`이 있다"는 것은
"요청이 잘못됐다"가 아니라 "결과가 없다"는 뜻이다. 원인은 `error` 필드로 구분한다:
`INVALID_REQUEST` / `REFUSED` / `REQUEST_NOT_FOUND` / `UNREADABLE_REQUEST` / `BAD_ACCEPTED_AT` / `UNEXPECTED`.

`BAD_ACCEPTED_AT`은 `NORMA_ACCEPTED_AT`에 epoch 초가 아닌 값(예: ISO-8601 문자열)을 넘겼을 때다.
같은 표의 `NORMA_IMAGE_BUILT_UTC`는 ISO-8601이므로 헷갈리기 쉽다.

### 스펙 8쪽 HTTP 코드와의 대응

나중에 API로 전환할 때를 위한 대응표다. 지금 컨테이너에는 HTTP가 없다.

| 종료 코드 | 대응 HTTP | 스펙 8쪽 처리 원칙 |
|---|---|---|
| 10 | 400 / 422 | 형식·차원·버전·제약 충돌을 수정한 뒤 새 요청. **자동 반복 금지** |
| 11 | 403 / 422 | 정책·설정 문제. 승인 또는 설정 변경 필요 |
| 12 | — | 호출자 인프라 문제 |
| 13 | 500 | 노르마에 전달 |
| — | 409 | 멱등 키 충돌. 컨테이너에는 멱등 키가 없다 |
| — | 429 / `BUDGET_LIMIT` | 호출률·월 한도. 엠버스 스케줄러가 건다 |

### `error.json`의 모양

```json
{
  "error": "INVALID_REQUEST",
  "message": "[SCHEMA] data: Field required; [OUT_OF_RANGE] execution.top_k: must be 1..5",
  "issues": [
    { "code": "SCHEMA", "field": "data", "message": "Field required" },
    { "code": "OUT_OF_RANGE", "field": "execution.top_k", "message": "must be 1..5" }
  ],
  "engine": "norma-qaoa",
  "recorded_utc": "2026-10-16T05:12:33Z"
}
```

**위반을 한 번에 모아서 돌려준다.** 첫 오류에서 멈추지 않으므로 한 번의 왕복으로 전부 고칠 수 있다.
코드 목록은 `docs/io-contract.md` 5절에 있다.

### 경고

거부가 아닌 주의 사항은 `manifest.warnings[]`에 담긴다. 결과는 정상 반환된다.

| 경고 | 뜻 |
|---|---|
| 벌점 점검 실패 | 벌점 값이 가해/비가해 분리를 보장하기에 부족하다. 결과는 나오지만 신뢰도가 낮다 |
| `max_wall_seconds reached; ...` | 시간 한도로 종료. 후보는 그때까지 얻은 표본에서 나왔다 |
| `final sampling not executed; ...` | 최종 샘플링을 못 돌려, 비용이 가장 낮았던 평가의 표본을 후보로 썼다 |

**경고가 있는 결과를 고객에게 그대로 노출하지 않기를 권한다.** 스펙 12쪽대로 엠버스가 재검산한 뒤
노출 승인을 거치는 것을 전제로 한다.

---

## 5. 점검 절차

> ⚠️ **이 이미지는 납품 시점까지 한 번도 빌드된 적이 없다.** 작성 환경에 Docker가 없었다.
> 아래 1번(자체 점검)이 **처음으로 이미지를 실제로 돌려 보는 지점**이며, 그 전에 `docker build`가
> 실패할 가능성이 남아 있다. 빌드 오류가 나면 노르마에 전달한다.

이미지를 처음 받았을 때와 업데이트할 때마다 아래를 돌린다.

```bash
# 1. 이미지 자체 점검 — 시뮬레이터 1회 실행 + 스키마 검증
docker run --rm norma-qaoa:0.1.0 --selftest

# 2. 알려진 입력으로 왕복
mkdir -p job out && cp fixtures/synthetic_12_6.json job/request.json
docker run --rm -v "$PWD/job:/in:ro" -v "$PWD/out:/out" \
  -e NORMA_IMAGE_DIGEST="sha256:..." norma-qaoa:0.1.0
echo "exit=$?"

# 3. 재검산 — 엠버스 측 검산기로 objective_penalized 대조
```

`--selftest`가 실패하면 그 이미지는 쓰지 않는다.

---

## 6. 이 문서가 다루지 않는 것

- **인증·전송 보안**: 컨테이너는 네트워크를 쓰지 않는다. 이미지 배포 경로의 보안은 양사 합의 사항(D06)
- **월·일 사용량 한도와 과금**: 미결(D07)
- **지원 응답시간·장애 책임**: 미결(D08)
- **실행 환경(CPU/GPU) 사양**: 미결(D03). 현재 시뮬레이터는 CPU만 쓴다
