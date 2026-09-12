# RE-VISION

**Edge AI 기반 Adaptive Active Vision 정밀 부품 자율 품질검사 시스템**

금속 부품을 촬영해 판정하고, 애매하면 조명 방향·밝기를 바꿔 다시 확인하는 프로젝트입니다.
첨부 제안서·아이디어·논문 정리본을 바탕으로 마련한 **실행 가능한 초기 개발 기반**입니다.
실제 결함 검출 모델, MCU 펌웨어, WISE-PaaS 실계정 연동은 후속 개발 대상입니다.

## 바로 실행

Python **3.11 이상**. 기본 데모는 외부 패키지·카메라·LED·GPU·학습 가중치가 필요 없습니다.

```bash
git clone https://github.com/KiHyeonLee1121/RE-VISION.git
cd RE-VISION
python -m venv .venv
```

가상환경 활성화: Windows PowerShell은 `.venv\Scripts\Activate.ps1`,
Linux/macOS는 `source .venv/bin/activate`.

```bash
python -m pip install -e .
python -m revision demo --scenario scratch
python -m revision demo --scenario clean
python -m revision demo --scenario uncertain
python -m revision demo --scenario glare
```

| 데모 | 예상 동작 |
|---|---|
| `scratch` | 첫 점수 0.52 → 다른 방향 촬영 → 0.96 → FAIL |
| `clean` | 첫 점수 0.04 → PASS |
| `uncertain` | 4회 촬영해도 애매함 → REVIEW |
| `glare` | 과노출 관측 제외 → 낮은 밝기 선택 → PASS |

위 이미지·점수·노출 값은 정해진 **시나리오 fixture**입니다.
실제 AI 정확도나 광학 시뮬레이션 결과가 아닙니다.
각 실행은 JSON 결과를 출력하고 `outputs/demo/revision.db`에 결과/outbox를 저장합니다.
취득 이미지는 `outputs/demo/captures/<inspection_id>/`에 남습니다.

## 무엇을 바꾸면 되는가

| 변경 대상 | 위치 |
|---|---|
| 검사 횟수·시간·판정 threshold | `configs/`, `src/revision/config.py` |
| 카메라 / LED / 모델 | `src/revision/adapters/` |
| 다음 조명 선택 | `src/revision/policies.py` |
| 여러 관측 결합 | `src/revision/fusion.py` |
| 공통 데이터 계약 / 모듈 조립 | `src/revision/ports.py`, `service.py` |
| 데이터 검증 / 학습 / 모델 export | `src/revision/data/`, `ml/` |
| 로컬 API / WISE-PaaS 확장 | `src/revision/api.py`, `docs/wise-paas.md` |
| MCU / 대시보드 / 생산라인 확장 | `hardware/`, `apps/dashboard/`, `integrations/` |

## 설정과 실행 모드

```bash
python -m revision inspect --config configs/demo.toml --part-id part-001
```

- `demo`: 가상 장비 + 정해진 점수. 코드 연결 확인용.
- `replay`: 실제 저장 사진 + 기록된 점수 또는 ONNX 모델. 이미지/manifest를 채워 사용.
- `live`: OpenCV 카메라 + MCU serial ACK + 실제 ONNX 모델. 장비와 모델 설정이 필요.

설정 파일의 상대경로는 **해당 TOML 파일 위치 기준**입니다.
`live.example.toml`은 예시이므로 실제 장비 정보를 넣은 `configs/local.toml`로 복사합니다.
실행 모드가 live일 때 모델이 없다고 mock으로 전환하지 않습니다.

선택 패키지는 필요한 것만 설치합니다.

```bash
python -m pip install -e ".[api]"             # 로컬 API
python -m pip install -e ".[vision,hardware]" # 실제 ONNX / USB / serial
python -m pip install -e ".[train,vision]"    # 최소 학습 → ONNX → 추론
python -m pip install -e ".[dev,api,vision,train]" # 개발·검증
```

로컬 API 실행:

```bash
python -m revision serve --config configs/demo.toml
```

브라우저에서 `http://127.0.0.1:8000/docs`를 열면 검사 실행과 기록 조회를 해볼 수 있습니다.
단일 장비용 worker=1이며 인터넷 공개용 인증은 아직 없습니다.

## 학습과 데이터

데이터 중복 검사, 부품·촬영 세션에 따른 분할, 작은 logistic 기준선 학습,
ONNX export, manifest 검증, letterbox 전처리, 제품별 결과 지표 계산을 제공합니다.
실행 명령과 라벨 계약은 [데이터·모델 안내](docs/data-and-models.md)에 있습니다.
학습 기준선은 연결 검증용이며 실제 Scratch/Dent 검출·분할 모델로 교체해야 합니다.

## 검증

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

테스트는 조기 판정, 재촬영, REVIEW, 과노출 제외, 시간 한도, 장치 오류,
조명 종료 실패, 동시 접근, 기록·재전송, 데이터 누수 방지, API,
실제 작은 모델의 학습/ONNX 추론 경로를 확인합니다.
ONNX/API 선택 패키지가 없으면 해당 테스트는 skip됩니다.
CI는 선택 패키지까지 설치해 Python 3.11/3.12에서 검사하도록 구성했습니다.

## 다음에 읽을 문서

- [자료별 요구사항과 구현 현황](docs/requirements.md)
- [구조·데이터 흐름·교체 방법](docs/architecture.md)
- [데이터·학습·평가](docs/data-and-models.md)
- [MCU 조명 통신 규격](hardware/protocol.md)
- [WISE-PaaS 실연동 준비](docs/wise-paas.md)
- [단계별 개발 순서](docs/roadmap.md)
- [팀 개발 안내](CONTRIBUTING.md)

현재 threshold와 조명 정책은 초기 기준선입니다. 실제 부품·조명·모델로 검증하여 조정하고,
카메라 프레임 동기화, 위치 기반 fusion, 치수 calibration은 다음 단계에서 구현합니다.
