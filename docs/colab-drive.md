# Colab Pro + Google Drive 학습

[Colab에서 학습 노트북 열기](https://colab.research.google.com/github/KiHyeonLee1121/RE-VISION/blob/main/notebooks/01_train_colab.ipynb)

코드는 GitHub, 원본 데이터와 학습 결과는 본인 Google Drive에 둡니다.
Colab 작업 디스크에서 GPU 학습을 수행하고 매 epoch 체크포인트를 Drive에 복사합니다.
이 연결은 노트북의 `google.colab.drive.mount()`로 이루어집니다.
GitHub에 Google 토큰·서비스 계정 키를 넣거나 공개 데이터셋 링크를 만들 필요가 없습니다.
팀원이 사용할 때는 각자 접근 권한이 있는 Drive 경로를 설정합니다.

## Drive에서 준비할 경로

기본 프로젝트 경로는 `내 드라이브/RE-VISION/`입니다.

| 경로 | 내용 | 준비 주체 |
|---|---|---|
| `datasets/v001/manifest.jsonl` | 이미지·부품·세션·조명·라벨 목록 | 팀 |
| `datasets/v001/images/...` | 원본 이미지, 부품/세션별 하위 폴더 권장 | 팀 |
| `datasets/v001.zip` | 위 폴더 대신 선택할 수 있는 ZIP | 팀, 선택 |
| `runs/<RUN_ID>/run.json` | 학습 설정, 코드 커밋, GPU·라이브러리 버전 | 학습 코드 |
| `runs/<RUN_ID>/dataset-snapshot.json` | 임시 경로를 제외한 학습/검증 데이터와 checksum | 학습 코드 |
| `runs/<RUN_ID>/checkpoints/epoch-*.pt` | epoch별 재개용 체크포인트 | 학습 코드 |
| `runs/<RUN_ID>/latest.json` | 마지막 저장에 성공한 checkpoint와 checksum | 학습 코드 |
| `runs/<RUN_ID>/history.json` | loss/accuracy 이력 | 학습 코드 |
| `runs/<RUN_ID>/split-summary.json` | train/val/test 그룹 분할 정보 | 노트북 |
| `runs/<RUN_ID>/exports/<model-hash>/` | ONNX, manifest, 검증 결과, 모델 ZIP | 내보내기 코드 |

Drive 안에 위 폴더를 지금 자동 생성하는 작업은 하지 않았습니다.
노트북 실행 시 지정한 `runs/<RUN_ID>`만 생성하고 원본 데이터는 수정하지 않습니다.

## 데이터 목록 예시

`manifest.jsonl` 한 줄이 이미지 한 장입니다. `image_path`는 manifest 위치 기준의
상대경로여야 하며 데이터셋 폴더 밖을 가리킬 수 없습니다.

```json
{"sample_id":"p001-front","part_id":"p001","session_id":"session01","light_id":"front","image_path":"images/session01/p001/front.png","label":"defective"}
{"sample_id":"p001-rear","part_id":"p001","session_id":"session01","light_id":"rear","image_path":"images/session01/p001/rear.png","label":"defective"}
{"sample_id":"p002-front","part_id":"p002","session_id":"session01","light_id":"front","image_path":"images/session01/p002/front.png","label":"clean"}
```

사진만 모으면 물리적 부품과 촬영 세션을 나중에 구분하기 어렵습니다.
처음부터 부품/세션/조명 ID를 기록하세요. 같은 실제 부품의 다른 조명 사진을
train과 val/test에 나누면 데이터 누수가 생깁니다.
현재 분할은 부품 또는 세션이 연결된 전체 그룹을 함께 이동합니다.
독립 그룹이 최소 3개 필요하며, train/val 각각 정상과 불량이 있어야 합니다.
이미지 수가 아니라 독립 부품·세션과 라벨 분포를 먼저 확보하세요.

ZIP을 쓸 경우 압축 내부 최상위는 `manifest.jsonl`과 `images/`여야 합니다.
`v001/manifest.jsonl`처럼 상위 폴더까지 싸서 압축하면 현재 코드는 거부합니다.
ZIP 내부 경로 이탈·심볼릭 링크·파일 중복을 검사하고, 디스크 용량을 확인한 뒤 로컬에 풉니다.
이미지 checksum 중복, 없는 파일, 라벨 불일치도 검사합니다.
현재 staged 데이터는 이진 분류용 이미지입니다. segmentation mask/COCO 학습은 별도 importer가 필요합니다.

## 노트북 실행 순서

1. 위 링크를 열어 본인 Drive에 노트북 사본을 저장하고 GPU 런타임을 선택합니다.
2. 코드 설치 셀을 실행합니다. 기존 Colab CUDA PyTorch가 요구 버전을 충족하면 그대로 사용합니다.
   설치 후 CUDA를 확인하며 GPU가 없으면 명확히 중단합니다.
3. Drive를 마운트하고 `PROJECT_ROOT`, `DATASET_SOURCE`, `RUN_ID`를 지정합니다.
4. `configs/train.colab.toml` 설정을 확인합니다. 처음에는 `RESUME=False`입니다.
5. 데이터 복사·검증·분할 → GPU 학습 → ONNX 내보내기 순서로 실행합니다.
6. Drive에 저장된 체크포인트와 `model-bundle.zip`을 확인합니다.

초기 설정은 MobileNetV3-Small/ImageNet 가중치, 224×224 letterbox, batch 16,
AdamW, 20 epoch, CUDA AMP입니다. 기본적으로 전체 네트워크를 fine-tuning합니다.
학습 데이터 증강과 클래스 가중치는 아직 추가하지 않았습니다.
**이 모델은 정상/불량 이미지 분류 기준선입니다. 실제 Scratch/Dent 위치·영역을 반환하는
최종 모델 구조를 확정한 것은 아닙니다.** 모델 생성부는 `build_model()`로 분리했습니다.
기존 CPU logistic 학습 예제도 유지됩니다.

## 런타임 중단 후 재개

새 Colab 런타임에서 같은 노트북을 열고 다음을 맞춥니다.

- setup의 `REPO_REF`: 기존 `run.json`의 `code_revision` 값
- `RUN_ID`: 중단한 학습과 동일
- `DATASET_SOURCE`와 split seed, 학습 설정: 동일
- `RESUME=True`

처음부터 셀을 실행하면 데이터는 새 작업 디스크에 다시 복사되고,
모델/optimizer/AMP scaler/난수 상태/최고 모델/이력을 마지막 완료 epoch에서 불러옵니다.
이미지의 임시 절대경로는 데이터 식별에서 제외하므로 Colab 경로가 바뀌어도 재개됩니다.
데이터·라벨·split·코드 커밋·학습 설정이 다르면 중단하여 혼합을 방지합니다.
`epochs`만 늘릴 수 있으며, 이는 **추가 epoch 수가 아닌 총 목표 epoch 수**입니다.

첫 epoch 저장 이전에 끊긴 경우에는 재개 체크포인트가 없으므로 새 RUN_ID로 시작합니다.
저장 완료 메시지가 나오지 않은 epoch은 다시 실행될 수 있습니다.
하드웨어/라이브러리 버전 차이에 따른 완전한 bitwise 재현은 보장하지 않으며 환경 버전을 기록합니다.
같은 RUN_ID를 여러 런타임에서 동시에 쓰는 분산 잠금은 없습니다.

체크포인트는 새 파일로 저장·복사하고 checksum 확인 후 `latest.json`을 바꿉니다.
전송 중단에 대비해 이전 epoch 파일을 자동 삭제하지 않습니다. 저장 공간은 epoch 수에 따라 증가합니다.
손상된 latest checkpoint는 자동으로 무시하지 않고 오류를 냅니다.
이전 정상 파일을 복구할 때는 해당 파일 checksum을 검증한 뒤 pointer를 복구해야 합니다.

## 결과를 프로젝트 추론 코드에서 사용

내보내기는 validation loss가 가장 낮은 epoch을 선택합니다.
실제 validation 이미지 최대 5장의 PyTorch/ONNX 점수를 비교한 뒤 결과를 저장합니다.
검증한 것은 형식·전처리·출력 일치이며, 실물 불량검사 정확도나 threshold 적합성은 별도 평가입니다.
현재 노트북은 test split을 생성·보관하지만 test 성능 보고까지 자동 실행하지 않습니다.

Drive의 `model-bundle.zip`을 내려받아 다음과 같이 배치합니다.

```text
models/weights/my-model/model.onnx
models/weights/my-model/manifest.json
models/weights/my-model/metrics.json
```

replay 또는 live 설정:

```toml
model_manifest = "../models/weights/my-model/manifest.json"
```

기존 `OnnxBinaryClassifier`에서 그대로 읽는 RGB/NCHW/float32/letterbox 계약입니다.
ONNX 출력은 결함 logit 하나이고 런타임에서 sigmoid를 적용합니다.
PASS/FAIL threshold는 검증 세트에서 선택하고, 미세 결함 성능과 관측 정책은 별도로 평가하세요.
가중치와 원본 이미지는 Git에 올리지 않습니다.

## Colab·Drive 관련 주의점

Colab VM은 일시적이고, Pro에서도 리소스·종료 조건은 변동될 수 있습니다.
Drive의 잦은 작은 파일 읽기를 줄이기 위해 작업 디스크에서 학습하며,
이미지가 많으면 ZIP으로 묶어 복사할 수 있게 했습니다.
자세한 동작은 [Colab 공식 FAQ](https://research.google.com/colaboratory/faq.html)를 참고하세요.
마운트된 파일을 다시 읽어 checksum을 검사해도 Drive 서버 동기화 완료를 보장하지는 않으므로
종료 전 Drive 웹 화면에서 파일을 확인하세요.

구현 참고: [PyTorch checkpoint 저장/복원](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html),
[MobileNetV3-Small](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html),
[AMP](https://docs.pytorch.org/docs/stable/notes/amp_examples.html),
[ONNX export](https://docs.pytorch.org/docs/stable/onnx.html).

로컬/CI에서는 작은 합성 데이터로 CPU 학습·재개·ONNX 일치 여부를 테스트합니다.
Colab 계정 인증, 실제 Drive 마운트와 CUDA GPU 학습은 본인 런타임에서 검증해야 합니다.
