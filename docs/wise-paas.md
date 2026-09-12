# WISE-PaaS 연동 준비

대회 신청서에서 WISE-PaaS 사용을 필수로 지정했습니다. 이 저장소는
검사와 클라우드 연결을 분리하는 Publisher 계약과 영속 outbox를 제공합니다.
**실제 WISE-PaaS tenant 연결, vendor SDK 전송, 태그 생성, 클라우드 Dashboard는 아직 미구현입니다.**

현재 `HttpPublisher`는 팀이 운영하는 **HTTPS 수신 gateway**에 프로젝트 JSON을 보내는
범용 어댑터입니다. WISE-PaaS 주소에 그대로 POST하면 동작한다는 의미가 아닙니다.
선택한 WISE 서비스/버전의 공식 SDK로 `Publisher.publish(event)`를 구현하거나,
이 JSON을 받아 공식 SDK로 변환하는 gateway를 만들어야 합니다.
서비스 규격은 [Advantech 공식 기술 문서](https://docs.wise-paas.advantech.com/)와
대회 제공 교육·계정 자료를 기준으로 확정합니다. API 경로나 인증 필드를 추정하지 않습니다.

## 계정을 받은 뒤 확정할 내용

- 대회에서 제공하는 서비스(DataHub 등)의 정확한 이름과 SDK 버전
- endpoint, tenant/node/device 식별자, 인증 방법과 자격증명
- telemetry tag 생성 규격, timestamp 단위, 문자열/배열 허용 여부
- 연결 재시도 및 실제 수신 확인 방식, Dashboard 조회 경로

## 프로젝트 이벤트 → WISE 태그 설계 초안

아래 태그 이름은 프로젝트 제안이며 vendor 고정 필드가 아닙니다.

| 프로젝트 이벤트 | 의미 | 제안 태그/표현 |
|---|---|---|
| `event_id` | 검사 이벤트 고유 ID | `inspection_id` 또는 별도 이력 키 |
| `part_id` | 검사 부품 ID | `part_id` |
| `started_at` | UTC ISO8601 검사 시각 | SDK timestamp로 변환 |
| `mode` | demo/replay/live | `station_mode` |
| `verdict` | PASS/FAIL/REVIEW/ERROR | `verdict`, 필요 시 수치 enum |
| `defect_score` | 유효 관측 최대 모델 점수 | `defect_score`, null이면 유효 여부 별도 태그 |
| `uncertainty` | 점수 기반 모호함 | `uncertainty_score` |
| `view_count`, `reinspection` | 촬영 횟수/재촬영 여부 | `view_count`, `reinspection` |
| `duration_ms` | 검사 소요 시간 | `inspection_ms` |
| `observations[].action_id/intensity` | 선택한 조명과 밝기 | 관측 이력 또는 별도 per-view tag |
| `observations[].defects` | 위치·유형·치수 | 문자열/별도 이력 저장 지원 확인 후 변환 |

원본 사진과 로컬 경로는 이 이벤트에 포함하지 않습니다.
사진 공유가 필요하면 별도 object storage와 접근 정책을 정하고 참조 ID만 추가합니다.

## outbox 사용

검사 결과와 전송할 이벤트를 하나의 SQLite transaction에 저장합니다.
검사 중 네트워크 전송을 기다리지 않습니다.

```bash
# 아래 주소는 팀이 구현한 gateway여야 합니다. .env는 자동 로드되지 않습니다.
export REVISION_TELEMETRY_URL="https://your-gateway.example/inspection-events"
export REVISION_TELEMETRY_TOKEN="your-token"
python -m revision flush --config configs/demo.toml
```

Windows PowerShell에서는 `$env:REVISION_TELEMETRY_URL="..."` 형식으로 지정합니다.
성공한 이벤트만 delivered로 표시하며 실패 이벤트는 다음 실행에서 재전송합니다.
현재 자동 백그라운드 스케줄러는 없으므로 운영 시 단일 worker/timer로 `flush`를 실행합니다.
수신 측이 받은 직후 프로세스가 끊기면 동일 이벤트가 다시 전송될 수 있습니다.
gateway는 `event_id`/`Idempotency-Key`로 중복을 제거하고 **영속 수신한 뒤에만 2xx**를 응답해야 합니다.
WISE SDK의 단순 publish 호출 반환이 서버 저장 ACK와 같은지는 실제 SDK에서 확인해야 합니다.

## 연동 완료 기준

실계정으로 이벤트 1건을 보내고 Dashboard에서 같은 ID/시각/판정을 조회합니다.
이후 네트워크 단절 → 검사 지속 및 로컬 저장 → 재연결 → outbox 전달 → 중복 처리까지 검증합니다.
현재 코드 테스트의 fake publisher 성공은 이 실계정 검증을 대신하지 않습니다.
