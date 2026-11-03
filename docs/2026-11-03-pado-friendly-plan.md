# Plan - PADO 친화 변형식으로 PPS 정확도 확보 (2026-11-03)

계약: `docs/2026-11-03-pado-friendly-contract.md`. 이 문서는 가이드이고 권한은 계약에 있다.

## 가는 길

원래 식에서 PPS가 실패한 원인은 두 가지였다. Dicke 준비 회로(CX 2,496개)와 조밀한 상관(1,225쌍 중 989쌍)이다. 변형식은 |+⟩ 시작으로 앞의 원인을 없애고, 차수 3 희소 그래프로 뒤의 원인을 줄인다. 차수가 작으면 빛원뿔 정확 계산이 가능해져, N=150에서도 PPS를 정확값과 비교할 수 있다.

U1이 데이터와 문제 파일을 만든다. U2가 정확 기준값을 세우고 kill-question에 먼저 답한다. 답이 "아니오"면 U3는 측정 없이 원인 분석과 보고서만 낸다. 세 단위는 순차로 진행한다.

실험 코드·데이터·결과는 모두 세션 스크래치패드(`SP` = `C:/Users/norma/AppData/Local/Temp/claude/C--Users-norma-Desktop-finance/94150966-2414-4560-a445-73dacc13e82d/scratchpad`)의 `pf/` 아래에 둔다. 원시 다운로드는 `pf/raw/`에 둔다. 오라클 `pf/pf_check.py`는 U1에서 만들고, 각 단위의 산출물이 계약 조건을 만족하지 않으면 0이 아닌 종료 코드를 낸다.

## Work units

- [ ] U1 데이터 150개 수집과 문제 구성 — 원래 식과 변형식, N=50/100/150 [unit: U1 scope=docs/2026-11-03-pado-friendly-*.md oracle=C:/Users/norma/Desktop/finance/.venv/Scripts/python.exe C:/Users/norma/AppData/Local/Temp/claude/C--Users-norma-Desktop-finance/94150966-2414-4560-a445-73dacc13e82d/scratchpad/pf/pf_check.py U1]
- [ ] U2 빛원뿔 정확 시뮬레이터 대조, N=50 원래 식 순위, kill-question (N=50 p=1 PPS) [unit: U2 scope=docs/2026-11-03-pado-friendly-*.md after=U1 oracle=C:/Users/norma/Desktop/finance/.venv/Scripts/python.exe C:/Users/norma/AppData/Local/Temp/claude/C--Users-norma-Desktop-finance/94150966-2414-4560-a445-73dacc13e82d/scratchpad/pf/pf_check.py U2]
- [ ] U3 PPS 규모 측정 (N=50/100/150 × p=1,2 × w), N≥100 순위 표본, 판정 보고서 [unit: U3 scope=docs/2026-11-03-pado-friendly-*.md after=U2 oracle=C:/Users/norma/Desktop/finance/.venv/Scripts/python.exe C:/Users/norma/AppData/Local/Temp/claude/C--Users-norma-Desktop-finance/94150966-2414-4560-a445-73dacc13e82d/scratchpad/pf/pf_check.py U3]

## 각 오라클이 확인하는 것

- **U1:**
  - 티커 목록 150개, 기존 50개 포함, 중복 없음.
  - 모든 티커가 공통 거래일 ≥ 500일.
  - N=50/100/150 문제 파일에 원래 식(h, J)과 변형식(h', J', λ)이 있음.
  - 변형식의 최대 차수 ≤ 3.
  - 데이터 해시가 기록됨.
- **U2:**
  - 빛원뿔 대조 결과 파일에서 p=1·2 모두 \|차이\| < 1e-9.
  - N=50 원래 식 전수 순위 결과가 있음.
  - kill-question 결과 파일에 w별 오차와 판정이 있음.
- **U3:**
  - C1 표가 N∈{50,100,150} × p∈{1,2}를 모두 덮음. 각 칸은 측정값이거나 "불가(사유)".
  - C2 표가 N 셋을 모두 덮음.
  - 판정 보고서에 `Verdict:` 줄이 있음.
  - kill-question이 "아니오"였으면 표 대신 그 사실과 원인 분석이 있음.

## 알려진 제약

- 이전 세션에서 메모리 부족으로 백그라운드 작업이 두 번 종료됐다 (2026-10-23, 2026-10-26). 총 RAM은 15.7 GB다. PPS 실행은 한 번에 하나씩, 포그라운드 위주로 한다.
- `python`이 PATH에서 Windows Store 스텁을 가리킨다. 모든 명령은 `.venv/Scripts/python.exe`를 직접 지정한다.
- Windows 콘솔이 cp949라서 한글 출력에는 `PYTHONIOENCODING=utf-8`이 필요하다.

## Progress log

- 2026-11-03 13:38 운영자 승인: "오케이 이렇게 진행해줘."
- 2026-11-03 승인 기록 도구 `record.cjs activate`가 "lies outside the zone root"로 거부했다. 원인은 git이 주는 루트 `C:/...`와 `path.resolve`의 `C:\...` 구분자 불일치(record.cjs:75)다. 플러그인은 고치지 않았고 포인터도 손으로 만들지 않았다. 실험은 저장소 밖 스크래치패드에서만 하므로, 이 계약을 지침으로 진행한다. 단위 전이 명령(`unit`)은 쓸 수 없어 이 로그에 기록한다.
- 이전 스크래치패드의 스크립트와 가격 파일이 OS 임시폴더 정리로 사라져 새로 작성했다. padopauli는 .venv의 2.0.2를 쓴다.
- U1 완료, 오라클 PASS.
  - 150개 모두 2년 이력 통과, 대체 없음. 공통 504일(2024-10-29~2026-11-02).
  - 가산 모형(c + a_i + a_j)의 Q 분산 설명력 21%/17%/19%, 남긴 잔차 |R| 비중 21%/15%/10% (N=50/100/150).
  - λ: N=50 2.909, N=100 4.705, N=150 6.196 (p=1 기대 선택 수 6.000).
  - 빛원뿔 대조 최대 차이 3.6e-14 (p=1·2, 20큐비트).
- U2 완료, 오라클 PASS.
  - PPS 회로 규약 자체 점검: 12큐비트, w=12에서 |차이| ≤ 4.4e-15.
  - kill-question 통과: N=50, p=1에서 w=4·5·6 모두 오차 3.9e-16 × 이득. 단, 차수 3 그래프의 p=1 빛원뿔이 6큐비트 이하라서 판별력이 없다. 판별은 p=2(빛원뿔 ≤14)에서 한다.
  - C2 N=50: 변형식 최적해가 원래 식 1,429위 / 15,890,700 (상위 0.009%), 원래 최적해와 6개 중 4개 공통, G·V 상관 0.87.
- U3 진행 중 (2026-11-03 14:xx 정지).
  - C1 측정 13/14 설정 완료. p=2 오차/이득: N=50 4.7e-4 (w=4) → 4.0e-7 (w=6); N=100 4.5e-5 → 1.7e-8; N=150 1.0e-4 (w=4), 4.3e-6 (w=5). 컴파일 ≤ 178 s.
  - N=150 p=2 w=6: 시스템 메모리 부족으로 백그라운드 셸이 종료됐다. 그러나 python 프로세스(PID 1048, 5.5 GB)는 남아 있었고, 이를 끄는 명령은 권한 분류기가 거부했다. 남은 여유 메모리가 0.8 GB라서 C2 N=100·150 순위 계산(약 1~2 GB)을 시작하지 않고 운영자에게 가져간다.
- 운영자 "다음 단계 진행해줘." 남아 있던 프로세스는 스스로 끝나 N=150 p=2 w=6 행을 남겼다(오차/이득 2.3e-8, 컴파일 317 s, 최대 6.79 GB). 여유 메모리 7.5 GB를 확인한 뒤 순위 계산을 실행했다.
- U3 완료, 오라클 PASS.
  - C1 promote: 6칸 모두 기준 충족.
  - C2: N=50 상위 0.009%, N=100 상위 0%(표본 100만 전부보다 좋음), N=150 상위 3.5%로 실패. 원인은 해에 포함된 버려진 상한 쌍 DBC–XOP(+2.37)다.
  - 판정: hold. 보고서는 스크래치패드 `pf/verdict.md`.
