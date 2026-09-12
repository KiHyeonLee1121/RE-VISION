# 비교 실험 계획

동일한 테스트 부품과 조명 후보 집합에서 아래 기준을 비교합니다.

| 실험 | 관측 방식 | 목적 |
|---|---|---|
| Single-light | 기본 조명 1회 | 속도/정확도 기준선 |
| Exhaustive | 모든 조명 순서대로 | 최대 관측 기준선 |
| Adaptive-rule | 현재 기본 정책 | 불확실할 때만 재촬영하는 이득 측정 |
| Adaptive-learned | 후속 학습 정책 | 규칙 기반 대비 정보 선택 개선 확인 |

현재 CLI가 직접 구현한 것은 Adaptive-rule 실행과 결과 지표 계산입니다.
나머지 실험 runner와 정책은 추가 구현 대상입니다. 동일 데이터셋·분할·모델·threshold로
비교하고 `part_id`, `experiment_id`, dataset hash, model hash, Git commit,
장비 정보, policy 설정, 실행 모드를 함께 보관합니다.

제품 판정 정확도뿐 아니라 false-pass, REVIEW율, 평균 촬영 수, p95 지연을 함께 봅니다.
`results.example.jsonl`은 지표 계산 사용법을 보여주는 가상 수치이며 프로젝트 성능이 아닙니다.
