# 외부 시스템 확장

WISE-PaaS: `revision.ports.Publisher`를 구현해 로컬 outbox 이벤트를 전송합니다.
프로젝트 내부 JSON과 vendor payload를 분리해 vendor SDK 변경 시 검사 코어를 보존합니다.

PLC/MES/배출기: 현재 실제 출력 코드는 없습니다. 추가 시 `InspectionResult`를 입력받는
전용 adapter를 만들고 검사 코어 내부에서 직접 코일/GPIO를 쓰지 않습니다.
PASS/FAIL/REVIEW/ERROR를 모두 처리하고, REVIEW/ERROR를 정상 통과로 취급하지 않습니다.
검사 ID와 제품 추적 ID의 대응, 결과 ACK, 중복 실행 방지, 장치 timeout을 계약에 포함합니다.
