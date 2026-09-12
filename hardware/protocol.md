# Edge ↔ MCU 조명 통신 v1

이 규격은 **이 저장소가 제안하는 프로젝트 내부 규격**이며 Advantech/Arduino의
기존 표준 프로토콜이 아닙니다. `SerialLighting`을 사용할 MCU 펌웨어가 이 계약을 구현해야 합니다.
보드 및 배선이 미정이므로 실행 가능한 GPIO 펌웨어를 임의의 핀 번호로 넣지 않았습니다.

전송: UTF-8 JSON 한 줄 + LF, 기본 baudrate 115200. 요청마다 고유 `id`를 사용합니다.
방향 이름은 Edge 설정에 있고 MCU에는 channel과 intensity만 보냅니다.

```json
{"v":1,"id":"unique-request-id","command":"set","channel":0,"intensity":0.7}
```

`set`은 **다른 모든 채널을 끄고** 지정된 한 채널을 0..1 범위 PWM/전류 설정으로 적용합니다.
하드웨어 적용이 끝난 다음에만 같은 id로 ACK를 반환합니다.

```json
{"v":1,"id":"unique-request-id","ok":true}
```

전체 OFF:

```json
{"v":1,"id":"another-request-id","command":"off"}
```

유효하지 않은 channel/값/version은 출력하지 않고 같은 id와 `ok:false`를 반환합니다.
다른 요청의 ACK, ACK 누락, 잘못된 JSON은 Edge에서 오류로 처리합니다.
최대 ACK 크기는 LF 포함 2048 bytes, 대기 시간은 `serial.timeout_s`입니다.

MCU 측 필수 구현: 부팅 시 전체 OFF, `set` 원자적 채널 전환, `off` 반복 호출 허용,
잘못된 명령 시 OFF, 호스트 단절/통신 정지 시 watchdog OFF.
watchdog 시간은 촬영·추론 최대 지연과 일관되게 설계하고 실제 타이밍을 확인합니다.
Edge의 `finally`는 프로세스 강제 종료나 케이블 단절 시 실행을 보장하지 않습니다.

## 하드웨어 실험 순서

1. 카메라와 부품을 고정하고 각 LED의 실제 방향을 `direction_deg`와 대응합니다.
2. LED 전원/드라이버의 PWM 및 전류 한계를 확인하고 채널별 응답을 측정합니다.
3. MCU ACK와 OFF, 단절 watchdog을 검증합니다.
4. 카메라 자동노출/자동화이트밸런스를 고정하거나 값을 기록합니다.
   OpenCV의 노출 설정 단위는 장치별로 다르므로 현재 어댑터에서 임의 설정하지 않습니다.
5. 조명 변경 후 안정화 지연과 카메라 버퍼 지연을 측정해 settling/flush 값을 설정합니다.
6. USB prototype에서 순서를 확인한 뒤, 필요하면 trigger 가능한 산업용 카메라로 교체합니다.

`OpenCVCamera.captured_at`은 호스트 수신 시각입니다. 실제 센서 노출 시작 시각이 아니며,
buffer flush만으로 이전 조명 프레임 제거가 보장되지는 않습니다.
