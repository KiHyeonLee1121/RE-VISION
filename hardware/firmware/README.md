# MCU 펌웨어 구현 위치

선정된 MCU용 프로젝트(예: PlatformIO, Arduino, 제조사 SDK)를 이 디렉토리에 추가합니다.
현재 펌웨어는 제공하지 않으며, Edge 쪽 serial adapter와 fake serial 테스트가 준비되어 있습니다.

구현할 외부 계약은 `../protocol.md`입니다. 보드, LED driver, channel-to-pin 표,
PWM 범위, watchdog timeout을 확정한 뒤 코드와 회로 연결표를 함께 추가하세요.
호스트가 보낸 디지털 핀 번호를 그대로 실행하는 범용 명령은 만들지 않습니다.
