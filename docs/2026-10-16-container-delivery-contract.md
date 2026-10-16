# Contract - 컨테이너 배치 납품 패키지 (2026-10-16)

No load-bearing decision absent from this contract proceeds: stop and bring the question.

Pin: start commit 158cc7bc0fde8240e8ca135de7f8c9a1ecd6a641
Approval: norma 2026-10-16 - verification state at approval: 테스트 153개 통과(측정됨), 엔진 fixture 왕복 성공(측정됨), 이미지 빌드는 이 머신에 docker 부재로 미검증

## Completion conditions

All conditions must hold. Partial progress is not completion.

1. **manifest 보강** — `manifest.json`이 스펙 19쪽 목록 중 현재 빠진 네 항목을 담는다: `attempt_id`, 컨테이너/SDK digest, 자원 사용량(CPU 시간·최대 RSS), 대기시간. 자원 값은 표준 라이브러리만으로 측정하며 측정 불가한 플랫폼에서는 `null`을 기록하고 그 사유를 필드 옆에 남긴다.
2. **컨테이너 실행 모듈** — `Dockerfile`, 엔트리포인트, `.dockerignore`, 빌드 스크립트가 존재한다. 엔트리포인트는 `/in/request.json`을 읽어 `/out/result.json`과 `/out/manifest.json`을 쓴다. 엔트리포인트 로직을 docker 없이 로컬에서 직접 실행해 fixture 1건이 왕복하고 결과가 스키마 검증을 통과한다.
3. **입출력 명세** — `docs/`에 request/result의 JSON Schema 파일과 사람이 읽는 계약 문서가 있다. 생성된 스키마로 `fixtures/synthetic_12_6.json`과 실제 산출된 `result.json`이 모두 검증을 통과한다.
4. **운영 가이드** — `docs/`에 한도·취소·재시도·오류 처리 가이드가 있고, 문서의 각 기술이 `errors.py`·`policy.py`·`config.py`·예산 계수 규칙의 실제 동작과 일치한다. 코드에 없는 기능(예: 작업 취소 API)은 "없음"으로 명시하고 컨테이너 환경에서의 대체 수단을 적는다.
5. **회귀 없음** — 기존 153개 테스트와 이번 런에서 추가한 테스트가 모두 통과한다.
6. **독립 검토** — `docs/2026-10-16-container-delivery-review.md`가 신선한 서브에이전트(read-only)에 의해 작성되고, MUST-FIX가 열린 채로 남지 않으며, 모든 발견이 처리된다 — 적용 후 재검토, 사유를 들어 기각, 또는 운영자에게 가져감.

Verification (oracles): 조건 1·5는 `pytest`와 fixture 실행 후 manifest 키 확인; 조건 2는 엔트리포인트 로컬 실행 + `validate_request`/`Result` 스키마 통과; 조건 3은 생성된 스키마로 두 파일 검증; 조건 4는 문서 각 항목과 소스의 대조(자기보고); 조건 6은 검토 결과 파일의 `Verdict:` 줄과 각 `F<n>`의 처리 상태.

Not answered: HTTP API 경로(스펙 8쪽 4개 엔드포인트, 인증, 멱등성). 이미지 빌드 성공과 이미지 실행 검증. 엠버스 측 납품물. D03·D07·D08 등 미결 항목.

## Forbidden rows

- Write scope: 이번 런이 쓰는 경로 [machine: write-scope src/norma_qaoa/**,tests/**,docs/**,docker/**,scripts/**,Dockerfile,.dockerignore,.gitignore]
- HTTP 서버·웹 프레임워크 코드를 추가하지 않는다. D01이 컨테이너로 확정됐고 API 경로는 이 런의 범위가 아니다 [self-report]
- 새 런타임 의존성을 추가하지 않는다. `pyproject.toml`의 `[project] dependencies`는 이 런에서 늘어나지 않는다 [self-report]
- `pyproject.toml`의 `rustworkx<0.18` 핀을 제거하지 않는다. 핀 사유는 개발 머신의 Windows Smart App Control이며 그 환경은 그대로다. 해제는 컨테이너 이미지 안에서만 한다 [self-report]
- 기존 측정 결과 수치를 바꾸지 않는다 — `docs/proposals.md`의 측정 표, 발표 자료의 수치, 리포트 아티팩트의 값 [self-report]
- 패키지 설치 명령을 실행하지 않는다 [machine: bash-deny (^|[;&|]\s*|-m\s+)(pip|pip3|npm|yarn|pnpm|uv|poetry|conda)\s+(install|add)]

## Budget

작업 단위 6개. 한 단위의 오라클이 세 번 연속 실패하면 그 단위를 멈추고 운영자에게 가져간다. 전체가 막히면: INCOMPLETE - RESUME REQUIRED (resume: `node <amber>/scripts/record.cjs unit init docs/2026-10-16-container-delivery-plan.md` 후 미완 단위부터 이어서 진행).

## Settled decisions

- D01 연동 제공 방식을 **컨테이너 배치**로 확정한다. HTTP API 경로는 이 런에서 다루지 않는다 (norma 2026-10-16)
- 범위는 스펙 20쪽 노르마 납품물 체크리스트 ①②⑤⑥ 전부 (norma 2026-10-16)
- 컨테이너 IO 계약은 **단일 작업·디렉터리 마운트**: `/in/request.json` → `/out/result.json` + `/out/manifest.json`. 현 CLI `run --input <file> --out <dir>`와 동일 동작 (norma 2026-10-16)
- `rustworkx<0.18` 핀은 컨테이너 이미지에서만 해제한다. 개발 환경과 이미지의 의존성 차이는 manifest `versions`에 기록한다 (norma 2026-10-16)
- 이미지 빌드는 이 런에서 검증하지 않는다. 이 머신에 docker가 없다(`docker: command not found`). 작성까지 수행하고 빌드 성공은 미검증으로 보고한다 (norma 2026-10-16)
- 체크리스트 ①은 **JSON Schema + 계약 문서**로 낸다. OpenAPI는 쓰지 않는다 — 구현하지 않는 엔드포인트를 명세화하지 않기 위해 (norma 2026-10-16)
- 자원 사용량은 **표준 라이브러리만**으로 측정한다. POSIX는 `resource.getrusage`, 공통은 `time.process_time`. Windows에서 일부 `null` 허용 (norma 2026-10-16)
- 통합 점검 직전에 독립 검토 단계를 둔다 (norma 2026-10-16)

## Discretion

모델이 혼자 정해도 되는 항목과 그 기본값:

- 베이스 이미지: `python:3.12-slim-bookworm`을 digest로 핀. 개발 환경이 3.12.10이고 `requires-python >=3.11`과 맞는다. 변경 가능
- 엔트리포인트 언어: Python (`docker/entrypoint.py`). 기존 CLI를 그대로 호출하므로 셸 스크립트보다 오류 처리가 분명하다. 변경 가능
- 마운트 경로 기본값 `/in`·`/out`, 환경변수로 덮어쓰기 허용. 변경 가능
- JSON Schema 생성 방식: pydantic `model_json_schema()`. 변경 가능
- 문서 파일명과 절 구성. 변경 가능
- manifest 신규 필드의 정확한 키 이름과 중첩 위치(예: `resources` 객체로 묶을지). 변경 가능

## Standing rules

- End the run with the completion report in the shape of the plugin's `references/reports.md`, given once as the message after the completion signal: what was done and how, in full - show the actual deliverable, state what changed where and what verified it, and explain it for a reader with no context. The signal closes the report; it never replaces it [self-report]
- Before the completion signal, semantically re-check the original request, every required condition of this contract, the current artifacts, and the validation evidence. One condition without evidence, or with failed, unsuitable, or stale evidence, means the work is not complete. After a change made during that re-check, refresh the affected validation and re-check again [self-report]
- Incomplete, blocked, waiting, and status-only turns run no completion signal. The signal declares the contracted work unit itself complete, never that an assessment, report, or attempt finished [self-report]
- The re-check result goes into `record.cjs done --review "<evidence summary>" --goal "<goal-test result>" --summary "<summary>"` (the last tool call; no marker line in the message). S2 checks only the signal, the pointer, the current contract link, and leftover worktrees; semantic completion is the model's judgment. On a pass the hook removes the pointer and progress.json [hook: S2]
- Numbers and claims carry provenance (verified / quoted / unverified)
- Independent review (when the plan carries a review unit): the reviewer reads the pinned commit, this contract, the artifacts, and the evidence itself, read-only; the author's summary is not authority. A finding names the condition it violates and its evidence. The reviewer's PASS replaces no operator gate, and a MUST-FIX disputed on a required condition means not complete [self-report]
- Plan units transition only through `record.cjs unit` (`.amber/progress.json`); a stop while units are open is announced first with `amber:mark hold`. Parallel units run as subagents in worktrees; the main agent re-runs the same oracle itself whichever worker did the unit's work (a subagent in its worktree, another session, a person), records what it showed in `unit verified --evidence` (an empty `--evidence` is refused), and merges last. A leftover worktree means not complete [hook: E1, S2]

## Question handling

Default: on a discovery outside the contract, full stop plus a stop report in the shape of the plugin's `references/reports.md`.

## Carry-over (filled at completion)

- Left behind:
- Waiting (what waits on whose judgment):
- Next action:
