# analyzer/ — 오프라인 트레이스 디코더 & CLI

라이선스: Apache-2.0. Python ≥ 3.11 패키지 `hmb_trace`.
`daemon/`이 떨어뜨린 raw dump 파일을 구조화된 record로 디코드하고,
조사·분석용 CLI를 제공한다.

## 툴체인

환경 관리는 **uv** 사용. 시스템 `pip` 호출은 하지 않는다.

```sh
uv sync                       # .venv 생성 / 의존성 설치
uv run hmb-trace-analyze --help
uv run pytest                 # 테스트 (예정)
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Make 타깃 (`make -C analyzer …`):

```sh
make            # uv sync
make lint       # ruff + mypy
make fmt        # ruff format
make test       # uv run pytest
make clean      # .venv, 캐시 제거
```

## 스타일

- **Python 3.11+** 기능만 사용 (`Self`, exception groups, `tomllib` OK).
- **type hint는 필수.** 모든 public 함수/dataclass에 부착.
  pyproject.toml 설정으로 `mypy --strict` 통과.
- **ruff**가 lint + format + isort + pyupgrade까지 담당하는 단일 도구.
- `TypedDict`보다 `dataclasses` 선호. hot 디코드 경로에서는
  수동 바이트 슬라이싱보다 `struct.Struct` + `memoryview`.
- 라이브러리 코드에서 `print()` 금지 — `logging` 사용. CLI는 `rich`가
  있으면 사용, 없으면 평범한 stdio.

## 디코드 계약

- 입력: HMB ring 스냅샷의 연속 또는 미리 추출된 record 스트림인 raw
  바이트 파일. 첫 헤더의 magic + version으로 dialect를 식별한다.
- 디코더는 `version > HMB_TRACE_ABI_VERSION`을 만나면 **명확한 에러로
  거부**한다. 마이너 버전 후방 호환(새 옵션 플래그 추가)은 허용.
- 테스트 벡터는 `docs/test-vectors/` 아래에 살며 `tests/test_format.py`
  에서 라운드트립한다.

## CLI 표면

```
hmb-trace-analyze decode  <dump>           # record를 텍스트로 dump
hmb-trace-analyze stats   <dump>           # opcode/cpu별 카운트, ts 히스토그램
hmb-trace-analyze convert <dump> <out.csv> # 표 형식 export
```

CLI는 `argparse` 기반. 새 top-level 명령은 `docs/abi.md` 갱신 없이
추가하지 않는다.
