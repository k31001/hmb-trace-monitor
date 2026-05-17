# analyzer/ — 오프라인 트레이스 디코더, 분석 CLI, 웹 리포트

라이선스: Apache-2.0. Python ≥ 3.11 패키지 `hmb_trace`.
`daemon/`이 떨어뜨린 raw dump 파일을 구조화된 record로 디코드하고,
조사·분석용 CLI와 셀프-컨테인드 HTML 웹 뷰어를 제공한다.

## 모듈 구성

```
src/hmb_trace/
├── __init__.py    공개 API
├── format.py      RingHeader / RecordHeader — kernel hmb_ring.h 미러
├── stream.py      Record dataclass + iter_records() (lazy stream)
├── stats.py       TraceStats.compute() — opcode/CPU/dt/seq-gap 집계
├── synth.py       합성 dump 생성기 (`hmb-trace-synth` 진입점)
├── report.py      셀프-컨테인드 HTML 리포트 빌더 (CDN 없음)
└── cli.py         `hmb-trace-analyze` 멀티 커맨드 CLI (rich 기반)
```

테스트는 `tests/`에 있고 `pytest -q` 한 줄로 돈다.

## 툴체인

환경 관리는 **uv**. 시스템 `pip` 호출은 하지 않는다.

```sh
uv sync                       # .venv 생성 / 의존성 설치
uv run hmb-trace-analyze --help
uv run hmb-trace-synth /tmp/t.bin -n 1000
uv run pytest                 # 16개 테스트
uv run ruff check .
uv run ruff format --check .
uv run mypy src               # --strict
```

Make 타깃:

```sh
make           # uv sync
make lint      # ruff + mypy
make fmt       # ruff format
make test      # uv run pytest
make clean
```

## 의존성

- 런타임: `rich>=13` 만.
- dev: `pytest`, `ruff`, `mypy`.
- 보고서 HTML은 외부 CDN/패키지 의존성을 가지지 않는다(검증: `tests/test_report.py`).

## 스타일

- **Python 3.11+** 기능만 사용 (`Self`, exception groups, `tomllib` OK).
- **type hint는 필수.** public 함수/dataclass에 부착. `mypy --strict`
  통과 필요(pyproject 설정).
- **ruff**가 lint + format + isort + pyupgrade까지 담당.
  라인 길이 110. `report.py`의 인라인 HTML/JS 템플릿만 E501 예외.
- `TypedDict`보다 `dataclasses` 선호. hot 디코드 경로에서는
  수동 바이트 슬라이싱 대신 `struct.Struct`.
- 라이브러리 코드에서 `print()` 금지. CLI는 rich(`Console`) 사용.

## 디코드 계약

- 입력: `daemon`이 쓴 dump 파일 — 32B 헤더 + payload + 8B 정렬 패딩의
  연속 (자세한 규약은 `docs/trace-format.md` §6.5).
- `version > HMB_TRACE_ABI_VERSION`을 만나면 분석기가 **명확한 에러로
  거부**한다.
- 마이너 버전 후방 호환(새 옵션 플래그 추가)은 허용 — 모르는 플래그 비트는
  로그만 남기고 계속 진행.
- 잘못된 magic / truncated 헤더는 즉시 abort.

## CLI 표면

| 서브커맨드 | 역할 |
|------------|------|
| `info`     | 한 화면 요약(rich Panel) |
| `stats`    | opcode/CPU/dt 분포, 갭 요약 |
| `decode`   | record 한 줄씩 텍스트 dump |
| `filter`   | opcode/cpu/시간 범위로 필터링 |
| `convert`  | CSV / JSONL export (`--include-payload`) |
| `gaps`     | 시퀀스 갭(드롭 추정) 표 |
| `report`   | 단일 HTML 리포트(웹 뷰어) |

`--catalog` 옵션으로 사용자 정의 opcode→이름 매핑 JSON을 넘길 수 있다.
없으면 데모 카탈로그(`hmb-trace-synth`가 생성하는 값들)가 사용된다.

`hmb-trace-synth` 는 별도 진입점으로, 분석기를 시연하거나 테스트할 때
사용하는 합성 dump를 만든다. 시퀀스 드롭/트렁케이션/wrap marker를 강제할
수 있다.

## HTML 리포트(웹 뷰어)

`report` 서브커맨드가 만드는 HTML은 다음을 보장한다.

- **셀프-컨테인드**: 외부 CSS/JS/이미지 의존성 없음. 오프라인 OK.
- **인라인 데이터**: `<script id="report-data" type="application/json">`
  태그에 record + stats를 JSON으로 박는다.
- **클라이언트 필터링**: vanilla JS로 페이지네이션 + opcode/cpu/플래그/
  payload-hex 검색.
- **다크 테마**: GitHub 다크 팔레트 기반.

큰 dump를 다룰 땐 통계는 전체에서 계산하되 record 표는
`--max-table-rows`(기본 5000) 만큼만 박는다. 더 깊은 탐색은
`filter`/`convert` 서브커맨드로.

## 새 분석 기능을 추가할 때

1. 통계 차원이라면 `TraceStats`에 필드 + `compute()` 갱신.
2. CLI에 노출이 필요하면 `_build_parser()`에 서브커맨드 + `_cmd_*` 추가.
3. HTML 리포트에도 보이려면 `_stats_to_json()` 결과에 키를 추가하고
   `_HTML_TEMPLATE` 안 JS에서 카드/바/표 렌더 코드 추가.
4. 테스트는 `tests/test_stream_stats.py` 또는 신규 파일에 1개 이상.

opcode 카탈로그를 코드에 하드코딩하지 말 것 — `--catalog` JSON으로 받게
한다. 빌트인 데모 카탈로그(`cli.DEFAULT_CATALOG`, `synth.DEMO_OPCODES`)는
오직 데모용이다.
