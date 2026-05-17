---
title: 분석기 & 웹 뷰어
layout: default
nav_order: 5
---

# 분석기 & 웹 뷰어
{: .no_toc }

`hmb-trace-analyze` CLI와 셀프-컨테인드 HTML 리포트(웹 뷰어)를 사용하는 방법을 정리합니다.
{: .fs-5 .fw-300 }

<details open markdown="block">
  <summary>목차</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## 설치 / 첫 실행

```sh
make -C analyzer          # = uv sync
uv run --project analyzer hmb-trace-analyze --help
```

펌웨어/모듈/데몬 셋업 없이도 합성 데이터로 분석기 전체 흐름을 체험할 수 있습니다.

```sh
uv run --project analyzer hmb-trace-synth /tmp/demo.bin \
    -n 50000 --drop-every 1000 --truncate-every 500 --wrap-every 5000
```

이 명령은 약 4 MB의 dump를 만들고, 시퀀스 갭과 truncated 플래그가 의도적으로
섞여 있어 분석기 기능을 한 번에 보기 좋습니다.

## CLI 서브커맨드

| 서브커맨드 | 용도 |
|------------|------|
| `info`     | 한 화면 요약 — 총 record, 시간 범위, records/sec, 경고 |
| `stats`    | opcode/CPU/dt 분포(rich 테이블) |
| `decode`   | 사람이 읽을 수 있는 텍스트 dump |
| `filter`   | opcode/cpu/시간 범위로 필터링 |
| `convert`  | CSV / JSONL 로 export |
| `gaps`     | 시퀀스 갭(드롭 추정) 표 |
| `report`   | 셀프-컨테인드 HTML 리포트 생성 (웹 뷰어) |

전역 옵션:

- `--catalog opcode.json` — 펌웨어 opcode → 이름 매핑 JSON 파일. 형식은
  `{"0x0001": "NAND_READ", ...}` 또는 10진 키도 가능.
- `--no-color` — 컬러 비활성화 (CI/파일 리다이렉트 환경).

### info — 빠른 요약

```
╭─────────────────────────────── hmb-trace info ───────────────────────────────╮
│ 소스          /tmp/demo.bin                                                  │
│ 크기          4.0 MB                                                         │
│ ABI           v1 · ring_hdr=64B · rec_hdr=32B                                │
│ 총 record     49,951                                                         │
│ 기간          10.816 s                                                       │
│ Records/sec   4,618                                                          │
│ payload 평균  51.0 B                                                         │
│ Opcodes       9 개                                                           │
│ CPUs          4 개                                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

`TRUNCATED` 카운트나 시퀀스 갭이 있으면 별도 패널이 노란/빨강으로 따라 붙습니다.

### stats — 상세 분포

`opcode 분포`, `CPU 분포`, `인접 record dt 히스토그램`(로그 스케일 버킷)을 한 번에 보여줍니다.

```sh
uv run --project analyzer hmb-trace-analyze stats /tmp/demo.bin --top 20
```

### gaps — 드롭 추정

시퀀스 번호가 점프한 지점을 모두 모아 표로 출력합니다. 직전/직후 ts도 같이
보여줘 어느 시점에 펌웨어가 record를 흘렸는지 파악할 수 있습니다.

### filter — 조사용 필터링

```sh
# opcode 0x0010(GC start)만, cpu 2만, 5초 ~ 10초 범위
uv run --project analyzer hmb-trace-analyze filter /tmp/demo.bin \
    --opcode 0x0010 --cpu 2 \
    --from-ts 5000000000 --to-ts 10000000000 -n 50
```

`--opcode`/`--cpu` 는 반복 가능합니다(`--opcode 0x0001 --opcode 0x0002`).

### convert — 외부 도구 연동

```sh
uv run --project analyzer hmb-trace-analyze convert /tmp/demo.bin out.csv  --include-payload
uv run --project analyzer hmb-trace-analyze convert /tmp/demo.bin out.jsonl
```

CSV는 표 도구(엑셀, DuckDB 등)에, JSONL은 jq/pandas 파이프라인에 적합합니다.

## HTML 리포트 — 웹 뷰어

```sh
uv run --project analyzer hmb-trace-analyze report /tmp/demo.bin --open
```

- 단일 `.html` 파일이 만들어집니다 (`<dump>.report.html`).
- **외부 CDN/패키지 의존성이 없습니다.** 오프라인에서, 이메일로 보내서, USB로
  넘겨서 어디서나 동일하게 열립니다.
- 다크 테마 UI — 요약 카드, opcode/CPU/dt CSS 바 차트, 시퀀스 갭 표, 페이지네이션이
  되는 record 표(opcode/cpu/플래그/페이로드 hex 검색).
- 통계는 전체 record에 대해, record 표는 `--max-table-rows`(기본 5000) 만큼만
  임베드해 파일 크기와 브라우저 부하를 관리합니다. 그 이상은 CLI(`filter`/`convert`)로.

```
┌──────────────────────────────────────────────────────────────┐
│  HMB Trace Report                                            │
│  소스: /tmp/demo.bin · 크기: 4.0 MB · 생성: 2026-05-17 ...   │
│                                                              │
│  [총 record: 49,951] [기간: 10.8s] [rec/s: 4,618] ...       │
│                                                              │
│  Opcode 분포                                                 │
│  0x0001 NAND_READ      ████████████████  40%   19,943       │
│  0x0002 NAND_PROGRAM   █████████         25%   12,418       │
│  ...                                                         │
│                                                              │
│  시퀀스 갭 (총 49건 · 드롭 추정 97건)                        │
│  prev_seq | next_seq | dropped | prev_ts   | next_ts        │
│                                                              │
│  레코드 [opcode__][cpu__][flags__][hex 검색__]              │
│  ... 페이지네이션 표 ...                                     │
└──────────────────────────────────────────────────────────────┘
```

## opcode 카탈로그 (선택)

자기 펌웨어의 opcode 번호를 사람이 읽을 수 있는 이름으로 매핑하려면 JSON 파일을
하나 만들어 `--catalog` 로 넘기면 됩니다. 빌트인 데모 카탈로그(`cli.DEFAULT_CATALOG`,
`synth.DEMO_OPCODES`)가 형식 예시입니다.

```json
{
  "0x0001": "NAND_READ",
  "0x0002": "NAND_PROGRAM",
  "0x00F0": "ERROR"
}
```

```sh
uv run --project analyzer hmb-trace-analyze info /tmp/demo.bin --catalog mycatalog.json
uv run --project analyzer hmb-trace-analyze report /tmp/demo.bin --catalog mycatalog.json
```

CLI 출력과 HTML 리포트 모두 이 라벨을 자동으로 표시합니다.

## 다음 단계

- 실제 펌웨어 trace를 흘릴 준비가 되었다면 [개발 튜토리얼](tutorial.html)을
  따라 mock 환경을 부팅하세요.
- 새 분석 차원(예: payload 패턴 매칭, 상태 머신 추적)을 추가하고 싶다면
  `analyzer/CLAUDE.md` 의 "새 분석 기능을 추가할 때" 절을 참고.
