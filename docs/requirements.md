# 자료 검토와 구현 범위

이 초기 구조는 다음 첨부 자료를 읽고 설계했습니다.

1. `[양식] 2026 Advantech AIoT Innoworks Project 신청서 및 제안서 (1).hwp`
2. `프로젝트-아이디어.txt`
3. `프로젝트-관련-논문.txt`

원격 저장소의 시작 상태는 `0dade311ba85dc63755a26d061a9925bff4bb30a`이며
`# RE-VISION` 한 줄의 README만 존재했습니다. 신청서의 연락처·학번 등은
공개 저장소에 복사하지 않았습니다.

## 제안서에서 추출한 요구사항

| 요구사항 | 초기 코드 / 확장 위치 | 현재 범위 |
|---|---|---|
| 고정 카메라 + 다방향 LED + MCU + Edge | `ports.py`, `adapters/`, `hardware/` | 데모, OpenCV 캡처, serial ACK 계약 구현; 실장비 검증 필요 |
| 신뢰도가 높으면 즉시 판정, 불확실하면 재촬영 | `inspection.py`, `config.py` | PASS/FAIL/REVIEW/ERROR 및 횟수·시간 한도 구현 |
| 방향과 밝기 선택 | `policies.py`, `configs/live.example.toml` | 노출 상태와 각도 커버리지를 이용한 규칙 기반 초기 정책 |
| Scratch, Dent/Burr, 오염 및 반사광 구분 | `Prediction`, `Defect`, `ml/` | 공통 데이터 계약; 실제 학습 모델/데이터는 아직 없음 |
| Detection/Segmentation의 여러 관측 결합 | `fusion.py`, `ports.Fusion` | 최대 결함 점수 결합만 구현; 위치 대응·마스크 결합은 후속 |
| 결함 위치·면적·길이·방향·Severity | `domain.Defect` | 필드와 원본 픽셀 좌표 계약; 실제 계산 및 mm 보정은 후속 |
| 검사 결과·AI score·조명·시간 기록 | `adapters/sqlite_store.py` | 원본 관측과 설정, 로컬 DB, 클라우드 outbox 구현 |
| WISE-PaaS 사용 필수 | `ports.Publisher`, `docs/wise-paas.md` | 전송 확장점·재시도 큐·태그 설계; 계정별 실제 연동 필요 |
| Dashboard | `api.py`, `apps/dashboard/` | 조회/검사 API 구현; 시각 대시보드는 후속 |
| PLC/MES·자동 배출 확장 | `integrations/` | 이벤트 및 판정 계약 문서; 실장치 출력은 미구현 |

## 논문 자료가 설계에 반영된 위치

제공된 논문 정리본의 아이디어를 아래와 같이 사용했습니다. 논문의 실제 코드를
재구현했거나, 정리본에 기재된 수치를 재현했다는 의미는 아닙니다.

| 정리본의 논문 | 반영된 설계 |
|---|---|
| Next Best Light Position | `LightPolicy`를 분리하여 다음 조명 선택기 교체 가능 |
| ActiveInspect | 관측 이력, 추가 관측/종료 결정, 관측 예산 |
| Fusion of Multi-Light Source Illuminated Images… | 조명별 관측 보관, 독립적인 `Fusion` 인터페이스 |
| Photometric-Stereo-Based Defect Detection System… | 후속 normal-map 모델을 별도 predictor/fusion으로 추가 가능 |
| Defect Segmentation for Multi-Illumination Quality Control Systems | 동일 부품의 조명별 데이터를 한 그룹으로 관리, 조명 보존 증강 지침 |
| HD-RTI | 노출 품질 기록, 밝기 변경 action; HDR 병합 자체는 미구현 |
| A Dataset for Surface Defect Detection on Complex Structured Parts… | light/session/part 식별자를 포함한 데이터 계약 |

## 결정한 기본값과 미확정 사항

- Python 코어 + 선택 설치형 API/ONNX/장비 어댑터. GPU·NPU·특정 OS를 코어에 고정하지 않습니다.
- PASS ≤ 0.15, FAIL ≥ 0.85는 **데모 값**이며 실데이터 검증으로 결정해야 합니다.
- uncertainty = `1 - abs(2*score - 1)`은 점수의 중간값 근접도입니다.
  인식 실패/OOD/가려진 결함을 포함하는 통계적 불확실성이나 보정된 확률이 아닙니다.
- 기본 카메라 모델, MCU 기종, PWM 핀, LED 전류, 부품 크기/공차,
  WISE-PaaS tenant/node/device/tag 설정, 실학습 데이터셋은 자료에서 확정되지 않았습니다.
- 강화학습, VLM, photometric stereo를 초기 필수 의존성으로 두지 않았습니다.
  우선 수집/제어/재촬영/기록이 연결되는 기준선을 확보한 뒤 비교 실험으로 추가합니다.
