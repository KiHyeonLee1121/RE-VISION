# 대시보드 연동 위치

초기 코드는 시각 UI 대신 station API를 제공합니다. 대회 최종 모니터링은
WISE-PaaS Dashboard 구성을 우선하며 세부 매핑은 `docs/wise-paas.md`를 따릅니다.
필요하면 이 디렉토리에 별도 React/Vue 등 로컬 UI를 추가할 수 있습니다.

```bash
python -m pip install -e ".[api]"
python -m revision serve --config configs/demo.toml
```

기본 주소는 `http://127.0.0.1:8000`, API 사용 화면은 `/docs`입니다.

| Method | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 프로세스 준비 상태와 실행 모드 |
| POST | `/inspections` | `{"part_id":"part-001"}` 검사 실행 |
| GET | `/inspections?limit=20` | 최근 검사 결과 |
| GET | `/inspections/{inspection_id}` | 관측·조명·판정 상세 |

동시 검사 요청은 HTTP 409이며 재시도 여부는 호출자가 결정합니다.
검사 verdict ERROR는 저장된 검사 결과이므로 응답 본문에서 반드시 확인해야 합니다.
서버 장애/DB 저장 실패는 5xx입니다. 건강 확인은 카메라 실제 영상 품질 진단이 아닙니다.

UI 표시 항목: 현재 mode, 최종 판정과 사유, 모델 ID, 관측 수, 선택 조명 순서,
점수/품질 사유, 결함 위치·유형, 검사 소요 시간, REVIEW/ERROR 비율.
시뮬레이션 결과는 `mode=demo/replay`로 구분해 실검사 성능 통계와 섞지 않습니다.

API는 로컬 개발용이며 인증을 구현하지 않았습니다. 인터넷 공개 전에는 인증/권한,
TLS, 요청 제한, 원격 조작 정책을 추가합니다. 장비 공유를 막기 위해 worker는 1개로 유지합니다.
