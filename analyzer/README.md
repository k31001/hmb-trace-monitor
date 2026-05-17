# hmb-trace (analyzer)

`hmb-trace-daemon`이 생성한 raw HMB 트레이스 dump 파일을 위한 오프라인
디코더 + 분석 CLI + 셀프-컨테인드 HTML 리포트 생성기.

```sh
uv sync

# 데모용 합성 트레이스 생성
uv run hmb-trace-synth /tmp/demo.bin -n 50000 --drop-every 1000 --truncate-every 500

# 한눈에 보는 요약
uv run hmb-trace-analyze info /tmp/demo.bin

# 상세 통계 (opcode/CPU/dt 분포)
uv run hmb-trace-analyze stats /tmp/demo.bin

# 시퀀스 갭(드롭 추정) 표
uv run hmb-trace-analyze gaps /tmp/demo.bin

# 필터링 + 텍스트 디코드
uv run hmb-trace-analyze filter /tmp/demo.bin --opcode 0x0010 --cpu 2

# CSV/JSONL로 export
uv run hmb-trace-analyze convert /tmp/demo.bin out.csv --include-payload

# 단일 HTML 리포트 (브라우저로 볼 수 있는 웹 뷰어)
uv run hmb-trace-analyze report /tmp/demo.bin --open
```

`--catalog opcode.json` 으로 펌웨어의 opcode → 이름 매핑을 넘기면 모든
출력과 리포트에 라벨이 함께 표시됩니다 (예: `{"0x0001": "NAND_READ", ...}`).

권위 있는 바이너리 레이아웃: [`../docs/trace-format.md`](../docs/trace-format.md).

라이선스: Apache-2.0.
