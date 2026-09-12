# 구현 순서

## 0. 현재 초기 기반

실행 가능한 demo/replay, 검사 상태와 품질 기준, 조명 선택 및 점수 결합,
USB/serial 연결용 adapter, SQLite/outbox, 로컬 API, 데이터 검증·그룹 분할,
최소 학습/ONNX export/runtime, 핵심 테스트 및 CI 설정.

Colab Pro/Drive 노트북과 GPU 분류 fine-tuning, epoch 체크포인트 저장·재개,
Drive 모델 묶음 저장도 제공합니다. 실제 계정·GPU·팀 데이터로의 학습은 아직 수행하지 않았습니다.

## 1. 장치와 데이터 확보

담당 영역: hardware + data.
실제 MCU firmware, 채널/밝기 보정, 지그, 노출/초점/white balance 제어,
동일 제품 다방향 촬영, 정상 반사광과 실제 미세결함 ground truth를 확보합니다.
완료 조건은 LED 조건과 이미지가 정확히 대응하는 데이터가 여러 독립 세션에 존재하는 것입니다.

## 2. 실제 단일 영상 AI

담당 영역: ml + adapters.
Scratch 중심 detector/segmenter 또는 적절한 anomaly model을 학습합니다.
학습 데이터와 동일한 전처리/원본 좌표 복원/모델 manifest를 검증하고,
실장비 추론 latency와 false-pass를 측정합니다.

## 3. 능동 재검사의 효과 검증

담당 영역: policy + fusion + experiments.
단일 조명/전부 촬영/적응 촬영을 같은 부품으로 비교합니다.
반사광 오탐을 여러 관측의 위치·형상·특징 대응으로 해소하는 fusion을 추가합니다.
현재 max-score만으로 정상 반사광과 실제 결함을 근본적으로 구별했다고 주장하지 않습니다.

## 4. WISE-PaaS 실연동과 시연

담당 영역: integrations + dashboard.
실제 계정의 SDK/tag 계약에 맞춰 Publisher를 구현하고 Dashboard에서 추적합니다.
네트워크 단절, 복구, 중복 전송, 검사 기록, REVIEW/ERROR 처리까지 시연합니다.

## 5. 고도화

충분한 데이터가 생긴 뒤 정보 이득 기반 조명 선택, 학습 정책, HDR/photometric stereo,
제품별 calibration, 치수·Severity 판정, PLC/MES와 배출기 연동을 비교·추가합니다.
