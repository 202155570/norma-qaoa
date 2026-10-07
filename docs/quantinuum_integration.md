# Quantinuum 연동 경로

## 현재 상태 (norma-qaoa 0.1.0, 2026-10-07)

| 경로 | kind | 상태 |
|---|---|---|
| Qiskit Aer (CPU) | `local_simulator` | 기본 백엔드 (`--backend aer`) |
| Quantinuum H2-1LE (pytket-quantinuum[pecos]) | `local_simulator` | 구현 완료 (`--backend quantinuum_local`). 로컬 실행, 노이즈 없음, 네트워크 사용 없음 |
| Quantinuum Nexus 에뮬레이터 (H2-Emulator 등) | `cloud_emulator` | 미구현. 정책상 `allow_external_transfer=false`면 거부 |
| Quantinuum 하드웨어 (H2, Helios) | `hardware_qpu` | 미구현. 정책상 항상 거부 |

`qnexus`와 `qiskit-ibm-runtime`은 import하지 않는다. `tests/test_guards.py`가 이를 검사한다.

## 구조

- 모든 백엔드는 `src/norma_qaoa/backends/base.py`의 `SamplingBackend` 규약을 따른다.
  - `prepare(spec, seed_transpiler)`
  - `run(parameter_sets, shots, seed) -> list[dict[str, int]]`
  - `info()`
- 반환 counts의 key는 **Qiskit 규약 bitstring**(little-endian, qubit 0이 맨 오른쪽)이어야 한다.
  - pytket 결과(readout tuple `(c[0], c[1], ...)`)는 어댑터 안에서 `tket_readout_to_qiskit_bitstring()`으로 변환한다.
  - 자산 순서 변환은 `ising.bitstring_to_bit_vector()` 한 곳에서만 한다.
- 새 어댑터는 `tests/test_backend_conformance.py`를 통과해야 한다. 이 테스트는 다음을 확인한다.
  - 결정적 회로의 비트 순서
  - seed를 주면 결과가 재현되는지
  - 다른 백엔드와 같은 파라미터에서 분포가 일치하는지(TVD < 0.06)
- QAOA 회로는 `circuits.QaoaSpec`(정규화된 Z/ZZ 항)에서 각 SDK로 직접 만든다. pytket-qiskit 변환기는 `qiskit-ibm-runtime`을 함께 설치하므로 쓰지 않는다.
- pytket 각도 단위는 half-turn이다: `Rz(a) = exp(-iπaZ/2)`, 즉 `a = θ/π`.
- 하드웨어와 외부 전송 차단은 `policy.assert_backend_allowed()` 한 곳에서 한다.

## H2-1LE 어댑터 메모

- `QuantinuumBackend(device_name="H2-1LE", data=QuantinuumBackendData(..., local_emulator=True))`로 만든다.
  - `data`를 주면 pytket-quantinuum은 온라인 조회를 하지 않는다.
  - 0.56.1부터 원격 제출 기능이 아예 제거되었다.
- `pytket.extensions.quantinuum.backends.data.H2` 상수의 gate set에는 `Measure`와 `Reset`이 없다. 그래서 측정을 포함한 회로가 `GateSetPredicate`에 걸린다. 어댑터는 dataclass 기본 gate set에 있는 이 두 연산을 추가한다.
- Quantinuum 컴파일러는 기호 파라미터를 받지 않는다(`NoSymbolsPredicate`). 그래서 평가마다 숫자 각도로 회로를 만들고 컴파일한다. manifest의 `backend_circuit_hash`는 null이다.
- 실행 시간: toy 문제(4큐비트, 회로 60개)가 약 17초 걸렸다. Aer는 약 0.8초다.
- `process_circuits(..., seed=...)`를 지원한다. 같은 seed로 실행하면 결과가 재현되는 것을 테스트로 확인했다.

## Nexus 에뮬레이터 / 하드웨어 어댑터를 추가할 때

공식 문서 기준 qnexus 흐름은 다음과 같다(https://docs.quantinuum.com/systems/trainings/alternate_pathways/qiskit_h2.html).

```text
qnx.projects.get_or_create(...) / qnx.context.set_active_project(...)
config = qnx.QuantinuumConfig(device_name="H2-Emulator" | "H2-1" | ...)
ref = qnx.circuits.upload(circuit=<pytket Circuit>, name=...)
job = qnx.start_compile_job(circuits=[ref], optimisation_level=..., backend_config=config, name=...)
qnx.jobs.wait_for(job); compiled = qnx.jobs.results(job)[0].get_output()
cost = qnx.client.circuits.cost(compiled, n_shots=..., backend_config=config)   # 하드웨어 HQC 추정
job = qnx.start_execute_job(circuits=[compiled], backend_config=config, n_shots=[...], name=...)
qnx.jobs.wait_for(job); result = qnx.jobs.results(job)[0].download_result()   # BackendResult
```

어댑터 구현 체크리스트:
1. `kind`를 지정한다. 에뮬레이터는 `cloud_emulator`, 실제 장비는 `hardware_qpu`다.
2. counts를 `tket_readout_to_qiskit_bitstring()`으로 변환하고, 적합성 테스트를 통과시킨다.
3. 회로를 실행하기 전에 비용(HQC)을 추정하고, 작업 예산과 월 한도를 확인하는 단계를 둔다(사양 14).
4. 격자 49점을 job 하나로 묶어 제출할 수 있다(`run`은 회로 묶음을 받는다). 큐 대기 시간과 300초 실행 한도를 어떻게 나눌지는 미결이다.
5. Nexus job ID, 실제 장치명, HQC 사용량을 manifest의 `backend` 항목에 기록한다.

정책상 막혀 있는 지점(사양 근거):
- `hardware_qpu`: 사양 p.9·p.17에서 `allow_qpu=false`이고, p.3에 따라 실행 환경 변경은 양사 승인 대상이다(D03). 승인되면 `schema.validate_request`의 `QPU_NOT_ALLOWED` 규칙과 `policy.py`를 함께 바꾼다.
- `cloud_emulator`: 사양 16에 따라 외부 반출(제3자 클라우드)은 사전 승인을 받아야 한다. 승인되면 config `allow_external_transfer=true`로 켠다.
- 비용과 한도: 사양 14·D07에 따라 HQC 단가, 월 상한, 실패 작업 비용이 합의되어야 한다.

## 개발 환경 메모 (Windows Smart App Control)

이 개발 PC는 Smart App Control이 켜져 있다.
- 설치 직후에는 `rustworkx 0.18.1`과 `pytket`(2.17.0, 2.18.0, 2.18.3, 2.18.4)의 DLL이 차단되었다.
- `rustworkx`는 0.17.1로 고정했다(`pyproject.toml`).
- `pytket 2.18.3`은 이후 다시 시도했을 때 정상적으로 로드되었고, 모든 Quantinuum 테스트가 실제 에뮬레이터로 실행되었다.
- 같은 차단이 다시 생기면 Quantinuum 테스트는 그 사유를 표시하고 skip한다. Aer 경로는 영향을 받지 않는다.
