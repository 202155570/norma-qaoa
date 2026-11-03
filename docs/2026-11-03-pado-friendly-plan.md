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
