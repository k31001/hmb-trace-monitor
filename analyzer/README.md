# hmb-trace (analyzer)

`hmb-trace-daemon`이 생성한 raw HMB 트레이스 dump 파일을 위한 오프라인
디코더입니다.

```sh
uv sync
uv run hmb-trace-analyze decode /path/to/trace.bin
```

권위 있는 바이너리 레이아웃은 [`../docs/trace-format.md`](../docs/trace-format.md)
에 있습니다.

라이선스: Apache-2.0.
