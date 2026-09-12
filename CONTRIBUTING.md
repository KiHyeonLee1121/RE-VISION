# 개발 시작

Python 3.11 이상을 사용합니다. 팀원이 수정할 위치는 `docs/architecture.md`를 먼저 확인하세요.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,api,vision,train]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

새 카메라, 조명 컨트롤러, 모델을 연결할 때는 `ports.py`의 계약을 구현하고
`service.py`에서 조립합니다. 장비 SDK를 `inspection.py`에 직접 import하지 않습니다.
프로토콜이나 JSON 필드의 의미를 바꾸면 스키마 버전과 관련 문서를 함께 갱신합니다.

수정 순서: 기능 브랜치 → 해당 기능 실행 → 영향을 받는 테스트 → PR.
하드웨어가 필요한 변경은 사용한 장치, 펌웨어, 촬영 설정, 검증 범위를 PR에 적습니다.
장비가 없어서 수행하지 못한 검증을 통과로 기록하지 않습니다.

사진, 학습 가중치, 실행 기록, 계정 토큰은 Git에 넣지 않습니다. 데이터셋은
manifest와 checksum으로 버전을 관리하고 원본 저장 위치는 팀에서 별도로 공유합니다.
기존 데이터셋 및 논문 구현을 사용할 때는 해당 라이선스와 이용 조건을 확인합니다.
