# RE-VISION

**Edge AI 기반 Adaptive Active Vision 정밀 부품 자율 품질검사 시스템**

## 프로젝트 아이디어와 핵심 기술

금속 부품의 흠집은 조명에 따라 가려지거나 반사광처럼 보일 수 있습니다.
RE-VISION은 **AI가 판단하기 어려울 때 조명 방향·밝기를 바꿔 다시 확인하는 검사 시스템**입니다.
알루미늄 가공품 등의 Scratch, Dent/Burr, 표면 오염을 검사 대상으로 하며,
모든 부품을 반복 촬영하지 않고 필요한 경우에만 추가 촬영하는 것을 목표로 합니다.

**기본 흐름:** 촬영 → AI 분석 → 확실하면 판정 / 애매하면 조명 변경·재촬영 → 관측 결합 → 결과 저장

| 핵심 기술 | 역할 | 현재 구현 |
|---|---|---|
| Edge AI 비전 | 부품 영상에서 결함 여부 분석 | ONNX 추론, MobileNetV3-Small 정상/불량 분류 학습 기준선 |
| Adaptive Active Vision | 다음 조명 방향·밝기를 선택해 재촬영 | 노출 상태·촬영 각도를 고려한 규칙 기반 정책 |
| 다중 관측 결합 | 여러 조명에서 얻은 결과로 최종 판정 | 유효 관측의 최대 결함 점수 결합 |
| 모듈형 장치 제어 | 카메라·LED·AI 모델을 독립적으로 교체 | 공통 인터페이스, OpenCV 카메라·MCU serial 연결부 |
| AIoT 기록·모니터링 | 검사 이력 저장과 외부 시스템 전달 | SQLite, 전송 대기열·재시도, 로컬 API |

현재는 **실행 가능한 초기 개발 기반**입니다. 실제 결함 검출·분할 모델, 위치 기반 관측 결합,
MCU 펌웨어, WISE-PaaS 실계정 연동은 후속 개발 대상입니다.
판정은 `PASS`·`FAIL`, 증거가 부족하면 `REVIEW`, 장치·처리 오류가 발생하면 `ERROR`로 구분합니다.

## 디렉토리별 역할

| 디렉토리 | 수행하는 기능 |
|---|---|
| `src/` | 설치해서 실행하는 Python 소스 패키지 |
| `src/revision/` | 촬영·추론·재검사·판정 전체 흐름, 공통 데이터 형식, 설정, CLI·API |
| `src/revision/adapters/` | 카메라, LED serial 제어, ONNX 모델, SQLite 저장, HTTP 전송의 구체 구현 |
| `src/revision/data/` | 데이터 목록 검증, 중복 검사, 부품·촬영 세션별 분할, Drive 데이터 복사, 평가 지표 |
| `src/revision/ml/` | 전처리, CPU/GPU 학습, 체크포인트 저장·재개, ONNX 내보내기·검증 |
| `configs/` | demo/replay/live 실행 설정, 조명 후보·판정 기준, Colab 학습 설정 |
| `notebooks/` | Colab에서 Drive 연결부터 GPU 학습·모델 저장까지 실행하는 노트북 |
| `data/` | 데이터 목록과 녹화 이미지 재실행용 형식 예제 |
| `data/raw/` | 로컬 원본 이미지 배치 위치. 실제 학습 원본은 Drive에서 관리하며 Git에서 제외 |
| `data/processed/` | 검증·분할된 학습/검증/테스트 데이터 목록 저장 위치. 생성 결과는 Git에서 제외 |
| `models/` | 모델 입력·출력·전처리·checksum을 정의하는 manifest 예제 |
| `models/weights/` | Drive에서 내려받은 모델 가중치·manifest 배치 위치. 실제 가중치는 Git에서 제외 |
| `hardware/` | 카메라·LED 연결 지침과 Edge↔MCU 통신 규격 |
| `hardware/firmware/` | 선정된 MCU용 조명 제어 펌웨어를 구현할 위치. 현재는 구현 안내만 제공 |
| `apps/dashboard/` | 검사 화면 개발 및 WISE-PaaS Dashboard 연결 안내. 시각 UI는 후속 구현 |
| `integrations/` | WISE-PaaS, PLC/MES, 자동 배출기 등 외부 시스템 확장 계약·안내 |
| `experiments/` | 단일 조명·전체 촬영·적응 촬영 비교 실험 계획과 결과 형식 예제 |
| `tests/` | 검사 흐름, 오류 처리, 데이터 분할, 저장·재개, API, 학습·ONNX 연결 테스트 |
| `docs/` | 상세 설계, 데이터·학습 방법, 장비·클라우드 연결, 개발 로드맵 |
| `.github/workflows/` | GitHub에 반영된 코드의 자동 검사·테스트 설정 |
| `outputs/` | 실행 중 생성되는 촬영 이미지, 검사 DB, 데모 결과. Git에서 제외 |

카메라·모델 등을 교체할 때는 `src/revision/ports.py`의 인터페이스를 구현하고
`service.py`에서 연결합니다. 다음 조명 선택은 `policies.py`, 관측 결합은 `fusion.py`,
검사 순서는 `inspection.py`에서 수정합니다.

## 외부 애플리케이션·장비 연결

| 대상 | 연결 방식과 데이터 흐름 | 준비할 것 / 현재 범위 |
|---|---|---|
| **Google Colab Pro** | GitHub의 학습 노트북을 열어 코드 설치 → GPU 확인 → 학습 → ONNX 변환 | GPU 런타임 선택, 학습 설정 지정. [노트북 열기](https://colab.research.google.com/github/KiHyeonLee1121/RE-VISION/blob/main/notebooks/01_train_colab.ipynb) |
| **Google Drive** | 노트북의 `drive.mount()`로 인증 → 데이터 폴더/ZIP을 Colab 작업 디스크로 복사 → 체크포인트·모델을 Drive에 저장 | 데이터셋·`manifest.jsonl` 준비, Drive 경로·`RUN_ID` 지정. [준비 안내](docs/colab-drive.md) |
| **로컬 PC / Edge 실행 프로그램** | Drive의 `model-bundle.zip`을 내려받아 `models/weights/`에 해제 → 설정의 `model_manifest`로 ONNX 로드 | ONNX 실행 환경과 모델 파일. 실제 장비용 threshold는 별도 검증 |
| **웹 브라우저 / 별도 프런트엔드** | FastAPI의 검사 실행·기록 조회 API 호출 | 로컬 API 구현. [API 안내](apps/dashboard/README.md), 시각 대시보드는 후속 구현 |
| **카메라 / LED 제어 MCU** | OpenCV로 영상 취득, serial JSON 명령·ACK로 조명 전환 후 재촬영 | 카메라·포트 설정과 [통신 규격](hardware/protocol.md)에 맞는 MCU 펌웨어 필요 |
| **Advantech WISE-PaaS** | 로컬 전송 대기열 → `Publisher` 구현체 또는 팀의 HTTPS gateway → WISE-PaaS 저장·시각화 | 대회 필수 연동 대상. 현재는 확장점·재시도 구조이며 실제 계정별 SDK·태그 연동은 후속. [연동 안내](docs/wise-paas.md) |
| **PLC / MES / 자동 배출기** | 검사 ID·부품 ID·판정 이벤트를 전용 adapter로 전달 | 확장 계약만 준비. 실제 장치 출력은 미구현. [확장 안내](integrations/README.md) |
| **GitHub Actions** | 원격 push/PR 시 코드 형식·테스트·CPU 학습 연결 검사 실행 | 저장소의 workflow로 실행. 실제 Colab 인증·CUDA 검증과는 별도 |

학습 데이터 흐름은 **GitHub 코드 + Drive 원본 → Colab GPU 학습 → Drive 모델 묶음 → PC/Edge 추론**입니다.
중단된 학습은 같은 데이터·코드·설정과 `RUN_ID`를 사용하고 `RESUME=True`로 재개합니다.
Colab 노트북은 연결 코드를 제공하며 본인 계정 인증과 실제 GPU 학습은 노트북 실행 시 진행합니다.

## 빠른 실행

Python **3.11 이상**에서 저장소를 내려받고 가상환경을 만듭니다.

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
```

데모는 장비·가중치 없이 동작하는 정해진 시나리오이며 실제 AI 성능 결과가 아닙니다.
`clean`은 즉시 PASS, `scratch`는 재촬영 후 FAIL, `uncertain`은 관측 한도 후 REVIEW,
`glare`는 과노출 관측을 제외하고 밝기를 바꿔 확인합니다.
결과는 `outputs/demo/`의 이미지와 SQLite DB에 저장합니다.

| 실행 모드 | 용도 |
|---|---|
| `demo` | 가상 장비·정해진 점수로 전체 흐름 확인 |
| `replay` | 저장된 사진과 기록 점수 또는 ONNX 모델로 재실행 |
| `live` | 실제 카메라·MCU·ONNX 모델로 검사. 장비 설정과 모델 필요 |

```bash
# 설정 파일로 검사
python -m revision inspect --config configs/demo.toml --part-id part-001

# 브라우저에서 사용할 로컬 API 실행
python -m pip install -e ".[api]"
python -m revision serve --config configs/demo.toml
```

API 실행 후 [로컬 API 사용 화면](http://127.0.0.1:8000/docs)을 엽니다.
단일 장비용 worker=1이며 인터넷 공개용 인증은 아직 없습니다.
설정의 상대경로는 **해당 TOML 파일 위치 기준**입니다.
실제 장비 설정은 `configs/live.example.toml`을 `configs/local.toml`로 복사해 수정합니다.

## 상세 문서와 개발 안내

- [구조·교체 방법](docs/architecture.md) · [자료별 요구사항](docs/requirements.md)
- [데이터·모델·평가](docs/data-and-models.md) · [Colab·Drive 학습](docs/colab-drive.md)
- [MCU 통신](hardware/protocol.md) · [WISE-PaaS 연동](docs/wise-paas.md)
- [개발 순서](docs/roadmap.md) · [개발 환경·검증 방법](CONTRIBUTING.md)

**작업을 마칠 때마다 아래 변경 이력에 해당 작업을 한 줄씩 추가합니다.**
팀 개발 규칙은 `CONTRIBUTING.md`, 코딩 에이전트용 규칙은 `AGENTS.md`에 명시합니다.

## 변경 이력

날짜는 한국 시간(KST) 기준이며 최신 날짜를 위에 둡니다.
같은 날의 새 작업은 해당 날짜의 맨 위에 추가하고 기존 기록은 유지합니다.

### 2026-09-12

- **문서 정리:** README를 프로젝트 아이디어·기술, 디렉토리 역할, 외부 연결, 일자별 이력 순서로 재구성하고 작업별 이력 갱신 규칙을 추가.
- **Colab·Drive 연결:** GPU 분류 학습 노트북, 데이터 폴더/ZIP 복사, epoch 체크포인트 저장·재개, ONNX 변환·검증·Drive 저장 추가. CPU 환경의 44개 테스트 및 GitHub CI 통과.
- **초기 개발 기반:** 교체 가능한 카메라·LED·모델·정책 구조, 적응 재검사 루프, 데모·재실행, 로컬 API·DB·전송 대기열, 데이터 분할·학습 기준선·개발 문서 구성.
