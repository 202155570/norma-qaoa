# Plan - 컨테이너 배치 납품 패키지 (2026-10-16)

계약: `docs/2026-10-16-container-delivery-contract.md`. 이 문서는 가이드이고 권한은 계약에 있다.

## 가는 길

엔진은 이미 스펙의 JSON 계약을 정확히 만족한다 (실측: 최상위 필드 누락 0, candidate 필드 누락 0). 빠진 것은 **포장과 문서**다. 그래서 U1에서 manifest를 스펙 19쪽 수준으로 맞추고, 그 위에 U2가 컨테이너를, U3·U4가 문서를 올린다.

U1이 먼저인 이유: 엔트리포인트가 컨테이너 digest를 manifest에 주입해야 하므로 필드가 먼저 있어야 한다. U3·U4는 U1·U2가 만든 실제 동작을 기술하므로 뒤에 온다.

**병렬 가능**: U3와 U4는 쓰기 범위가 겹치지 않게 파일을 나눠 두었으나(U3는 스키마와 계약 문서, U4는 운영 가이드), 둘 다 `docs/`를 쓰므로 순차 실행한다. 나머지는 모두 선후 의존이 있다.

## Work units

- [ ] U1 manifest 보강 — attempt_id·digest·자원사용량·대기시간 [unit: U1 scope=src/norma_qaoa/**,tests/** oracle=.venv/Scripts/python.exe -m pytest tests/test_manifest.py -q]
- [ ] U2 컨테이너 패키징 — Dockerfile·엔트리포인트·빌드 스크립트 [unit: U2 scope=Dockerfile,.dockerignore,docker/**,scripts/** after=U1 oracle=.venv/Scripts/python.exe docker/entrypoint.py --selftest]
- [ ] U3 입출력 명세 — JSON Schema + 계약 문서 [unit: U3 scope=docs/**,scripts/** after=U1 oracle=.venv/Scripts/python.exe scripts/check_schema.py]
- [ ] U4 운영 가이드 — 한도·취소·재시도·오류 처리 [unit: U4 scope=docs/** after=U2,U3 oracle=.venv/Scripts/python.exe -m pytest tests/ -q]
- [ ] U5 독립 검토 — 신선한 서브에이전트, read-only [unit: U5 scope=docs/** after=U1,U2,U3,U4 oracle=.venv/Scripts/python.exe scripts/check_review.py docs/2026-10-16-container-delivery-review.md]
- [ ] U6 통합 점검 — main checkout 전체 테스트 + fixture 왕복 [unit: U6 scope=docs/** after=U5 oracle=.venv/Scripts/python.exe -m pytest -q]

U2·U3·U5의 오라클 스크립트(`docker/entrypoint.py --selftest`, `scripts/check_schema.py`, `scripts/check_review.py`)는 해당 단위에서 함께 만든다. 각 스크립트는 실패 시 0이 아닌 종료 코드를 낸다.

## 알려진 제약

- 이 머신에 docker가 없다(`docker: command not found`, 2026-10-16 확인). U2의 오라클은 이미지 빌드가 아니라 **엔트리포인트 로직의 로컬 실행**이다. 이미지 빌드 성공은 이 런의 완료 조건이 아니며 보고서에 미검증으로 적는다.
- `python`이 PATH에서 Windows Store 스텁을 가리킨다. 모든 오라클은 `.venv/Scripts/python.exe`를 직접 지정한다.
- Windows 개발 환경에서는 `resource.getrusage`가 없으므로 U1의 자원 필드 일부가 `null`이 된다. 컨테이너(리눅스)에서 채워지는 것이 정상 동작이며, 테스트는 "키가 존재하고 타입이 맞다"까지만 본다.

## Progress log

- 2026-10-16 계약과 계획 작성. 승인 대기.
- 2026-10-16 13:51 승인: "어 이렇게 진행해줘."
- 2026-10-16 13:5x 포인터 생성 실패 — Amber 플러그인의 Windows 경로 비교 버그(`lib/contract.cjs:26`). `git rev-parse --show-toplevel`이 슬래시 경로를, `path.resolve`가 역슬래시 경로를 돌려주어 `startsWith(root + path.sep)`가 항상 거짓. 어떤 boundary 값으로도 통과 불가. 포인터를 제거해 Bash 차단을 해제하고 운영자 판단 대기.
- 2026-10-16 운영자 결정: Amber 기계적 강제 없이 진행. 이 계약과 계획을 지침으로 삼고 완료 조건·금지 항목·단위 순서는 수동으로 지킨다. 단위 전환은 이 로그에 기록한다.
- 2026-10-16 U1 완료 — manifest에 `attempt_id`, `container`, `resources`, `queue_wait_ms` 추가. 오라클: `pytest tests/test_manifest.py -q` 10 passed (신규 5개 포함). 전체 158 passed (기존 153 + 5).
- 2026-10-16 U2 완료 — `docker/entrypoint.py`, `Dockerfile`, `.dockerignore`, `scripts/build_image.sh`. 오라클: `entrypoint.py --selftest` 9개 검사 전부 ok. 추가 확인: 잘못된 요청 → exit 10 + error.json, 요청 파일 없음 → exit 12, 예산 부족 → exit 11. Dockerfile의 sed가 pyproject 핀을 치환하는 것과 원본이 바뀌지 않는 것 확인.
- 2026-10-16 U3 완료 — `docs/schema/{request,result}.schema.json`을 pydantic 모델에서 생성, `scripts/check_schema.py`가 재생성 대조 + fixture/result 검증. 오라클 통과. `docs/io-contract.md` 작성.
- 2026-10-16 U4 완료 — `docs/container-operations.md` 작성. 문서의 수치는 전부 소스 대조: 한도 상수는 `schema.py`, 예산 산술은 `Budget.plan`, 상태 규칙은 `decide_status`, 오류 코드는 `errors.py`/엔트리포인트 실측. 오라클: 전체 158 passed.
- 2026-10-16 U1–U4를 6610fb0으로 커밋. U5 독립 검토 시작 (신선한 서브에이전트, read-only).
