# 데이터 → 학습 → 추론

팀의 기본 학습 환경은 **Colab Pro GPU + Google Drive 데이터 저장**입니다.
[전용 노트북과 경로·체크포인트 안내](colab-drive.md)를 먼저 확인하세요.
GPU용 MobileNetV3-Small 분류 학습과 아래 CPU logistic 연결 예제를 모두 제공합니다.

## 수집 계약

기본 단위는 **같은 물리적 부품을 여러 조명에서 촬영한 묶음**입니다.
`sample_id`, `part_id`, `session_id`, `light_id`, `image_path`, `label`을 기록합니다.
`part_id`는 촬영 날짜가 바뀌어도 유지합니다. 부품에 새 결함을 가한 경우 상태 ID를 별도로
기록하되, 원래 물리적 부품을 연결하는 그룹이 깨지지 않도록 데이터 설계를 확장합니다.

분류 라벨은 `clean`/`defective`, 후속 위치 라벨은 scratch/dent/burr/contamination 등입니다.
반사광 때문에 특정 사진에서 결함이 안 보여도 **실제 불량 부품은 clean으로 바꾸지 않습니다.**
실물 검사로 제품 라벨을 정하고, 영상에서의 가시성/위치 라벨은 별도로 기록하세요.
현재 validator는 공통 필드와 파일/checksum/제품 라벨만 검사합니다.
COCO/마스크 annotation 변환 및 기하 검증은 향후 전용 importer에서 구현합니다.

원본 이미지와 데이터 split은 기본적으로 Git 제외입니다. 예제 manifest의 이미지는
동봉되지 않았으므로 실제 파일로 채워야 합니다.

```bash
python -m revision dataset data/my-manifest.jsonl
python -m revision dataset data/my-manifest.jsonl --output data/processed --seed 42
```

동일 SHA256 이미지, 중복 sample ID, 파일 누락, 부품 라벨 불일치를 거부합니다.
부품 또는 촬영 세션으로 연결된 모든 이미지를 같은 split에 넣습니다.
그룹 수 기준 약 60/20/20 분할이며 독립 그룹이 3개 미만이면 오류입니다.
한 세션에서 모든 부품을 찍으면 모두 한 그룹이 되므로 여러 독립 세션을 수집하세요.
**분할 후 클래스 비율과 재질/결함/조명 분포를 직접 확인해야 하며 자동 stratification은 없습니다.**
생성된 split 파일은 로컬 재현을 위해 절대 이미지 경로를 사용합니다.
다른 컴퓨터로 옮길 때 원본 manifest 기준으로 다시 분할하거나 경로를 재배치하세요.

## 실행 가능한 최소 학습 예제

```bash
python -m pip install -e ".[train,vision]"
python -m revision.ml.train_baseline --train data/processed/train.jsonl --val data/processed/val.jsonl --output models/weights/baseline
```

32×32 RGB logistic classifier를 학습하고 `model.onnx`, `manifest.json`, `metrics.json`을 만듭니다.
train/val은 각각 정상·불량을 포함해야 하며 부품/세션/이미지 중복을 다시 검사합니다.
기존 출력 폴더는 덮어쓰지 않습니다. 테스트 split은 학습에 사용하지 않습니다.
이 모델은 데이터와 export/runtime 연결을 점검하기 위한 기준선이며,
미세 결함의 종류·위치·영역을 검출하는 최종 모델이 아닙니다.
현재 학습은 메모리에 전체 이미지를 로드하므로 소규모 PoC에 사용합니다.

## 공통 전처리와 모델 계약

- 이미지 EXIF 방향 적용 → RGB → 비율을 유지하는 letterbox → `[0,1]` → mean/std → NCHW float32.
- resize 크기, 입력·출력 이름, 출력의 sigmoid 적용 여부, model SHA256을 manifest로 관리합니다.
- 실제 구현된 ONNX 어댑터의 출력은 이미지 한 장당 scalar 한 개입니다.
  `[1, 2]` 분류 출력, 검출 tensor, segmentation mask는 해당 형식용 새 어댑터가 필요합니다.
- 모델을 학습할 때도 같은 전처리를 사용합니다. 위치 정보는 `LetterboxTransform`으로
  원본 이미지 좌표로 되돌립니다. 실제 mm 치수는 카메라 보정과 기준척 없이는 계산하지 않습니다.
- `output_kind=defect_probability`는 출력 범위/활성화 계약입니다. 확률 보정 완료를 뜻하지 않습니다.
- provider가 설치되어 있지 않으면 오류가 납니다. CPU fallback을 원하면 manifest에 명시합니다.

ONNX 호출 방식의 기준은 [공식 Python API](https://onnxruntime.ai/docs/api/python/api_summary.html)입니다.

## 실제 결함 AI를 개발할 다음 순서

1. 정밀 부품 고정 지그, 카메라 초점/노출, LED 방향/밝기를 고정한 수집 프로토콜 확정.
2. 여러 부품·세션·결함 크기와 정상 반사광을 포함해 다중 조명 이미지와 실물 정답 수집.
3. 단일 조명 detector/segmenter 기준선 구축. 조명 ID와 mask/bbox 계약을 유지.
4. 밝기·노이즈·약한 blur 증강을 검증하고, 회전 시 조명 방향과 라벨도 일관되게 변환.
5. 단일 조명 / 모든 조명 / 규칙 기반 적응 조명을 같은 테스트 부품에서 비교.
6. 검증 세트에서 threshold, 최소 관측 수, 품질 기준을 선택하고 test는 마지막에만 사용.
7. 충분한 관측 데이터가 모이면 feature fusion, next-best-light 학습, photometric stereo 비교.

## 평가

```bash
python -m revision evaluate experiments/results.example.jsonl
```

제품마다 `part_id`, `label`, `verdict`, `duration_ms`, `view_count`가 있는 JSONL을 입력합니다.
제품 수준 defect recall, false-pass/false-fail, REVIEW/ERROR 비율, 자동 판정 비율,
평균 관측 횟수, 지연 p50/p95/p99를 계산합니다. REVIEW를 정답으로 간주하거나
분모에서 숨기지 않습니다. 위치 모델 도입 후 IoU/Dice, 작은 결함 recall, 치수 오차를 추가합니다.
